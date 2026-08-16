"""Cross-document reconciliation within a batch.

A bank statement line's description often mentions the reference of an
invoice that was uploaded separately (e.g. "Legal fees INV-LX-441"), or a
CSV row's invoice_number that matches it (e.g. "APL-Q2-2026"). When that
other record already has a counterparty_name, this backfills it onto the
line that's missing one, then re-validates the changed records.

Runs after every upload over the *whole* batch (not just the new records),
so order doesn't matter: uploading the bank statement before the invoice
that resolves one of its lines works the same as uploading it after.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FinancialRecord
from app.services.validation import (
    AMOUNT_TOLERANCE,
    check_business_rules,
    determine_status,
    parse_record_fields,
    record_to_raw_dict,
)


def _find_match(record: FinancialRecord, records: list[FinancialRecord]) -> FinancialRecord | None:
    if not record.description:
        return None
    description = record.description.upper()
    my_amount = abs(record.net_amount) if record.net_amount is not None else None

    for other in records:
        if other.id == record.id or not other.counterparty_name:
            continue
        for candidate_ref in (other.reference, other.invoice_number):
            if not candidate_ref or candidate_ref.upper() not in description:
                continue
            if my_amount is not None and other.net_amount is not None:
                if abs(my_amount - abs(other.net_amount)) > AMOUNT_TOLERANCE:
                    continue
            return other
    return None


def reconcile_batch(db: Session, batch_id: str) -> None:
    records = db.scalars(
        select(FinancialRecord).where(FinancialRecord.batch_id == batch_id)
    ).all()

    changed: list[FinancialRecord] = []
    for record in records:
        if record.counterparty_name:
            continue
        match = _find_match(record, records)
        if match:
            record.counterparty_name = match.counterparty_name
            record.counterparty_account = match.counterparty_account
            changed.append(record)

    if not changed:
        return

    all_refs = {r.reference for r in records if r.reference}
    for record in changed:
        raw = record_to_raw_dict(record)
        typed, raw_kept, parse_errors = parse_record_fields(raw)
        other_refs = all_refs - ({record.reference} if record.reference else set())
        errors = check_business_rules(typed, parse_errors, other_refs)
        status = determine_status(
            errors,
            source_type=record.source_type,
            extraction_confidence=record.extraction_confidence,
            confidence_threshold=settings.extraction_confidence_threshold,
        )
        record.validation_errors = errors
        record.raw_values = raw_kept
        record.status = status

    db.commit()
