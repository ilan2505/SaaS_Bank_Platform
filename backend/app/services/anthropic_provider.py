"""Anthropic Claude implementation of AIProvider.

Uses Claude's native PDF understanding (the PDF is sent as a base64 document
content block) combined with forced tool-use so the model's reply is
constrained to a JSON schema instead of free-form text. This avoids the
usual "parse JSON out of a markdown code fence" fragility.
"""

import base64
import logging

import anthropic

from app.config import settings
from app.models import Category, Currency, PaymentMethod
from app.services.ai_provider import AIProvider, ExtractionResult

logger = logging.getLogger(__name__)

_RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "reference": {
            "type": ["string", "null"],
            "description": (
                "Unique business reference for this record: the invoice number for a "
                "supplier invoice, or the statement line reference for a bank statement line."
            ),
        },
        "transaction_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD. Invoice date, or statement line date."},
        "value_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD. Due date, or statement value date, if present."},
        "description": {"type": ["string", "null"], "description": "Human-readable description of the transaction/invoice."},
        "gross_amount": {"type": ["string", "null"], "description": "Amount before fees and tax, as a plain decimal string, e.g. '1234.56'. For a bank statement line with no separate tax/fee, equal to the line amount. Negative for outgoing amounts if the statement shows them negative."},
        "fee_amount": {"type": ["string", "null"], "description": "Fees charged, decimal string, defaults to 0."},
        "tax_amount": {"type": ["string", "null"], "description": "Tax/VAT amount, decimal string, defaults to 0."},
        "net_amount": {"type": ["string", "null"], "description": "gross_amount + tax_amount - fee_amount, decimal string."},
        "currency": {"type": ["string", "null"], "enum": [c.value for c in Currency] + [None]},
        "counterparty_name": {"type": ["string", "null"], "description": "Supplier, customer, bank or investor name. Best-effort from context if not explicitly labelled."},
        "counterparty_account": {"type": ["string", "null"], "description": "IBAN or other account identifier, if present."},
        "country": {"type": ["string", "null"], "description": "ISO alpha-2 country code, e.g. 'LU'. Infer from IBAN prefix or supplier address if not explicit."},
        "category": {"type": ["string", "null"], "enum": [c.value for c in Category] + [None]},
        "invoice_number": {"type": ["string", "null"]},
        "payment_method": {"type": ["string", "null"], "enum": [p.value for p in PaymentMethod] + [None]},
        "confidence": {
            "type": "number",
            "description": "0 to 1: how confident you are that every required field above was correctly extracted and is present.",
        },
    },
    "required": ["confidence"],
}

_TOOL = {
    "name": "extract_financial_records",
    "description": (
        "Report the financial record(s) found in the document. A supplier invoice "
        "produces exactly one record. A bank statement produces one record per "
        "transaction line."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"records": {"type": "array", "items": _RECORD_SCHEMA}},
        "required": ["records"],
    },
}

_PROMPT = """You are extracting structured financial data from a PDF for an import pipeline.

The target schema per record is described by the extract_financial_records tool.

Rules:
- If this document is a supplier/customer invoice, produce exactly one record from it.
- If this document is a bank/account statement, produce one record per transaction line.
- Use the invoice's subtotal (pre-tax) as gross_amount, tax as tax_amount, fee_amount 0 unless a
  separate fee line is shown, and the invoice total as net_amount.
- For bank statement lines, gross_amount = net_amount = the line amount, fee_amount = tax_amount = 0,
  unless the description clearly indicates otherwise.
- Choose the single best-fitting category from the allowed enum, based on the description.
- country: infer from the IBAN country prefix of the relevant account when not stated explicitly.
- Never invent a reference, amount or date you cannot find or reasonably infer; leave it null instead.
- Set confidence honestly: lower it whenever you had to guess or a required field is missing.

Call the extract_financial_records tool with your result. Do not include any other text."""


class AnthropicProvider(AIProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0)

    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        if not settings.anthropic_api_key:
            return ExtractionResult(error="ANTHROPIC_API_KEY is not configured on the server")

        try:
            encoded = base64.standard_b64encode(pdf_bytes).decode("utf-8")
            message = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                tools=[_TOOL],
                tool_choice={"type": "tool", "name": "extract_financial_records"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": encoded,
                                },
                            },
                            {"type": "text", "text": _PROMPT},
                        ],
                    }
                ],
            )
        except anthropic.APITimeoutError:
            logger.exception("Anthropic extraction timed out for %s", filename)
            return ExtractionResult(error="AI provider request timed out")
        except anthropic.APIStatusError as exc:
            logger.exception("Anthropic API error for %s", filename)
            return ExtractionResult(error=f"AI provider returned an error: {exc.status_code}")
        except anthropic.APIConnectionError:
            logger.exception("Anthropic connection error for %s", filename)
            return ExtractionResult(error="Could not reach AI provider")
        except Exception as exc:  # noqa: BLE001 - last-resort guard, must never crash the upload
            logger.exception("Unexpected error calling Anthropic for %s", filename)
            return ExtractionResult(error=f"Unexpected AI provider error: {exc}")

        tool_use = next((block for block in message.content if block.type == "tool_use"), None)
        if tool_use is None:
            return ExtractionResult(error="AI provider did not return structured output")

        try:
            records = tool_use.input.get("records", [])
            if not isinstance(records, list):
                raise ValueError("'records' is not a list")
        except (AttributeError, ValueError) as exc:
            logger.exception("Malformed tool_use payload for %s", filename)
            return ExtractionResult(error=f"Invalid structured response from AI provider: {exc}")

        return ExtractionResult(records=records)
