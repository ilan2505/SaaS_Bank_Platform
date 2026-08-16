"""Persists uploaded PDF bytes to local disk so the review UI can show the
original document next to its extracted fields.

Local filesystem storage is fine for this assignment's scale; in production
this would be object storage (S3 or equivalent) behind the same two
functions, so callers wouldn't need to change.
"""

import hashlib
import shutil
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_ROOT = BACKEND_DIR / "uploads"


def save_pdf(batch_id: str, filename: str, content: bytes) -> str:
    """Saves the PDF and returns a path relative to BACKEND_DIR for storage on the record."""
    batch_dir = UPLOADS_ROOT / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    full_path = batch_dir / unique_name
    full_path.write_bytes(content)

    return str(full_path.relative_to(BACKEND_DIR))


def resolve(relative_path: str) -> Path:
    return BACKEND_DIR / relative_path


def delete_batch_uploads(batch_id: str) -> None:
    batch_dir = UPLOADS_ROOT / batch_id
    if batch_dir.exists():
        shutil.rmtree(batch_dir, ignore_errors=True)


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
