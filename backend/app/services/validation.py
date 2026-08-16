"""Field parsing and business-rule validation for financial_record.

This module is the single source of truth for turning loosely-typed input
(CSV cell strings, AI-extracted JSON values, or a user's edit payload) into
typed record fields, and for deciding whether a record is VALID or
NEEDS_REVIEW. It is used identically by the CSV importer, the PDF/AI
importer, and the "edit + re-run validation" endpoint so that all three
paths enforce exactly the same rules.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models import Category, Currency, PaymentMethod

REQUIRED_FIELDS = [
    "reference",
    "transaction_date",
    "description",
    "gross_amount",
    "net_amount",
    "currency",
    "counterparty_name",
    "country",
    "category",
]

DECIMAL_FIELDS = {"gross_amount", "fee_amount", "tax_amount", "net_amount"}
DATE_FIELDS = {"transaction_date", "value_date"}
STRING_FIELDS = {
    "reference",
    "description",
    "currency",
    "counterparty_name",
    "counterparty_account",
    "country",
    "category",
    "invoice_number",
    "payment_method",
}

ALL_FIELDS = DECIMAL_FIELDS | DATE_FIELDS | STRING_FIELDS

AMOUNT_TOLERANCE = Decimal("0.01")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_decimal(value: Any) -> Decimal:
    """Raises ValueError if value is non-blank but not a valid decimal."""
    return Decimal(str(value).strip())


def parse_date(value: Any) -> date:
    """Raises ValueError if value is non-blank but not a valid ISO date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def parse_record_fields(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], list[dict]]:
    """Convert a dict of loosely-typed input into typed values.

    Returns (typed_values, raw_values, parse_errors). `raw_values` retains
    the original string for any field that failed to parse, so the UI can
    show the user what was actually supplied. `typed_values` uses None for
    blank or unparsable fields.
    """
    typed: dict[str, Any] = {}
    raw_kept: dict[str, str] = {}
    errors: list[dict] = []

    for field in ALL_FIELDS:
        value = raw.get(field)
        if _is_blank(value):
            typed[field] = None
            continue

        try:
            if field in DECIMAL_FIELDS:
                typed[field] = parse_decimal(value)
            elif field in DATE_FIELDS:
                typed[field] = parse_date(value)
            else:
                typed[field] = str(value).strip()
        except (ValueError, InvalidOperation):
            typed[field] = None
            raw_kept[field] = str(value)
            kind = "date" if field in DATE_FIELDS else "decimal"
            errors.append({"field": field, "message": f"'{value}' is not a valid {kind}"})

    return typed, raw_kept, errors


def check_business_rules(
    typed: dict[str, Any],
    parse_errors: list[dict],
    other_references: set[str],
) -> list[dict]:
    """Apply Data_Dictionary validation rules on top of already-typed fields."""
    errors: list[dict] = list(parse_errors)
    fields_with_parse_error = {e["field"] for e in parse_errors}

    for field in REQUIRED_FIELDS:
        if typed.get(field) is None and field not in fields_with_parse_error:
            errors.append({"field": field, "message": "This field is required"})

    reference = typed.get("reference")
    if reference and reference in other_references:
        errors.append({"field": "reference", "message": "Duplicate reference within this import"})

    gross_amount = typed.get("gross_amount")
    if gross_amount is not None and gross_amount == 0:
        errors.append({"field": "gross_amount", "message": "gross_amount must be non-zero"})

    fee_amount = typed.get("fee_amount") or Decimal("0")
    if typed.get("fee_amount") is not None and fee_amount < 0:
        errors.append({"field": "fee_amount", "message": "fee_amount cannot be negative"})

    tax_amount = typed.get("tax_amount") or Decimal("0")
    if typed.get("tax_amount") is not None and tax_amount < 0:
        errors.append({"field": "tax_amount", "message": "tax_amount cannot be negative"})

    net_amount = typed.get("net_amount")
    if gross_amount is not None and net_amount is not None:
        expected = gross_amount + tax_amount - fee_amount
        if abs(expected - net_amount) > AMOUNT_TOLERANCE:
            errors.append(
                {
                    "field": "net_amount",
                    "message": (
                        f"net_amount ({net_amount}) does not equal gross_amount + tax_amount - "
                        f"fee_amount ({expected})"
                    ),
                }
            )

    currency = typed.get("currency")
    if currency is not None and currency not in {c.value for c in Currency}:
        errors.append({"field": "currency", "message": f"'{currency}' is not a supported currency"})

    country = typed.get("country")
    if country is not None and not COUNTRY_RE.match(country.upper()):
        errors.append({"field": "country", "message": f"'{country}' is not a valid ISO alpha-2 country code"})

    category = typed.get("category")
    if category is not None and category not in {c.value for c in Category}:
        errors.append({"field": "category", "message": f"'{category}' is not a supported category"})

    payment_method = typed.get("payment_method")
    if payment_method is not None and payment_method not in {p.value for p in PaymentMethod}:
        errors.append(
            {"field": "payment_method", "message": f"'{payment_method}' is not a supported payment method"}
        )

    return errors


def record_to_raw_dict(record) -> dict[str, Any]:
    """Re-serialize a stored record's current field values back to strings,
    so an edit payload can be merged in and the whole row re-parsed through
    the same path used at import time."""
    result: dict[str, Any] = {}
    for field in ALL_FIELDS:
        value = getattr(record, field, None)
        if value is None:
            result[field] = record.raw_values.get(field) if record.raw_values else None
        elif field in DATE_FIELDS:
            result[field] = value.isoformat()
        else:
            result[field] = str(value)
    return result


def determine_status(
    errors: list[dict],
    source_type: str,
    extraction_confidence: Decimal | None,
    confidence_threshold: float,
) -> str:
    if errors:
        return "NEEDS_REVIEW"
    if source_type == "PDF" and (extraction_confidence is None or float(extraction_confidence) < confidence_threshold):
        return "NEEDS_REVIEW"
    return "VALID"
