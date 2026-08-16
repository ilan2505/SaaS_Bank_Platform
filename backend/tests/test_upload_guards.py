import io

import pytest
from fastapi import HTTPException

from app.upload_guards import MAX_UPLOAD_BYTES, check_pdf_signature, check_upload_size


def test_check_upload_size_accepts_normal_content():
    check_upload_size(b"small content", "ok.csv")  # must not raise


def test_check_upload_size_rejects_oversized_content():
    with pytest.raises(HTTPException) as exc:
        check_upload_size(b"x" * (MAX_UPLOAD_BYTES + 1), "big.csv")
    assert exc.value.status_code == 413


def test_check_pdf_signature_accepts_real_pdf_bytes():
    check_pdf_signature(b"%PDF-1.4 rest of file...", "real.pdf")  # must not raise


def test_check_pdf_signature_rejects_non_pdf_bytes():
    with pytest.raises(HTTPException) as exc:
        check_pdf_signature(b"this is not a pdf", "fake.pdf")
    assert exc.value.status_code == 400


def test_upload_pdf_endpoint_rejects_content_that_isnt_actually_a_pdf(client, batch_id):
    r = client.post(
        f"/api/batches/{batch_id}/upload/pdf",
        files={"files": ("fake.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_csv_endpoint_rejects_oversized_file(client, batch_id):
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        f"/api/batches/{batch_id}/upload/csv",
        files={"file": ("big.csv", io.BytesIO(oversized), "text/csv")},
    )
    assert r.status_code == 413
