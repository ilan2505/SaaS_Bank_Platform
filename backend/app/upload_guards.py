"""Basic upload hardening: size limits and content-signature checks.

Trusting a client-supplied filename or extension for what a file "is" is
weak — the checks here also look at the actual bytes, not just the name.
"""

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
PDF_MAGIC = b"%PDF-"


def check_upload_size(content: bytes, filename: str) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(413, f"'{filename}' exceeds the {limit_mb}MB upload limit")


def check_pdf_signature(content: bytes, filename: str) -> None:
    """A .pdf extension is just a client-supplied string; this checks the
    actual file header so an upload can't smuggle arbitrary content past
    the extension check by simply naming it *.pdf."""
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(400, f"'{filename}' does not look like a valid PDF file")
