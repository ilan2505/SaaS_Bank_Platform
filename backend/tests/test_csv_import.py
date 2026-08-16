import io

from tests.conftest import SAMPLES_DIR


def test_full_sample_csv_import(client, batch_id):
    """The provided transactions_import.csv has 30 rows, 13 of which are
    intentionally invalid. All 30 must be imported (never reject the whole
    file), split correctly between VALID and NEEDS_REVIEW."""
    with open(SAMPLES_DIR / "transactions_import.csv", "rb") as f:
        r = client.post(
            f"/api/batches/{batch_id}/upload/csv",
            files={"file": ("transactions_import.csv", f, "text/csv")},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["records_created"] == 30

    summary = client.get(f"/api/batches/{batch_id}").json()
    assert summary["total_records"] == 30
    assert summary["needs_review_count"] == 13
    assert summary["valid_count"] == 17
    assert summary["csv_documents"] == ["transactions_import.csv"]
    assert summary["pdf_documents"] == []


def test_source_filename_and_batch_association_preserved(client, batch_id):
    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-1,2026-07-01,2026-07-01,Test row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
    )
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("my_upload.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    record = r.json()["records"][0]
    assert record["source_document_name"] == "my_upload.csv"
    assert record["source_type"] == "CSV"
    assert record["batch_id"] == batch_id
    assert record["status"] == "VALID"


def test_incomplete_row_does_not_reject_whole_file(client, batch_id):
    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-1,2026-07-01,,Good row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
        "TX-2,not-a-date,,Bad date row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
    )
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("mixed.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r.status_code == 200
    records = r.json()["records"]
    assert len(records) == 2
    statuses = {rec["reference"]: rec["status"] for rec in records}
    assert statuses["TX-1"] == "VALID"
    assert statuses["TX-2"] == "NEEDS_REVIEW"


def test_batch_summary_endpoint(client, batch_id):
    r = client.get(f"/api/batches/{batch_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == batch_id
    assert data["total_records"] == 0
    assert data["needs_review_count"] == 0


def test_delete_batch_removes_it_and_its_records(client, batch_id):
    with open(SAMPLES_DIR / "transactions_import.csv", "rb") as f:
        client.post(
            f"/api/batches/{batch_id}/upload/csv",
            files={"file": ("transactions_import.csv", f, "text/csv")},
        )

    r = client.delete(f"/api/batches/{batch_id}")
    assert r.status_code == 204

    assert client.get(f"/api/batches/{batch_id}").status_code == 404
    assert client.get(f"/api/batches/{batch_id}/records").status_code == 404
    assert batch_id not in {b["id"] for b in client.get("/api/batches").json()}


def test_delete_unknown_batch_returns_404(client):
    r = client.delete("/api/batches/does-not-exist")
    assert r.status_code == 404
