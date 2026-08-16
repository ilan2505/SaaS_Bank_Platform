# Financial Records Import

A small application that imports, extracts, validates, corrects and approves financial records from CSV files and PDF documents (invoices, bank statements), built for the technical assignment.

- **Backend:** Python, FastAPI, SQLAlchemy, SQLite
- **Frontend:** React (Vite)
- **AI provider:** Anthropic Claude (native PDF understanding + tool-use for structured extraction)

**→ See [`docs/DEMO.md`](docs/DEMO.md) for a full real end-to-end run** (real Anthropic API calls, real validation output) captured from live API responses — CSV import, PDF extraction on all 3 sample documents, and a full correct → revalidate → validate cycle.

## Table of contents

- [Demo walkthrough](docs/DEMO.md)
- [Setup and run](#setup-and-run)
- [Environment variables](#environment-variables)
- [Architecture and technical choices](#architecture-and-technical-choices)
- [Data model](#data-model)
- [AI provider integration](#ai-provider-integration)
- [Assumptions](#assumptions)
- [Completed / incomplete features](#completed--incomplete-features)
- [Known limitations](#known-limitations)
- [Production improvements](#production-improvements)
- [Tests](#tests)
- [Sample files](#sample-files)
- [AI tools used](#ai-tools-used)

## Setup and run

### Option A — local (no Docker)

**Backend**

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate        # Windows: .venv\Scripts\activate ; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

The API is now on `http://localhost:8000` (docs at `/docs`). Tables are created automatically on startup (SQLite file `backend/financial_records.db`).

**Frontend** (in a second terminal)

```bash
cd frontend
npm install
cp .env.example .env            # defaults to http://localhost:8000, adjust if needed
npm run dev
```

Open `http://localhost:5173`.

### Option B — Docker Compose

```bash
cp .env.example .env            # at repo root, fill in ANTHROPIC_API_KEY
docker compose up --build
```

Backend on `http://localhost:8000`, frontend on `http://localhost:5173`.

> Note: Docker Compose and the Dockerfiles were written to a standard, well-tested pattern (multi-stage Node build → nginx for the frontend, slim Python image for the backend) but Docker was not available in the environment this was built in, so this path itself was not executed end-to-end. Option A was fully run and verified, including a real Anthropic API call. If anything doesn't build cleanly, it's almost certainly a path/permission issue, not an architecture issue — happy to walk through it live.

### Running tests

```bash
cd backend
./.venv/Scripts/python.exe -m pytest -v
```

43 tests, all passing, no network calls (the AI provider is a fake test double — see [Tests](#tests)).

## Environment variables

**`backend/.env`** (see `backend/.env.example`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./financial_records.db` | SQLAlchemy URL. Swap for a `postgresql://...` URL to run on Postgres — no code changes needed. |
| `AI_PROVIDER` | `anthropic` | Selects the AI provider implementation (see [AI provider integration](#ai-provider-integration)). |
| `ANTHROPIC_API_KEY` | *(none)* | Required for real PDF extraction. Never commit this. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250929` | Model used for extraction. |
| `EXTRACTION_CONFIDENCE_THRESHOLD` | `0.75` | PDF records with AI-reported confidence below this are forced to `NEEDS_REVIEW` even if all required fields parsed successfully. |

**`frontend/.env`** (see `frontend/.env.example`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Base URL the frontend calls. |

**Root `.env`** (see `.env.example`) — only used by `docker-compose.yml`, which reads these into the backend container's environment.

## Architecture and technical choices

```
software_engineer_task/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, router wiring
│   │   ├── config.py                Settings (env vars)
│   │   ├── database.py              SQLAlchemy engine/session
│   │   ├── models.py                ORM models: ImportBatch, FinancialRecord
│   │   ├── schemas.py               Pydantic request/response models
│   │   ├── services/
│   │   │   ├── validation.py        Field parsing + business rules (single source of truth)
│   │   │   ├── csv_import.py        CSV → FinancialRecord rows
│   │   │   ├── ai_provider.py       Provider-agnostic interface
│   │   │   ├── anthropic_provider.py  Anthropic implementation
│   │   │   ├── pdf_extraction.py    Orchestrates provider → FinancialRecord rows
│   │   │   ├── reconciliation.py    Cross-document counterparty backfill (post-upload)
│   │   │   └── storage.py           Uploaded PDF persistence + retrieval
│   │   └── routers/
│   │       ├── batches.py           batch + upload endpoints
│   │       └── records.py           record + validation endpoints
│   └── tests/
├── frontend/
│   └── src/
│       ├── api.js                   Thin fetch wrapper over the backend API
│       ├── App.jsx                  Top-level state/orchestration
│       └── components/              Sidebar, UploadPanel, SummaryBar, RecordTable, RecordDrawer
├── docker-compose.yml
└── samples/                         The provided assignment files
```

**Key decisions:**

- **One validation module, four callers.** `app/services/validation.py` is the *only* place that knows what a valid `financial_record` looks like. CSV import, PDF extraction, the record-edit/revalidate endpoint, and reconciliation (after backfilling a field) all call the same `parse_record_fields` / `check_business_rules` functions. This was a deliberate choice so that "server-side validation even if the frontend validates too" isn't just true by accident — there is structurally only one rule engine, so no path can drift out of sync or duplicate logic (and a change to a business rule is a one-file change).
- **SQLite via SQLAlchemy, Postgres-ready.** All access goes through the SQLAlchemy ORM with standard, portable column types (`String`, `Date`, `Numeric`, `JSON`). Switching to Postgres is a `DATABASE_URL` change plus swapping the driver in `requirements.txt` (`psycopg2-binary` / `asyncpg`) — no query rewriting, since nothing SQLite-specific is used (the only SQLite-only line is the `check_same_thread` connect arg, which is conditional on the URL).
- **AI provider isolated behind an interface** (`ai_provider.py`). The router depends on `AIProvider` via FastAPI `Depends(get_provider)`, not on the Anthropic SDK directly — this is what lets tests substitute a `FakeProvider` and lets a second provider be added by writing one new file.
- **UUIDs as primary keys** (`str`, generated client-side) rather than auto-increment integers, so records could be created by future distributed workers (e.g. background PDF processing) without a round-trip to get an ID first.
- **Synchronous request/response, no background jobs.** PDF extraction happens inline during the upload request. This is the simplest thing that works correctly within the assignment's time box; see [Production improvements](#production-improvements) for what changes at scale.
- **Reconciliation is a full-batch re-scan on every upload, not an incremental diff.** `reconcile_batch` re-checks every record in the batch (not just the ones just uploaded) each time a CSV or PDF is uploaded, so it doesn't matter which order the invoice and the bank statement that references it arrive in — whichever arrives second resolves the match. This trades a little redundant work (batches here are small) for not having to reason about partial/one-directional backfill logic.

## Data model

Single core entity, `financial_record`, exactly as specified in the data dictionary, plus a lightweight `import_batch` parent:

**`import_batch`**: `id`, `name`, `created_at` — a batch is just a named container; its summary (counts, source file list) is computed on read from its records, not stored redundantly.

**`financial_record`**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `reference` | string | yes | unique **within an import** (checked against other records in the same batch, not globally) |
| `transaction_date` | date | yes | |
| `value_date` | date | no | |
| `description` | string | yes | |
| `gross_amount` | decimal | yes | non-zero |
| `fee_amount` | decimal | no | default 0, ≥ 0 |
| `tax_amount` | decimal | no | default 0, ≥ 0 |
| `net_amount` | decimal | yes | must equal `gross + tax - fee` (±0.01) |
| `currency` | enum | yes | EUR / USD / GBP / CHF |
| `counterparty_name` | string | yes | |
| `counterparty_account` | string | no | |
| `country` | string | yes | ISO alpha-2 |
| `category` | enum | yes | 15 supported values, see `Data_Dictionary.pdf` |
| `invoice_number` | string | no | |
| `payment_method` | enum | no | BANK_TRANSFER / DIRECT_DEBIT / CARD / INTERNAL |
| `source_type` | enum | yes | CSV / PDF |
| `source_document_name` | string | yes | original uploaded filename |
| `extraction_confidence` | decimal | PDF only | AI-reported confidence, 0–1 |
| `status` | enum | yes | NEEDS_REVIEW / VALID / VALIDATED |
| `validation_errors` | array | yes | `[{field, message}, ...]` |
| `raw_values` | object | — | *(implementation detail, not in the spec)* — original strings for any field that failed to parse (e.g. `"2026-13-16"` for a bad date), so the UI can show the user what they actually typed instead of a blank box |

**Status lifecycle:** `NEEDS_REVIEW → VALID` happens automatically whenever validation runs (import, edit+revalidate) and finds zero errors. `VALID → VALIDATED` only happens via the explicit "Validate" action, and is rejected (409) if the record isn't currently `VALID`. Editing a record always drops it back to `NEEDS_REVIEW` until it's explicitly revalidated — see [Assumptions](#assumptions).

## AI provider integration

**Provider:** Anthropic Claude (`claude-sonnet-4-5-20250929` by default), chosen because it accepts PDFs natively as a message content block (no separate OCR/text-extraction step) and supports forced tool-use, which turns "please reply with JSON" from a prompting convention into an actually-enforced response shape.

**Flow** (`services/anthropic_provider.py` + `services/pdf_extraction.py`):

1. The PDF is base64-encoded and sent as a `document` content block, alongside a text prompt describing the extraction task.
2. The request forces `tool_choice` to a single tool, `extract_financial_records`, whose JSON schema mirrors the `financial_record` fields (as strings, so the model isn't fighting decimal/date formatting) plus a `confidence` field. Claude *must* respond via that tool call — there's no free-text response to parse.
3. Each returned record dict is run through the same `parse_record_fields` / `check_business_rules` pipeline the CSV importer uses.
4. Status becomes `NEEDS_REVIEW` if there are validation errors **or** if `extraction_confidence < EXTRACTION_CONFIDENCE_THRESHOLD` (0.75 by default) — so a record can be "technically complete" but still flagged for review if the model wasn't confident.

**Error handling** (`ExtractionResult.error`, never an exception crossing into the router):
- Timeouts, connection errors, and non-2xx API responses are caught and turned into a one-line error string.
- If the model doesn't return a `tool_use` block, or `records` isn't a list, that's also captured as an error rather than raising.
- On any of the above, the upload still succeeds (HTTP 200) and **one placeholder `NEEDS_REVIEW` record is created per failed file**, with `validation_errors: [{"field": "_extraction", "message": "AI extraction failed: ..."}]`. The file is never silently dropped, and the batch/upload endpoint never 500s because of a provider problem.

**Multi-record extraction:** a supplier invoice is instructed to produce exactly one record; a bank statement is instructed to produce one record per line. This was verified against the real provider with the three sample PDFs — see the table below.

**Verified real-provider results** (not mocked — actual `ANTHROPIC_API_KEY` calls, run during development):

| File | Records | Result |
|---|---|---|
| `invoice_legal_services.pdf` | 1 | `VALID`, confidence 1.00 — all fields correctly extracted (gross 3900 EUR, tax 780, net 4680, category `PROFESSIONAL_SERVICES`) |
| `invoice_software_subscription.pdf` | 1 | `VALID`, confidence 0.95 — category correctly inferred as `SOFTWARE` from an invoice that never uses that word |
| `bank_statement_july_2026.pdf` | 8 | all 8 lines extracted with correct dates/references/signed amounts/categories; all landed in `NEEDS_REVIEW` because the statement never states a counterparty name per line — exactly the intended "missing required field → review" behavior |

**Adding a second provider:** implement `AIProvider.extract()` in a new file (e.g. `openai_provider.py`), branch on it in `get_provider()` (`pdf_extraction.py`), no other file changes.

## Assumptions

- **Reference uniqueness is scoped to the import batch**, matching "unique business reference within an import" in the data dictionary — not global across all batches ever imported.
- **Duplicate references: first occurrence wins.** When the same reference appears twice in one CSV/batch, the first row is left alone (it may well be valid) and the *second* (and any later) occurrence is flagged with a `reference` error. This matches how the sample CSV's `TX-2026-0003` duplicate is clearly meant to be caught.
- **Editing and revalidation are separate API operations, merged into one UI action.** `PATCH /records/{id}` (correct) and `POST /records/{id}/revalidate` (re-run validation) are the two distinct endpoints the assignment lists as steps 6 and 7 — both still exist independently and can be called separately (see `/docs`). Early on, the frontend exposed them as two buttons ("Save corrections" then "Re-run validation"), matching the two-step reading literally; after using it, a single flow made more sense for a human reviewer, since there's no realistic case where you'd want to save a correction *without* immediately finding out whether it's now valid. The record drawer's "Save" button now calls both in sequence (edit, then revalidate) and shows the final, revalidated status — the API still has both steps, the UI just doesn't make you click twice for something you always want to do together.
- **`country` is validated against the real ISO 3166-1 alpha-2 list** (`app/iso_countries.py`, all 249 officially assigned codes), not just a two-letter format — `"ZZ"` or `"XX"` are rejected even though they have the right shape, only actually-assigned codes like `"LU"` or `"GB"` pass.
- **Bank statement PDFs: `country` is inferred from the account's IBAN prefix** (all lines share the account's country, here `LU`), since the statement has no per-line country. `counterparty_name` is *not* guessed this way — it's left null when the statement text doesn't name one, which is what correctly drives those rows to `NEEDS_REVIEW` (see table above) rather than silently fabricating a counterparty.
- **Problem identified and solved: a bank statement line and the invoice it pays are two separate documents, so `counterparty_name` was always missing on the statement side.** `bank_statement_july_2026.pdf`'s line `STM-7713` ("Legal fees INV-LX-441", -4,680.00) is the payment for `invoice_legal_services.pdf` (`INV-LX-441`, LexBridge Advisory S.A., +4,680.00) — but each PDF is extracted independently, with no visibility into the other, so the AI has no way to know they're related. Extracting the statement alone can never fill in a name that isn't printed on it; only cross-referencing against the invoice (also in the same batch) can. Rather than leave every statement line permanently stuck in `NEEDS_REVIEW` for a fact the system could reasonably work out for itself, `app/services/reconciliation.py` now does that cross-referencing automatically: after every upload, it re-scans the whole batch for a record missing `counterparty_name` whose *description* contains another record's `reference` or `invoice_number`, with a matching amount as a safety check, and backfills `counterparty_name`/`counterparty_account` from the match — regardless of which document was uploaded first. This resolves `STM-7713` (matched against the invoice) and `STM-7716` ("Audit fee APL-Q2-2026", matched against the CSV row carrying that same `invoice_number`) automatically; see [AI provider integration](#ai-provider-integration) for why the other 6 statement lines correctly remain `NEEDS_REVIEW` — no matching document exists for them anywhere in the batch, so there's genuinely nothing to reconcile against. Deliberately **not** attempted: guessing a counterparty from the account holder's own name/IBAN printed in the statement header (`Northbridge Fund SCSp`, `LU12 0010 0012 3456 7891`) — that's *our own* account, not a counterparty, and would be constant, meaningless noise on every single line if used that way.
- **CSV numeric parsing does not "fix" malformed input** (e.g. `"1,200.00"` is left as a parse error, not auto-stripped of its thousands separator), because the sample CSV clearly places that row alongside other *intentionally* invalid rows to test error handling, not locale-aware number parsing.
- **`fee_amount`/`tax_amount` default to 0** only when the source field is genuinely blank; if present but invalid (e.g. non-numeric), it's treated as a parse error, not silently defaulted.

## Completed / incomplete features

**Completed:** all 9 workflow steps and all 9 required API endpoints from the assignment, plus batch and per-document delete endpoints and a source-document filter; CSV import (never rejects the whole file); real Anthropic PDF extraction for both invoice types and the multi-line bank statement; full server-side validation shared across both import paths; edit → revalidate → validate lifecycle with the 409 guard; batch summary; frontend covering upload, filtering (status + source + source filename), field-level error display, correction, and the record detail drawer — which for PDF-sourced records also renders the original PDF side-by-side with the extracted fields, so a reviewer can check the extraction against the source document without leaving the page; batch management (delete with confirmation, search-by-name, sort by date/name) for working with many batches at once; per-document deletion (remove one uploaded file and all the records it produced, without deleting the whole batch) with a duplicate-filename warning on re-upload; cross-document reconciliation (a record missing `counterparty_name` whose description references another same-batch record's reference/invoice_number, with a matching amount, gets it backfilled automatically after every upload, regardless of upload order); 43 passing tests; Dockerfiles + docker-compose.

**Not implemented** (all listed as optional bonus items in the assignment): authentication, pagination, background job processing (extraction is synchronous), idempotent import / duplicate-document detection, audit history for edits, multi-tenant isolation, provider fallback, cost/token usage tracking, field-level confidence display (only a record-level confidence is shown).

## Known limitations

- **No pagination** — `GET /batches/{id}/records` returns the full list. Fine at the assignment's scale (tens of records), not fine at thousands.
- **Synchronous PDF extraction** — a large multi-page bank statement or a slow provider response blocks the upload request for the duration of the API call. There's a 60s client-side timeout, but the user is stuck waiting on that request in the current UI.
- **No retry on transient AI provider failures** — a timeout produces a NEEDS_REVIEW placeholder immediately rather than retrying with backoff.
- **No authentication/authorization** — anyone with network access to the API can read/write any batch.
- **SQLite file-based concurrency** — fine for a single dev instance; concurrent writers would need Postgres (already supported by swapping `DATABASE_URL`, see above).
- **Re-upload duplicate detection is by filename, client-side only.** The frontend warns before re-uploading a filename already present in the batch, but this is a UX nudge, not a server-side guarantee: the API itself will happily accept the same file (or the same content under a different filename) twice, and each upload's rows are independently validated (only an identical `reference` would be caught as a genuine duplicate).
- **`VALID` means "passed the rules we can check mechanically," not "semantically correct."** Observed on a real run: the bank statement line `STM-7711`, description "Subscription proceeds," was extracted by Claude with `category = OTHER` instead of the obviously-better-fitting `SUBSCRIPTION` (the exact same description text, `TX-2026-0004` in the sample CSV, is correctly tagged `SUBSCRIPTION` there — so this wasn't an ambiguous case). `OTHER` is a syntactically valid enum member, so `check_business_rules` has no way to flag it — it only verifies category membership in the list, not whether it's the *right* member. Because this record also had a missing `counterparty_name`, it happened to land in `NEEDS_REVIEW` anyway and the miscategorization would very likely get caught during that review. But had every required field been present, this exact same wrong category would have produced a silent `VALID` record — nothing in the current UI singles out already-`VALID` records for a second look before someone clicks "Validate" on them. This isn't a bug to fix (no rule-based validator can verify semantic correctness — that's what the human review step is fundamentally for), but it's a real limit worth being explicit about: `VALID` is a floor, not a correctness guarantee.

## Production improvements

Roughly in priority order if this were going to production:

1. **Background job processing for PDF extraction** (e.g. a task queue) so uploads return immediately and the UI polls/streams status — the biggest UX and reliability win, and the natural place to add retry-with-backoff for transient provider errors.
2. **Postgres** instead of SQLite, plus Alembic migrations.
3. **Authentication + multi-tenant isolation** — every batch/record scoped to an org, not globally visible.
4. **Idempotent import / duplicate-document detection** — hash uploaded files, refuse or warn on exact re-upload.
5. **Audit history** — who edited which field, when, from what to what value (currently edits simply overwrite).
6. **Pagination + server-side filtering/sorting** on the records endpoint.
7. **Cost/token usage tracking** per extraction call, and a provider fallback (e.g. Anthropic → OpenAI) on repeated failures.
8. **Structured logging + tracing** around the AI call (latency, token counts, error rates) — currently just Python `logging`.
9. **Field-level confidence** from the provider (currently only record-level) to let the UI highlight exactly which extracted fields are shaky.
10. **Downstream export of `VALIDATED` records.** Today, "Validate" only flips a status flag in place — the record was already persisted at import/extraction time, and validating doesn't move it anywhere. In production, a `VALIDATED` record is the trigger for the next step in the pipeline: exporting/syncing it to the organization's actual accounting system (ERP, general ledger) or emitting an event/webhook for downstream consumers, plus stamping it with an export timestamp so it isn't re-sent. That integration is out of scope here (no target system was specified), but the status field already exists as the natural hook to build it on.
11. **Full invoice ↔ bank statement linking (beyond the counterparty backfill already implemented).** As of `app/services/reconciliation.py`, a record missing `counterparty_name` whose *description* contains another same-batch record's `reference`/`invoice_number` — with a matching amount, e.g. the bank statement's `STM-7713` line ("Legal fees INV-LX-441", -4,680) against the invoice record `INV-LX-441` (+4,680) — gets its counterparty backfilled from that match automatically, re-running after every upload so order doesn't matter (invoice-then-statement or statement-then-invoice both resolve). What this **doesn't** do: the two records still exist as fully independent rows with no stored link between them, opposite signs, and nothing stops both from being validated and both being counted in a downstream sum — so the double-counting risk described in earlier discussion is only half-solved (the missing-field annoyance is gone; the aggregation-safety problem remains). A full solution would store the match itself (e.g. a `reconciled_with_record_id` field) and either suppress one side from totals or make the link explicit in the UI.

## Tests

`backend/tests/`, 43 tests, run with `pytest` (no real network calls — the AI provider tests use a `FakeProvider` test double injected via FastAPI's dependency override, so the suite is fast and deterministic):

- `test_validation.py` — unit tests directly against the shared validation engine: valid row, invalid date, unsupported currency, inconsistent net_amount (and within-tolerance acceptance), zero/negative amounts, missing required field, duplicate reference, invalid category/country, a syntactically-valid-but-unassigned country code (`"ZZ"`) correctly rejected against the real ISO 3166-1 list, malformed (comma) amount, status transitions including low-confidence PDF forcing review.
- `test_csv_import.py` — the full provided sample CSV (asserts exactly 30 rows imported, 13 NEEDS_REVIEW / 17 VALID, matching the intentionally-invalid rows), source filename/batch association, a file that mixes one valid and one invalid row (whole file not rejected), batch summary endpoint.
- `test_correction_flow.py` — validate rejected (409) while NEEDS_REVIEW, full correct → revalidate → VALID → validate → VALIDATED cycle, revalidation that's still invalid, the record-errors endpoint.
- `test_pdf_extraction.py` — provider error/timeout doesn't crash (produces a NEEDS_REVIEW placeholder), invalid structured response handled gracefully, missing required field → NEEDS_REVIEW, low confidence forces NEEDS_REVIEW even with complete fields, a bank-statement-shaped response produces multiple records, duplicate reference across PDF-extracted records is flagged, original PDF is stored and servable via the source-file endpoint, CSV records correctly report no source file, deleting a document removes its records and its stored PDF.
- `test_csv_import.py` also covers batch deletion (removes it and cascades to its records; unknown batch → 404), filtering records by source document name, and per-document deletion (removes only that document's records; unknown document → 404).
- `test_reconciliation.py` — a statement line uploaded *after* the invoice it references is backfilled immediately; one uploaded *before* is backfilled retroactively once the invoice arrives; a CSV row's `invoice_number` reconciles a PDF statement line; an unrelated description is left alone; a reference match with a mismatched amount is correctly treated as a false positive and not linked.

The real Anthropic integration (not part of the automated suite, which must stay deterministic and offline) was verified manually against all three sample PDFs — results in the table under [AI provider integration](#ai-provider-integration).

## Sample files

Provided in `samples/`: `transactions_import.csv`, `invoice_legal_services.pdf`, `invoice_software_subscription.pdf`, `bank_statement_july_2026.pdf`, `Data_Dictionary.pdf`, `Technical_Assignment.pdf`. Upload the CSV and/or PDFs to a batch through the UI (or `POST /api/batches/{id}/upload/csv` / `/upload/pdf`) to reproduce everything described above.

## AI tools used

**Claude Code** was used for effectively the entire implementation (backend, frontend, tests, this README), driven interactively: I provided the assignment PDF, data dictionary, and sample files, and worked through the design decisions above (validation architecture, status lifecycle, provider abstraction, assumptions) as explicit choices rather than accepting defaults silently — several of the [Assumptions](#assumptions) above (duplicate-reference handling, edit-not-auto-revalidating, bank-statement country inference) were decisions I reviewed and confirmed rather than boilerplate.

**How it was verified, not just generated:**
- Every backend service module was exercised against the real sample data before moving on — the CSV importer was run against the actual `transactions_import.csv` and its output checked row-by-row against the 13 intentionally-invalid rows (`test_csv_import.py::test_full_sample_csv_import` pins this: 30 imported / 13 NEEDS_REVIEW / 17 VALID).
- The AI provider integration was **run for real** against Anthropic's API with all three sample PDFs (not just unit-tested against a fake) — see the results table above, captured directly from that run.
- The full frontend workflow (create batch → upload CSV → filter to NEEDS_REVIEW → open a record → see the exact invalid field highlighted with its message → correct it → re-run validation → see it become VALID → validate → see it become VALIDATED) was driven end-to-end in a real browser against the running backend, screenshotted at each step, not just assumed to work from the code.
- The full `pytest` suite (43 tests) passes locally.

**Parts that needed correction/redesign during the session:**
- The initial `datetime.utcnow()` usage in `models.py` triggered a deprecation warning under the installed SQLAlchemy/Python versions and was switched to `datetime.now(timezone.utc)`.
- `Settings.env_file` initially resolved `.env` relative to the process's current working directory, which broke when the backend was launched from a different working directory (surfaced concretely as `ANTHROPIC_API_KEY is not configured` errors during manual browser testing even though `backend/.env` was correctly filled in) — fixed to resolve the `.env` path relative to the config module's own location instead.
- The record-detail drawer originally refetched the *filtered* record list after a revalidate/validate action to refresh its state; when a record's status changed such that it no longer matched the active filter (e.g. NEEDS_REVIEW → VALID while filtering to "Needs review"), the drawer would silently close instead of showing the new status. Fixed to fetch the single record by ID directly, so the drawer stays open and the user can immediately continue (e.g. click "Validate" right after "Re-run validation" turns it VALID) — this was caught by actually clicking through the flow in a browser, not from reading the code.
- The initial `country` validation only checked *format* (`^[A-Z]{2}$`), which would silently accept an unassigned code like `"ZZ"` — a real gap against the data dictionary's "must be a two-letter ISO code" rule, initially shipped as a documented, deliberate scope trade-off rather than an oversight. When re-checked line-by-line against the data dictionary's rule list, it was upgraded to validate against the actual 249-code ISO 3166-1 alpha-2 list (`app/iso_countries.py`) instead of trusting the format alone.

I can walk through and explain any part of this codebase in the follow-up interview, including the reasoning behind each of the assumptions above.
