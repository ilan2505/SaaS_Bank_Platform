from decimal import Decimal

from app.services.validation import check_business_rules, determine_status, parse_record_fields

VALID_ROW = {
    "reference": "TX-1",
    "transaction_date": "2026-07-01",
    "value_date": "2026-07-01",
    "description": "Management fee",
    "gross_amount": "1000.00",
    "fee_amount": "0.00",
    "tax_amount": "170.00",
    "net_amount": "1170.00",
    "currency": "EUR",
    "counterparty_name": "ABC Capital",
    "country": "LU",
    "category": "MANAGEMENT_FEE",
}


def test_valid_row_produces_no_errors():
    typed, raw_kept, parse_errors = parse_record_fields(VALID_ROW)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert errors == []
    assert raw_kept == {}


def test_invalid_date_is_reported_and_raw_value_kept():
    row = {**VALID_ROW, "transaction_date": "2026-13-16"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    assert typed["transaction_date"] is None
    assert raw_kept["transaction_date"] == "2026-13-16"
    assert any(e["field"] == "transaction_date" for e in parse_errors)


def test_unsupported_currency_is_reported():
    row = {**VALID_ROW, "currency": "JPY"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "currency" for e in errors)


def test_inconsistent_net_amount_is_reported():
    row = {**VALID_ROW, "net_amount": "1.00"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "net_amount" for e in errors)


def test_net_amount_within_tolerance_is_accepted():
    row = {**VALID_ROW, "net_amount": "1170.005"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert not any(e["field"] == "net_amount" for e in errors)


def test_zero_gross_amount_is_rejected():
    row = {**VALID_ROW, "gross_amount": "0.00", "net_amount": "0.00", "tax_amount": "0", "fee_amount": "0"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "gross_amount" for e in errors)


def test_negative_fee_is_rejected():
    row = {**VALID_ROW, "fee_amount": "-5.00"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "fee_amount" for e in errors)


def test_missing_required_field_is_reported():
    row = {**VALID_ROW, "counterparty_name": ""}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "counterparty_name" for e in errors)


def test_duplicate_reference_is_reported():
    typed, raw_kept, parse_errors = parse_record_fields(VALID_ROW)
    errors = check_business_rules(typed, parse_errors, other_references={"TX-1"})
    assert any(e["field"] == "reference" for e in errors)


def test_invalid_category_is_reported():
    row = {**VALID_ROW, "category": "NOT_A_CATEGORY"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "category" for e in errors)


def test_invalid_country_is_reported():
    row = {**VALID_ROW, "country": "Luxembourg"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    errors = check_business_rules(typed, parse_errors, other_references=set())
    assert any(e["field"] == "country" for e in errors)


def test_malformed_amount_is_reported():
    row = {**VALID_ROW, "gross_amount": "1,200.00"}
    typed, raw_kept, parse_errors = parse_record_fields(row)
    assert typed["gross_amount"] is None
    assert any(e["field"] == "gross_amount" for e in parse_errors)


def test_determine_status_valid_vs_needs_review():
    assert determine_status([], "CSV", None, 0.75) == "VALID"
    assert determine_status([{"field": "x", "message": "y"}], "CSV", None, 0.75) == "NEEDS_REVIEW"


def test_determine_status_low_pdf_confidence_forces_review():
    assert determine_status([], "PDF", Decimal("0.5"), 0.75) == "NEEDS_REVIEW"
    assert determine_status([], "PDF", Decimal("0.9"), 0.75) == "VALID"
