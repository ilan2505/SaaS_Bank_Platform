import io

from app.main import app
from app.services.ai_provider import AIProvider, ExtractionResult
from app.services.pdf_extraction import get_provider


class FakeProvider(AIProvider):
    def __init__(self, result: ExtractionResult):
        self._result = result

    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        return self._result


def _upload_one_csv_row(client, batch_id):
    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-1,2026-07-01,,Row,100.00,0.00,0.00,100.00,EUR,,,LU,OTHER,,BANK_TRANSFER\n"
    )
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("data.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    return r.json()["records"][0]


def test_editing_a_field_creates_a_history_entry(client, batch_id):
    record = _upload_one_csv_row(client, batch_id)
    assert record["counterparty_name"] is None

    client.patch(f"/api/records/{record['id']}", json={"counterparty_name": "ACME"})

    history = client.get(f"/api/records/{record['id']}/history").json()
    entries = {h["field"]: h for h in history}
    assert entries["counterparty_name"]["old_value"] is None
    assert entries["counterparty_name"]["new_value"] == "ACME"
    assert entries["counterparty_name"]["source"] == "edit"


def test_saving_without_changing_a_value_creates_no_history(client, batch_id):
    record = _upload_one_csv_row(client, batch_id)

    client.patch(f"/api/records/{record['id']}", json={"description": record["description"]})

    history = client.get(f"/api/records/{record['id']}/history").json()
    assert history == []


def test_changing_two_fields_creates_two_entries(client, batch_id):
    record = _upload_one_csv_row(client, batch_id)

    client.patch(
        f"/api/records/{record['id']}",
        json={"counterparty_name": "ACME", "country": "GB"},
    )

    history = client.get(f"/api/records/{record['id']}/history").json()
    changed_fields = {h["field"] for h in history}
    assert changed_fields == {"counterparty_name", "country"}
    for h in history:
        assert h["source"] == "edit"


def test_history_endpoint_404_for_unknown_record(client):
    r = client.get("/api/records/does-not-exist/history")
    assert r.status_code == 404


def test_reconciliation_backfill_is_logged_with_source_reconciliation(client, batch_id):
    invoice_record = {
        "reference": "INV-LX-441",
        "transaction_date": "2026-07-02",
        "description": "Legal structuring services",
        "gross_amount": "3900.00",
        "tax_amount": "780.00",
        "fee_amount": "0.00",
        "net_amount": "4680.00",
        "currency": "EUR",
        "counterparty_name": "LexBridge Advisory S.A.",
        "counterparty_account": "LU55 0019 8000 4411 2200",
        "country": "LU",
        "category": "PROFESSIONAL_SERVICES",
        "confidence": 1.0,
    }
    statement_line = {
        "reference": "STM-7713",
        "transaction_date": "2026-07-05",
        "description": "Legal fees INV-LX-441",
        "gross_amount": "-4680.00",
        "tax_amount": "0.00",
        "fee_amount": "0.00",
        "net_amount": "-4680.00",
        "currency": "EUR",
        "counterparty_name": None,
        "country": "LU",
        "category": "PROFESSIONAL_SERVICES",
        "confidence": 0.95,
    }

    def upload_pdf(records, filename):
        provider = FakeProvider(ExtractionResult(records=records))
        app.dependency_overrides[get_provider] = lambda: provider
        try:
            content = f"%PDF-1.4 fake content for {filename}".encode()
            return client.post(
                f"/api/batches/{batch_id}/upload/pdf",
                files={"files": (filename, io.BytesIO(content), "application/pdf")},
            )
        finally:
            del app.dependency_overrides[get_provider]

    r1 = upload_pdf([statement_line], "statement.pdf")
    stm_id = r1.json()["records"][0]["id"]

    upload_pdf([invoice_record], "invoice.pdf")

    history = client.get(f"/api/records/{stm_id}/history").json()
    changed_fields = {h["field"] for h in history}
    assert changed_fields == {"counterparty_name", "counterparty_account"}
    for h in history:
        assert h["source"] == "reconciliation"
        assert h["old_value"] is None
    assert next(h for h in history if h["field"] == "counterparty_name")["new_value"] == "LexBridge Advisory S.A."
