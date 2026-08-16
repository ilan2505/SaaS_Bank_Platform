"""CSV ingestion. Every row is imported, valid or not: invalid rows are kept
as NEEDS_REVIEW records with structured errors rather than causing the whole
file (or that row) to be rejected outright, per the assignment's brief.
"""

import csv
import io

from app.config import settings
from app.models import FinancialRecord, RecordStatus, SourceType
from app.services.validation import check_business_rules, parse_record_fields


def import_csv(content: bytes, filename: str, batch_id: str) -> list[FinancialRecord]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    records: list[FinancialRecord] = []
    seen_references: set[str] = set()

    for row in reader:
        typed, raw_kept, parse_errors = parse_record_fields(row)

        errors = check_business_rules(typed, parse_errors, other_references=seen_references)
        reference = typed.get("reference")
        if reference:
            seen_references.add(reference)

        status = RecordStatus.NEEDS_REVIEW if errors else RecordStatus.VALID

        record = FinancialRecord(
            batch_id=batch_id,
            reference=reference,
            transaction_date=typed.get("transaction_date"),
            value_date=typed.get("value_date"),
            description=typed.get("description"),
            gross_amount=typed.get("gross_amount"),
            fee_amount=typed.get("fee_amount") if typed.get("fee_amount") is not None else 0,
            tax_amount=typed.get("tax_amount") if typed.get("tax_amount") is not None else 0,
            net_amount=typed.get("net_amount"),
            currency=typed.get("currency"),
            counterparty_name=typed.get("counterparty_name"),
            counterparty_account=typed.get("counterparty_account"),
            country=typed.get("country"),
            category=typed.get("category"),
            invoice_number=typed.get("invoice_number"),
            payment_method=typed.get("payment_method"),
            source_type=SourceType.CSV,
            source_document_name=filename,
            extraction_confidence=None,
            status=status,
            validation_errors=errors,
            raw_values=raw_kept,
        )
        records.append(record)

    return records
