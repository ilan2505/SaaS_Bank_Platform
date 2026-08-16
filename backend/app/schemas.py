from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValidationError(BaseModel):
    field: str
    message: str


class BatchCreate(BaseModel):
    name: str


class BatchSummary(BaseModel):
    id: str
    name: str
    created_at: datetime
    total_records: int
    needs_review_count: int
    valid_count: int
    validated_count: int
    source_documents: list[str]

    model_config = ConfigDict(from_attributes=True)


class BatchOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordOut(BaseModel):
    id: str
    batch_id: str

    reference: str | None = None
    transaction_date: date | None = None
    value_date: date | None = None
    description: str | None = None

    gross_amount: Decimal | None = None
    fee_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    net_amount: Decimal | None = None

    currency: str | None = None
    counterparty_name: str | None = None
    counterparty_account: str | None = None
    country: str | None = None
    category: str | None = None
    invoice_number: str | None = None
    payment_method: str | None = None

    source_type: str
    source_document_name: str
    extraction_confidence: Decimal | None = None

    status: str
    validation_errors: list[ValidationError]
    raw_values: dict[str, Any]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordUpdate(BaseModel):
    """All fields optional: only the ones supplied are patched onto the record."""

    reference: str | None = None
    transaction_date: str | None = None
    value_date: str | None = None
    description: str | None = None
    gross_amount: str | None = None
    fee_amount: str | None = None
    tax_amount: str | None = None
    net_amount: str | None = None
    currency: str | None = None
    counterparty_name: str | None = None
    counterparty_account: str | None = None
    country: str | None = None
    category: str | None = None
    invoice_number: str | None = None
    payment_method: str | None = None


class UploadResult(BaseModel):
    batch_id: str
    records_created: int
    records: list[RecordOut]
