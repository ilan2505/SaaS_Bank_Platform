import io

from app.main import app
from app.services.ai_provider import AIProvider, ExtractionResult
from app.services.pdf_extraction import get_provider


class FakeProvider(AIProvider):
    def __init__(self, result: ExtractionResult):
        self._result = result

    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        return self._result


def _upload_pdf(client, batch_id, records, filename="doc.pdf"):
    provider = FakeProvider(ExtractionResult(records=records))
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        return client.post(
            f"/api/batches/{batch_id}/upload/pdf",
            files={"files": (filename, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
    finally:
        del app.dependency_overrides[get_provider]


def _upload_csv(client, batch_id, csv_content, filename="data.csv"):
    return client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": (filename, io.BytesIO(csv_content.encode()), "text/csv")},
    )


INVOICE_RECORD = {
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

STATEMENT_LINE = {
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


def test_statement_line_uploaded_after_invoice_is_backfilled_immediately(client, batch_id):
    _upload_pdf(client, batch_id, [INVOICE_RECORD], filename="invoice.pdf")
    r = _upload_pdf(client, batch_id, [STATEMENT_LINE], filename="statement.pdf")

    record = r.json()["records"][0]
    assert record["counterparty_name"] == "LexBridge Advisory S.A."
    assert record["counterparty_account"] == "LU55 0019 8000 4411 2200"
    assert record["status"] == "VALID"


def test_statement_line_uploaded_before_invoice_is_backfilled_retroactively(client, batch_id):
    r1 = _upload_pdf(client, batch_id, [STATEMENT_LINE], filename="statement.pdf")
    stm_record = r1.json()["records"][0]
    assert stm_record["counterparty_name"] is None
    assert stm_record["status"] == "NEEDS_REVIEW"

    _upload_pdf(client, batch_id, [INVOICE_RECORD], filename="invoice.pdf")

    updated = client.get(f"/api/records/{stm_record['id']}").json()
    assert updated["counterparty_name"] == "LexBridge Advisory S.A."
    assert updated["status"] == "VALID"


def test_csv_invoice_number_reconciles_a_pdf_statement_line(client, batch_id):
    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-2026-0006,2026-07-06,,Audit services - Q2,4800.00,0.00,816.00,5616.00,EUR,"
        "Audit Partners Luxembourg,LU740011112222333344,LU,AUDIT,APL-Q2-2026,BANK_TRANSFER\n"
    )
    audit_line = {
        "reference": "STM-7716",
        "transaction_date": "2026-07-18",
        "description": "Audit fee APL-Q2-2026",
        "gross_amount": "-5616.00",
        "tax_amount": "0.00",
        "fee_amount": "0.00",
        "net_amount": "-5616.00",
        "currency": "EUR",
        "counterparty_name": None,
        "country": "LU",
        "category": "AUDIT",
        "confidence": 0.95,
    }

    r1 = _upload_pdf(client, batch_id, [audit_line], filename="statement.pdf")
    stm_record = r1.json()["records"][0]
    assert stm_record["counterparty_name"] is None

    _upload_csv(client, batch_id, csv_content)

    updated = client.get(f"/api/records/{stm_record['id']}").json()
    assert updated["counterparty_name"] == "Audit Partners Luxembourg"
    assert updated["counterparty_account"] == "LU740011112222333344"
    assert updated["status"] == "VALID"


def test_unrelated_description_is_not_reconciled(client, batch_id):
    unrelated_line = {**STATEMENT_LINE, "reference": "STM-9999", "description": "Bank transfer fee"}
    _upload_pdf(client, batch_id, [INVOICE_RECORD], filename="invoice.pdf")
    r = _upload_pdf(client, batch_id, [unrelated_line], filename="statement.pdf")

    record = r.json()["records"][0]
    assert record["counterparty_name"] is None
    assert record["status"] == "NEEDS_REVIEW"


def test_mismatched_amount_prevents_false_positive_match(client, batch_id):
    wrong_amount_line = {**STATEMENT_LINE, "reference": "STM-8888", "net_amount": "-1.00", "gross_amount": "-1.00"}
    _upload_pdf(client, batch_id, [INVOICE_RECORD], filename="invoice.pdf")
    r = _upload_pdf(client, batch_id, [wrong_amount_line], filename="statement.pdf")

    record = r.json()["records"][0]
    assert record["counterparty_name"] is None
