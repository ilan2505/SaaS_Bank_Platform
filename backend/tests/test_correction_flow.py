import io


def _upload_bad_row(client, batch_id):
    csv_content = (
        "reference,transaction_date,value_date,description,gross_amount,fee_amount,"
        "tax_amount,net_amount,currency,counterparty_name,counterparty_account,country,"
        "category,invoice_number,payment_method\n"
        "TX-1,2026-13-16,,Bad date row,100.00,0.00,0.00,100.00,EUR,ACME,,LU,OTHER,,BANK_TRANSFER\n"
    )
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    return r.json()["records"][0]


def test_validate_rejected_while_needs_review(client, batch_id):
    record = _upload_bad_row(client, batch_id)
    assert record["status"] == "NEEDS_REVIEW"

    r = client.post(f"/api/records/{record['id']}/validate")
    assert r.status_code == 409


def test_successful_correction_and_revalidation(client, batch_id):
    record = _upload_bad_row(client, batch_id)
    record_id = record["id"]

    r = client.patch(f"/api/records/{record_id}", json={"transaction_date": "2026-07-16"})
    assert r.status_code == 200
    assert r.json()["status"] == "NEEDS_REVIEW"  # pending explicit revalidation

    r = client.post(f"/api/records/{record_id}/revalidate")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "VALID"
    assert body["validation_errors"] == []

    r = client.post(f"/api/records/{record_id}/validate")
    assert r.status_code == 200
    assert r.json()["status"] == "VALIDATED"


def test_revalidate_still_needs_review_if_still_invalid(client, batch_id):
    record = _upload_bad_row(client, batch_id)
    record_id = record["id"]

    r = client.post(f"/api/records/{record_id}/revalidate")
    assert r.json()["status"] == "NEEDS_REVIEW"
    assert any(e["field"] == "transaction_date" for e in r.json()["validation_errors"])


def test_get_record_errors_endpoint(client, batch_id):
    record = _upload_bad_row(client, batch_id)
    r = client.get(f"/api/records/{record['id']}/errors")
    assert r.status_code == 200
    assert any(e["field"] == "transaction_date" for e in r.json())
