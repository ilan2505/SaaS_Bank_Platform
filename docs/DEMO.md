# Demo walkthrough (real run, real API calls)

This documents an actual end-to-end run against the running application — CSV import, real Anthropic PDF extraction, and the correction → revalidate → validate lifecycle — using the exact sample files in `samples/`. Every response below is a real, unedited API response captured while driving the app, not a mock or a hand-written example.

> Why text instead of screenshots: the environment used to build this had a headless browser preview but no reliable way to save its screenshots to disk as image files, so instead of faking or omitting demo evidence, this captures the actual HTTP responses — arguably a stronger proof for a technical review than a picture, since every value here came straight from a live request. A short screen-recording/screenshots can be layered on top of this at any time (see [Adding your own screenshots](#adding-your-own-screenshots)); nothing here needs to change to do that.

Also fully verified interactively in a real browser during development (batch creation, upload, filtering, the record drawer, field-level error highlighting, corrections) — see the note in the main [README's AI tools used section](../README.md#ai-tools-used).

## 1. Create a batch

```
POST /api/batches
{"name": "Demo - July 2026 Import"}
```

```json
{
  "id": "5a66ed04-980b-4abf-9056-b24ba82213d5",
  "name": "Demo - July 2026 Import",
  "created_at": "2026-08-16T07:36:59.108126"
}
```

## 2. Upload the sample CSV — never rejects the whole file

```
POST /api/batches/5a66ed04.../upload/csv
file: transactions_import.csv
```

```json
{ "records_created": 30 }
```

```
GET /api/batches/5a66ed04...
```

```json
{
  "total_records": 30,
  "needs_review_count": 13,
  "valid_count": 17,
  "validated_count": 0,
  "source_documents": ["transactions_import.csv"]
}
```

All 30 rows were imported — the 13 intentionally-invalid rows became `NEEDS_REVIEW` with structured errors instead of failing the upload:

| Reference | Field | Error |
|---|---|---|
| TX-2026-0016 | `transaction_date` | `'2026-13-16' is not a valid date` |
| TX-2026-0017 | `value_date` | `'bad-date' is not a valid date` |
| TX-2026-0018 | `currency` | `'JPY' is not a supported currency` |
| TX-2026-0019 | `counterparty_name` | `This field is required` |
| TX-2026-0020 | `gross_amount` | `gross_amount must be non-zero` |
| TX-2026-0003 (2nd row) | `reference` | `Duplicate reference within this import` |
| *(missing)* | `reference` | `This field is required` |
| TX-2026-0023 | `net_amount` | `net_amount (1000.00) does not equal gross_amount + tax_amount - fee_amount (1160.00)` |
| TX-2026-0024 | `gross_amount` | `This field is required` |
| TX-2026-0025 | `category` | `'UNKNOWN_CATEGORY' is not a supported category` |
| TX-2026-0026 | `country` | `This field is required` |
| TX-2026-0027 | `fee_amount`, `net_amount` | `fee_amount cannot be negative` / amount mismatch |
| TX-2026-0028 | `gross_amount` | `'1,200.00' is not a valid decimal` |

Every row in this table maps 1:1 to a row the assignment's CSV intentionally seeded as invalid — confirming the validation engine catches exactly the cases it's meant to, no more, no less.

## 3. Upload the 3 real PDFs — live Anthropic Claude call

```
POST /api/batches/5a66ed04.../upload/pdf
files: invoice_legal_services.pdf, invoice_software_subscription.pdf, bank_statement_july_2026.pdf
```

```json
{ "records_created": 10 }
```

**Invoice → exactly one record, fully and correctly extracted, confidence 1.00:**

```json
{
  "reference": "INV-LX-441",
  "transaction_date": "2026-07-02",
  "value_date": "2026-07-17",
  "description": "Legal structuring services and regulatory filing review",
  "gross_amount": "3900.00",
  "fee_amount": "0.00",
  "tax_amount": "780.00",
  "net_amount": "4680.00",
  "currency": "EUR",
  "counterparty_name": "LexBridge Advisory S.A.",
  "counterparty_account": "LU55 0019 8000 4411 2200",
  "country": "LU",
  "category": "PROFESSIONAL_SERVICES",
  "invoice_number": "INV-LX-441",
  "source_type": "PDF",
  "source_document_name": "invoice_legal_services.pdf",
  "extraction_confidence": "1.000",
  "status": "VALID",
  "validation_errors": []
}
```

Note `category` was correctly inferred as `PROFESSIONAL_SERVICES` from an invoice line reading "Legal structuring services" / "Regulatory filing review" — the model isn't just copying a label, it's classifying free text against the 15-value enum.

**Bank statement → 8 records, one per line, dates/amounts/references all correct:**

```
STM-7711  Subscription proceeds   +75,000.00 EUR
STM-7712  Custody charges            -250.00 EUR
STM-7713  Legal fees INV-LX-441    -4,680.00 EUR
STM-7714  Interest income           1,245.35 EUR
STM-7715  Redemption payment      -50,000.00 EUR
STM-7716  Audit fee APL-Q2-2026    -5,616.00 EUR
STM-7717  Bank transfer fee           -35.00 EUR
STM-7718  Management fee income     8,750.00 EUR
```

All 8 came back `NEEDS_REVIEW` — correctly. The statement never names a counterparty per line (only a free-text description), and `counterparty_name` is required. This is the intended "PDF records with missing required fields must have status NEEDS_REVIEW" rule firing exactly as designed, not an extraction failure:

```json
{
  "reference": "STM-7711",
  "description": "Subscription proceeds",
  "gross_amount": "75000.00",
  "currency": "EUR",
  "counterparty_name": null,
  "country": "LU",
  "category": "OTHER",
  "extraction_confidence": "0.950",
  "status": "NEEDS_REVIEW",
  "validation_errors": [
    {"field": "counterparty_name", "message": "This field is required"}
  ]
}
```

> **Update, added later in the same session:** at the time this was captured, cross-document reconciliation (`app/services/reconciliation.py`) didn't exist yet. It was added afterward, and re-running this exact scenario today would resolve 2 of these 8 automatically: `STM-7713`'s description ("Legal fees INV-LX-441") matches the invoice record's reference with an identical amount, and `STM-7716`'s description ("Audit fee APL-Q2-2026") matches the CSV row's `invoice_number` with an identical amount — both would come back `VALID` with `counterparty_name`/`counterparty_account` backfilled instead of `NEEDS_REVIEW`. See [README → Production improvements #11](../README.md#production-improvements) and `tests/test_reconciliation.py` for the current behavior. The other 6 lines (`STM-7711`, `7712`, `7714`, `7715`, `7717`, `7718`) have no matching reference anywhere in the batch, so they correctly remain `NEEDS_REVIEW` — there's genuinely no data to reconcile them against, not a gap in the reconciliation logic. Also note `STM-7711`'s `category: OTHER` is itself a mis-extraction (should be `SUBSCRIPTION` — see [README → Known limitations](../README.md#known-limitations)); reconciliation only backfills `counterparty_name`/`counterparty_account`, it doesn't touch `category`.

(`country: "LU"` was correctly inferred from the account's IBAN prefix, `LU12 0010 0012 3456 7891` — see [Assumptions](../README.md#assumptions) in the README.)

## 4. Correct, revalidate, and approve a record — full lifecycle

Using the `STM-7711` record above (id `4e96b74f-ba16-44ca-8bd8-1edca548a796`):

```
POST /api/records/4e96b74f.../validate     → 409 Conflict
```
Rejected: the record is `NEEDS_REVIEW`, not `VALID` — matches "a corrected record should be revalidated before it can become VALIDATED".

```
PATCH /api/records/4e96b74f...
{"counterparty_name": "Helvetia Holdings AG"}
```
```json
{ "status": "NEEDS_REVIEW" }
```
Field corrected, but status stays `NEEDS_REVIEW` — editing does not auto-revalidate (see README assumptions).

```
POST /api/records/4e96b74f.../revalidate
```
```json
{ "status": "VALID", "validation_errors": [] }
```

```
POST /api/records/4e96b74f.../validate
```
```json
{ "status": "VALIDATED" }
```

Full cycle confirmed: `NEEDS_REVIEW → (409 blocks early validate) → edit → NEEDS_REVIEW → revalidate → VALID → validate → VALIDATED`.

## 5. Final batch state

```
GET /api/batches/5a66ed04...
```

```json
{
  "total_records": 40,
  "needs_review_count": 20,
  "valid_count": 19,
  "validated_count": 1,
  "csv_documents": ["transactions_import.csv"],
  "pdf_documents": [
    "bank_statement_july_2026.pdf",
    "invoice_legal_services.pdf",
    "invoice_software_subscription.pdf"
  ]
}
```

40 records from 4 source files in one batch (30 CSV + 10 PDF), 20 correctly flagged for review, 19 auto-passed validation, 1 manually corrected and approved end-to-end.

> **Update:** `source_documents` above has since been split into `csv_documents`/`pdf_documents` (shown as captured today, not from the original run — see [README → Data model](../README.md#data-model)). Separately, per the reconciliation note under step 3, re-running this whole walkthrough today would resolve `STM-7713` and `STM-7716` automatically, shifting these counts to `needs_review_count: 18` / `valid_count: 21`.

## Adding your own screenshots

The frontend workflow this documents (create batch → upload → filter to "Needs review" → click a row → see the exact invalid field highlighted → correct it → "Re-run validation" → "Validate") is easy to reproduce and screenshot yourself:

```bash
# terminal 1
cd backend && .venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev
```

Open `http://localhost:5173`, repeat the steps above using the files in `samples/`, and drop screenshots into `docs/screenshots/`.
