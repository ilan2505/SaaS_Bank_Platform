import io

from app.main import app
from app.services.ai_provider import AIProvider, ExtractionResult
from app.services.pdf_extraction import get_provider


class FakeProvider(AIProvider):
    def __init__(self, result: ExtractionResult):
        self._result = result

    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        return self._result


def _upload_with_provider(client, batch_id, provider, filename="doc.pdf"):
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        r = client.post(
            f"/api/batches/{batch_id}/upload/pdf",
            files={"files": (filename, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
    finally:
        del app.dependency_overrides[get_provider]
    return r


def test_provider_error_does_not_crash_and_creates_needs_review_placeholder(client, batch_id):
    provider = FakeProvider(ExtractionResult(error="AI provider request timed out"))
    r = _upload_with_provider(client, batch_id, provider)

    assert r.status_code == 200
    records = r.json()["records"]
    assert len(records) == 1
    assert records[0]["status"] == "NEEDS_REVIEW"
    assert any(e["field"] == "_extraction" for e in records[0]["validation_errors"])


def test_invalid_structured_response_is_handled_gracefully(client, batch_id):
    provider = FakeProvider(ExtractionResult(error="Invalid structured response from AI provider: not a list"))
    r = _upload_with_provider(client, batch_id, provider)

    assert r.status_code == 200
    assert r.json()["records"][0]["status"] == "NEEDS_REVIEW"


def test_pdf_record_missing_required_field_is_needs_review(client, batch_id):
    provider = FakeProvider(
        ExtractionResult(
            records=[
                {
                    "reference": "INV-1",
                    "transaction_date": "2026-07-02",
                    "description": "Legal services",
                    "gross_amount": "3900.00",
                    "tax_amount": "780.00",
                    "fee_amount": "0.00",
                    "net_amount": "4680.00",
                    "currency": "EUR",
                    "counterparty_name": None,  # missing required field
                    "country": "LU",
                    "category": "PROFESSIONAL_SERVICES",
                    "confidence": 0.95,
                }
            ]
        )
    )
    r = _upload_with_provider(client, batch_id, provider, filename="invoice.pdf")

    assert r.status_code == 200
    record = r.json()["records"][0]
    assert record["status"] == "NEEDS_REVIEW"
    assert any(e["field"] == "counterparty_name" for e in record["validation_errors"])
    assert record["source_type"] == "PDF"
    assert record["source_document_name"] == "invoice.pdf"


def test_low_confidence_forces_needs_review_even_if_fields_complete(client, batch_id):
    provider = FakeProvider(
        ExtractionResult(
            records=[
                {
                    "reference": "INV-2",
                    "transaction_date": "2026-07-02",
                    "description": "Legal services",
                    "gross_amount": "100.00",
                    "tax_amount": "0.00",
                    "fee_amount": "0.00",
                    "net_amount": "100.00",
                    "currency": "EUR",
                    "counterparty_name": "ACME",
                    "country": "LU",
                    "category": "PROFESSIONAL_SERVICES",
                    "confidence": 0.4,
                }
            ]
        )
    )
    r = _upload_with_provider(client, batch_id, provider)
    record = r.json()["records"][0]
    assert record["status"] == "NEEDS_REVIEW"


def test_bank_statement_produces_multiple_records(client, batch_id):
    lines = [
        {
            "reference": f"STM-{i}",
            "transaction_date": "2026-07-01",
            "description": f"Line {i}",
            "gross_amount": "100.00",
            "tax_amount": "0.00",
            "fee_amount": "0.00",
            "net_amount": "100.00",
            "currency": "EUR",
            "counterparty_name": "Bank",
            "country": "LU",
            "category": "OTHER",
            "confidence": 0.9,
        }
        for i in range(1, 9)
    ]
    provider = FakeProvider(ExtractionResult(records=lines))
    r = _upload_with_provider(client, batch_id, provider, filename="bank_statement.pdf")

    assert r.status_code == 200
    records = r.json()["records"]
    assert len(records) == 8
    assert all(rec["source_type"] == "PDF" for rec in records)
    assert all(rec["source_document_name"] == "bank_statement.pdf" for rec in records)
    assert {rec["reference"] for rec in records} == {f"STM-{i}" for i in range(1, 9)}


def test_duplicate_reference_across_pdf_records_is_flagged(client, batch_id):
    dup = {
        "reference": "STM-DUP",
        "transaction_date": "2026-07-01",
        "description": "Line",
        "gross_amount": "100.00",
        "tax_amount": "0.00",
        "fee_amount": "0.00",
        "net_amount": "100.00",
        "currency": "EUR",
        "counterparty_name": "Bank",
        "country": "LU",
        "category": "OTHER",
        "confidence": 0.9,
    }
    provider = FakeProvider(ExtractionResult(records=[dup, dict(dup)]))
    r = _upload_with_provider(client, batch_id, provider)
    records = r.json()["records"]
    assert records[0]["status"] == "VALID"
    assert records[1]["status"] == "NEEDS_REVIEW"
    assert any(e["field"] == "reference" for e in records[1]["validation_errors"])


def test_original_pdf_is_stored_and_servable(client, batch_id):
    provider = FakeProvider(ExtractionResult(records=[]))
    r = _upload_with_provider(client, batch_id, provider, filename="statement.pdf")
    record = r.json()["records"][0]
    assert record["has_source_file"] is True

    r = client.get(f"/api/records/{record['id']}/source-file")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-1.4 fake"


def test_deleting_document_removes_its_records_and_stored_pdf(client, batch_id):
    provider = FakeProvider(ExtractionResult(records=[]))
    r = _upload_with_provider(client, batch_id, provider, filename="to_delete.pdf")
    record_id = r.json()["records"][0]["id"]

    r = client.delete(f"/api/batches/{batch_id}/documents", params={"filename": "to_delete.pdf"})
    assert r.status_code == 204

    assert client.get(f"/api/records/{record_id}").status_code == 404
    assert client.get(f"/api/batches/{batch_id}/records").json() == []


def test_csv_record_has_no_source_file(client, batch_id):
    import io as _io

    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-1,2026-07-01,,Row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
    )
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("data.csv", _io.BytesIO(csv_content.encode()), "text/csv")},
    )
    record = r.json()["records"][0]
    assert record["has_source_file"] is False

    r = client.get(f"/api/records/{record['id']}/source-file")
    assert r.status_code == 404
