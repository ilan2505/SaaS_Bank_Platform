import io

from app.main import app
from app.services.ai_provider import AIProvider, ExtractionResult
from app.services.pdf_extraction import get_provider


class FakeProvider(AIProvider):
    def __init__(self, result: ExtractionResult):
        self._result = result

    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        return self._result


CSV_CONTENT = (
    "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
    "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
    "category,invoice_number,payment_method\n"
    "TX-1,2026-07-01,,Row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
)


def test_upload_csv_rejects_byte_identical_content_under_a_different_filename(client, batch_id):
    r1 = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("a.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("b.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    assert r2.status_code == 409
    assert "a.csv" in r2.json()["detail"]


def test_upload_csv_allows_different_content(client, batch_id):
    other_content = CSV_CONTENT.replace("TX-1", "TX-2")
    r1 = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("a.csv", io.BytesIO(CSV_CONTENT.encode()), "text/csv")},
    )
    r2 = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("b.csv", io.BytesIO(other_content.encode()), "text/csv")},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200


def _upload_pdf(client, batch_id, filename, content=b"%PDF-1.4 identical content"):
    provider = FakeProvider(ExtractionResult(records=[]))
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        return client.post(
            f"/api/batches/{batch_id}/upload/pdf",
            files={"files": (filename, io.BytesIO(content), "application/pdf")},
        )
    finally:
        del app.dependency_overrides[get_provider]


def test_upload_pdf_rejects_byte_identical_content_across_separate_uploads(client, batch_id):
    r1 = _upload_pdf(client, batch_id, "first.pdf")
    assert r1.status_code == 200

    r2 = _upload_pdf(client, batch_id, "second.pdf")  # same default content, different name
    assert r2.status_code == 409
    assert "first.pdf" in r2.json()["detail"]


def test_upload_pdf_rejects_byte_identical_content_within_the_same_multi_file_upload(client, batch_id):
    provider = FakeProvider(ExtractionResult(records=[]))
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        content = b"%PDF-1.4 identical content"
        r = client.post(
            f"/api/batches/{batch_id}/upload/pdf",
            files=[
                ("files", ("a.pdf", io.BytesIO(content), "application/pdf")),
                ("files", ("b.pdf", io.BytesIO(content), "application/pdf")),
            ],
        )
    finally:
        del app.dependency_overrides[get_provider]
    assert r.status_code == 409


def test_upload_pdf_allows_different_content(client, batch_id):
    r1 = _upload_pdf(client, batch_id, "a.pdf", content=b"%PDF-1.4 content A")
    r2 = _upload_pdf(client, batch_id, "b.pdf", content=b"%PDF-1.4 content B")
    assert r1.status_code == 200
    assert r2.status_code == 200
