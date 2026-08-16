"""Orchestrates PDF -> financial_record(s) using a configured AIProvider.

Converts whatever the provider returns into validated FinancialRecord rows,
and guarantees at least one row is produced per uploaded file (a placeholder
NEEDS_REVIEW row on total failure) so the upload never silently drops a file
or crashes.
"""

import logging

from app.config import settings
from app.models import FinancialRecord, RecordStatus, SourceType
from app.services.ai_provider import AIProvider
from app.services.validation import check_business_rules, determine_status, parse_record_fields

logger = logging.getLogger(__name__)


def get_provider() -> AIProvider:
    if settings.ai_provider == "anthropic":
        from app.services.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")


def _placeholder_record(batch_id: str, filename: str, message: str) -> FinancialRecord:
    return FinancialRecord(
        batch_id=batch_id,
        source_type=SourceType.PDF,
        source_document_name=filename,
        status=RecordStatus.NEEDS_REVIEW,
        validation_errors=[{"field": "_extraction", "message": message}],
        raw_values={},
        fee_amount=0,
        tax_amount=0,
    )


def import_pdf(
    provider: AIProvider, content: bytes, filename: str, batch_id: str, existing_references: set[str]
) -> list[FinancialRecord]:
    result = provider.extract(content, filename)

    if result.error:
        logger.warning("PDF extraction failed for %s: %s", filename, result.error)
        return [_placeholder_record(batch_id, filename, f"AI extraction failed: {result.error}")]

    if not result.records:
        return [_placeholder_record(batch_id, filename, "AI provider returned no records for this document")]

    records: list[FinancialRecord] = []
    seen_references = set(existing_references)

    for raw in result.records:
        confidence = raw.get("confidence")
        typed, raw_kept, parse_errors = parse_record_fields(raw)

        errors = check_business_rules(typed, parse_errors, other_references=seen_references)
        reference = typed.get("reference")
        if reference:
            seen_references.add(reference)

        status = determine_status(
            errors, source_type="PDF", extraction_confidence=confidence,
            confidence_threshold=settings.extraction_confidence_threshold,
        )
        if status == RecordStatus.NEEDS_REVIEW and confidence is not None and float(confidence) < settings.extraction_confidence_threshold:
            errors = errors + [
                {"field": "_extraction", "message": f"Low extraction confidence ({confidence})"}
            ]

        records.append(
            FinancialRecord(
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
                source_type=SourceType.PDF,
                source_document_name=filename,
                extraction_confidence=confidence,
                status=status,
                validation_errors=errors,
                raw_values=raw_kept,
            )
        )

    return records
