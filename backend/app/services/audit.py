"""Field-level change tracking for financial_record.

Two call sites produce history: a user correction (PATCH /records/{id})
and automatic cross-document reconciliation. Both follow the same
snapshot-before / compare-after pattern so a real change (not just a
no-op save) is what gets logged.
"""

from sqlalchemy.orm import Session

from app.models import FinancialRecord, RecordEditHistory

TRACKED_FIELDS = [
    "reference",
    "transaction_date",
    "value_date",
    "description",
    "gross_amount",
    "fee_amount",
    "tax_amount",
    "net_amount",
    "currency",
    "counterparty_name",
    "counterparty_account",
    "country",
    "category",
    "invoice_number",
    "payment_method",
]


def snapshot(record: FinancialRecord) -> dict:
    return {field: getattr(record, field, None) for field in TRACKED_FIELDS}


def log_changes(db: Session, record: FinancialRecord, before: dict, source: str = "edit") -> None:
    for field, old_value in before.items():
        new_value = getattr(record, field, None)
        if old_value != new_value:
            db.add(
                RecordEditHistory(
                    record_id=record.id,
                    field=field,
                    old_value=str(old_value) if old_value is not None else None,
                    new_value=str(new_value) if new_value is not None else None,
                    source=source,
                )
            )
