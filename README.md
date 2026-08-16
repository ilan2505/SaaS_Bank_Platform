# Financial Records Import

[![Tests](https://github.com/ilan2505/SaaS_Bank_Platform/actions/workflows/tests.yml/badge.svg)](https://github.com/ilan2505/SaaS_Bank_Platform/actions/workflows/tests.yml)

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
- [Code walkthrough — what each file does](#code-walkthrough--what-each-file-does)
- [Data model](#data-model)
- [AI provider integration](#ai-provider-integration)
- [Assumptions](#assumptions)
- [Completed / incomplete features](#completed--incomplete-features)
- [Known limitations](#known-limitations)
- [Security basics](#security-basics)
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

60 tests, all passing, no network calls (the AI provider is a fake test double — see [Tests](#tests)).

### Whenever the schema changes

Because this is SQLite with `Base.metadata.create_all()` (not a migration tool — see [Production improvements](#production-improvements)), a new column or table only appears on a **fresh** database file. If you pull a change that touches `models.py`, delete `backend/financial_records.db` before restarting the server — it's recreated automatically, empty, with the new schema.

## Environment variables

**`backend/.env`** (see `backend/.env.example`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./financial_records.db` | SQLAlchemy URL. Swap for a `postgresql://...` URL to run on Postgres — no code changes needed. |
| `AI_PROVIDER` | `anthropic` | Selects the AI provider implementation (see [AI provider integration](#ai-provider-integration)). |
| `ANTHROPIC_API_KEY` | *(none)* | Required for real PDF extraction. Never commit this. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250929` | Model used for extraction. |
| `EXTRACTION_CONFIDENCE_THRESHOLD` | `0.75` | PDF records with AI-reported confidence below this are forced to `NEEDS_REVIEW` even if all required fields parsed successfully. |
| `MAX_UPLOAD_MB` | `20` | Per-file upload size limit (CSV or PDF), enforced before the file is processed or sent to the AI provider. Raise this if you expect large scanned/image-based bank statement PDFs. |

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
│   │   ├── main.py                    FastAPI app, CORS, router wiring
│   │   ├── config.py                  Settings (env vars)
│   │   ├── database.py                SQLAlchemy engine/session
│   │   ├── models.py                  ORM models: ImportBatch, FinancialRecord, RecordEditHistory
│   │   ├── schemas.py                 Pydantic request/response models
│   │   ├── upload_guards.py           Upload size limit + PDF signature check
│   │   ├── iso_countries.py           ISO 3166-1 alpha-2 code list
│   │   ├── services/
│   │   │   ├── validation.py          Field parsing + business rules (single source of truth)
│   │   │   ├── csv_import.py          CSV → FinancialRecord rows
│   │   │   ├── ai_provider.py         Provider-agnostic interface
│   │   │   ├── anthropic_provider.py  Anthropic implementation
│   │   │   ├── pdf_extraction.py      Orchestrates provider → FinancialRecord rows
│   │   │   ├── reconciliation.py      Cross-document counterparty backfill (post-upload)
│   │   │   ├── audit.py               Field-change snapshot/diff → RecordEditHistory
│   │   │   └── storage.py             Uploaded PDF persistence, retrieval + content hashing
│   │   └── routers/
│   │       ├── batches.py             Batch + upload endpoints
│   │       └── records.py             Record + validation endpoints
│   └── tests/                         28 files → 60 tests, see Tests
├── frontend/
│   └── src/
│       ├── main.jsx                   React entry point
│       ├── App.jsx                    Top-level state/orchestration
│       ├── api.js                     Thin fetch wrapper over the backend API
│       ├── constants.js               Field metadata + enum value lists
│       ├── index.css                  All styling
│       └── components/                Sidebar, UploadPanel, AnalyticsPanel, RecordTable, RecordDrawer
├── docker-compose.yml
├── docs/DEMO.md                       Real captured end-to-end run
└── samples/                           The provided assignment files
```

**Key decisions:**

- **One validation module, four callers.** `app/services/validation.py` is the *only* place that knows what a valid `financial_record` looks like. CSV import, PDF extraction, the record-edit/revalidate endpoint, and reconciliation (after backfilling a field) all call the same `parse_record_fields` / `check_business_rules` functions. This was a deliberate choice so that "server-side validation even if the frontend validates too" isn't just true by accident — there is structurally only one rule engine, so no path can drift out of sync or duplicate logic (and a change to a business rule is a one-file change).
- **SQLite via SQLAlchemy, Postgres-ready.** All access goes through the SQLAlchemy ORM with standard, portable column types (`String`, `Date`, `Numeric`, `JSON`). Switching to Postgres is a `DATABASE_URL` change plus swapping the driver in `requirements.txt` (`psycopg2-binary` / `asyncpg`) — no query rewriting, since nothing SQLite-specific is used (the only SQLite-only line is the `check_same_thread` connect arg, which is conditional on the URL).
- **AI provider isolated behind an interface** (`ai_provider.py`). The router depends on `AIProvider` via FastAPI `Depends(get_provider)`, not on the Anthropic SDK directly — this is what lets tests substitute a `FakeProvider` and lets a second provider be added by writing one new file.
- **UUIDs as primary keys** (`str`, generated client-side) rather than auto-increment integers, so records could be created by future distributed workers (e.g. background PDF processing) without a round-trip to get an ID first.
- **Synchronous request/response, no background jobs.** PDF extraction happens inline during the upload request. This is the simplest thing that works correctly within the assignment's time box; see [Production improvements](#production-improvements) for what changes at scale.
- **Reconciliation is a full-batch re-scan on every upload, not an incremental diff.** `reconcile_batch` re-checks every record in the batch (not just the ones just uploaded) each time a CSV or PDF is uploaded, so it doesn't matter which order the invoice and the bank statement that references it arrive in — whichever arrives second resolves the match. This trades a little redundant work (batches here are small) for not having to reason about partial/one-directional backfill logic.
- **Duplicate detection is content-based (SHA-256), not filename-based.** A file renamed and re-uploaded is still caught; a genuinely different file that happens to share a name is not falsely blocked. It's a hard 409 rather than a soft warning, unlike the frontend's filename-based nudge (see [Known limitations](#known-limitations)) — there's no legitimate reason to re-upload byte-identical content, so there's nothing to ask the user to confirm.
- **Audit history tracks *what* changed, not *who*.** `record_edit_history` logs field/old-value/new-value/source/timestamp for every real change (manual edit or automatic reconciliation), reusing the same snapshot-before/compare-after helper (`services/audit.py`) from both call sites so the two paths can't drift apart. There's no `user_id` column because there's no authentication anywhere in this system to attribute a change to — see [Production improvements](#production-improvements).

## Code walkthrough — what each file does

The tree above says *where* things live; this says what each file is actually responsible for. Read top-to-bottom and you've read the whole backend.

### Backend — entry points & config

| File | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI app, runs `Base.metadata.create_all()` on startup (so a fresh SQLite file gets its schema automatically), adds the CORS middleware, mounts the `batches` and `records` routers, and exposes `GET /api/health`. |
| `app/config.py` | The single `Settings` object (pydantic-settings) every other file imports for configuration — never `os.environ` directly. Resolves `.env` by an **absolute path** relative to this file, not the process's working directory, so it doesn't matter where `uvicorn` is launched from (this was an actual bug fixed during the session — see [AI tools used](#ai-tools-used)). |
| `app/database.py` | The SQLAlchemy `engine`, the `SessionLocal` session factory, the `Base` declarative class every model inherits from, and `get_db()` — the FastAPI dependency that hands each request its own session and always closes it. |

### Backend — data layer

| File | Responsibility |
|---|---|
| `app/models.py` | The three ORM tables — `ImportBatch`, `FinancialRecord` (the core entity from the data dictionary, plus three implementation-only columns: `raw_values`, `source_document_path`, `source_document_hash`), and `RecordEditHistory` (the audit trail) — plus the five enums (`SourceType`, `RecordStatus`, `Currency`, `Category`, `PaymentMethod`) shared between the DB columns, the validation rules, and the AI extraction schema. |
| `app/schemas.py` | The Pydantic models FastAPI actually serializes to JSON: `BatchCreate`, `BatchOut`, `BatchSummary`, `RecordOut`, `RecordUpdate`, `UploadResult`, `ValidationError`, `EditHistoryOut`. Kept separate from `models.py` on purpose — the API's shape (e.g. the computed `has_source_file` boolean) doesn't have to be identical to the storage shape. |
| `app/iso_countries.py` | The 249 official ISO 3166-1 alpha-2 codes as a `frozenset`. Imported only by `validation.py`. |

### Backend — business logic (`app/services/`)

| File | Responsibility |
|---|---|
| `validation.py` | **The single source of truth.** `parse_record_fields()` turns loosely-typed input (a CSV cell, an AI-returned JSON value, an edit payload) into typed values, keeping the original string when something fails to parse. `check_business_rules()` applies every Data Dictionary rule (required fields, amount math, currency/category/country membership, duplicate reference). `determine_status()` decides `NEEDS_REVIEW` vs `VALID`. `record_to_raw_dict()` re-serializes an already-stored record back into strings so it can be re-parsed — used by both the revalidate endpoint and the edit endpoint's merge step. |
| `csv_import.py` | `import_csv()`: reads a CSV row by row and runs each row through `validation.py`, independently — one bad row never rejects the file. |
| `ai_provider.py` | The `AIProvider` abstract base class and the `ExtractionResult` dataclass. This is the seam: nothing outside this file and `anthropic_provider.py` knows which AI vendor is in use. |
| `anthropic_provider.py` | The concrete Claude implementation. Builds the forced tool-use request (PDF as a base64 `document` content block + a JSON-schema tool the model must call), and converts every provider-side failure (timeout, API error, connection error, malformed/missing tool response) into an `ExtractionResult.error` string — it never lets an exception escape to the router. |
| `pdf_extraction.py` | `get_provider()` (the factory FastAPI injects via `Depends`) and `import_pdf()`, which calls the provider and turns its output — or its error, via a placeholder `NEEDS_REVIEW` record — into `FinancialRecord` objects, through the same `validation.py` pipeline `csv_import.py` uses. |
| `reconciliation.py` | `reconcile_batch()`, called after every upload: finds records missing `counterparty_name` whose *description* contains another same-batch record's reference/invoice_number (with a matching amount as a safety check), backfills the counterparty from that match, and revalidates the changed record. |
| `audit.py` | `snapshot()` and `log_changes()` — the snapshot-before/diff-after helper shared by the manual-edit endpoint and `reconciliation.py`, so a user correction and an automatic backfill write to `RecordEditHistory` through identical logic. |
| `storage.py` | Everything to do with an uploaded PDF's bytes on disk: `save_pdf()` (write under `backend/uploads/{batch_id}/`), `resolve()` (stored path → `Path`), `delete_batch_uploads()` (cleanup on batch delete), `hash_content()` (SHA-256, for duplicate detection). |

### Backend — API (`app/routers/`)

| File | Endpoints |
|---|---|
| `batches.py` | `POST /batches`, `GET /batches`, `DELETE /batches/{id}`, `DELETE /batches/{id}/documents`, `GET /batches/{id}`, `GET /batches/{id}/records`, `POST /batches/{id}/upload/csv`, `POST /batches/{id}/upload/pdf`. Also `_summarize()` (records → `BatchSummary`) and `_find_duplicate_document()` (the content-hash lookup). |
| `records.py` | `GET /records/{id}`, `GET /records/{id}/errors`, `GET /records/{id}/source-file`, `GET /records/{id}/history`, `PATCH /records/{id}`, `POST /records/{id}/revalidate`, `POST /records/{id}/validate`. |

`backend/tests/` — one file per concern; see [Tests](#tests) for exactly what each one asserts.

### Frontend (`frontend/src/`)

| File | Responsibility |
|---|---|
| `main.jsx` | React entry point — mounts `<App />`. |
| `App.jsx` | All top-level state: which batch is selected, the active filters, the filtered record list (for the table) *and* a separate unfiltered one (for `AnalyticsPanel`, which always reflects the whole batch), and the handlers that wire the child components together (create/delete batch, upload, "something changed, refetch"). |
| `api.js` | The **only** file that calls `fetch()`. One function per backend endpoint, plus a shared `handle()` that turns any non-2xx response into a thrown `Error` carrying the backend's `detail` message — every component just `catch`es and shows `err.message`. |
| `constants.js` | `EDITABLE_FIELDS` (label, input type, select options — drives the record drawer's form generically) and the enum value lists (`CURRENCIES`, `CATEGORIES`, `PAYMENT_METHODS`), kept in sync with the backend's enums by hand (see [Known limitations](#known-limitations)). |
| `index.css` | All styling for the app — plain CSS, no framework, no CSS-in-JS, roughly ordered top-to-bottom the way components appear on screen. |
| `components/Sidebar.jsx` | Batch list: create form, search box, date/A–Z sort toggle, per-batch delete button. |
| `components/UploadPanel.jsx` | The single file picker + Upload button (custom-styled to avoid the browser's localized native text), the client-side duplicate-filename warning before upload, and the "Uploaded files" list (PDF/CSV, each individually deletable) below it. |
| `components/AnalyticsPanel.jsx` | The two charts (status breakdown, volume by category) — computed client-side from the batch's full unfiltered record list, so they don't change when the table's filters do. |
| `components/RecordTable.jsx` | The filtered record list, one row per record, click to open the drawer. |
| `components/RecordDrawer.jsx` | The record detail/edit panel: the original-PDF preview (PDF-sourced records only), the editable field grid with inline validation errors, the collapsible edit-history section, and the Save/Validate actions. |

## Data model

Single core entity, `financial_record`, exactly as specified in the data dictionary, plus a lightweight `import_batch` parent and an audit table:

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
| `source_document_path` | string | — | *(implementation detail)* PDF only — where the original file is stored on disk, so it can be re-served for the drawer's PDF preview |
| `source_document_hash` | string | — | *(implementation detail)* SHA-256 of the uploaded file's bytes, used only for duplicate-content detection at upload time — not otherwise exposed via the API |

**Status lifecycle:** `NEEDS_REVIEW → VALID` happens automatically whenever validation runs (import, edit+revalidate) and finds zero errors. `VALID → VALIDATED` only happens via the explicit "Validate" action, and is rejected (409) if the record isn't currently `VALID`. Editing a record always drops it back to `NEEDS_REVIEW` until it's explicitly revalidated — see [Assumptions](#assumptions).

**`record_edit_history`** *(implementation detail, not in the spec — added for the "audit history" optional bonus item)*: `id`, `record_id`, `field`, `old_value`, `new_value`, `source` (`"edit"` or `"reconciliation"`), `edited_at`. One row per field that actually changed value (a no-op save creates nothing); cascade-deleted with its parent record. No `user_id`/attribution column, since there's no auth/user concept anywhere in this system — see [Production improvements](#production-improvements).

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

**Reference & duplicate handling**
- **Reference uniqueness is scoped to the import batch**, matching "unique business reference within an import" in the data dictionary — not global across all batches ever imported.
- **Duplicate references: first occurrence wins.** When the same reference appears twice in one CSV/batch, the first row is left alone (it may well be valid) and the *second* (and any later) occurrence is flagged with a `reference` error. This matches how the sample CSV's `TX-2026-0003` duplicate is clearly meant to be caught.
- **Duplicate-content detection is hard-rejected (409), not just flagged.** Uploading a file whose bytes exactly match one already in the batch — same content under any filename, or the same file selected twice in one multi-file upload — is refused outright rather than imported and marked `NEEDS_REVIEW`. Unlike a data-quality problem (which the review workflow exists to surface and let a human resolve), an exact re-upload has no legitimate resolution other than "don't do that," so there's nothing for a reviewer to correct.

**Correction workflow**
- **Editing and revalidation are separate API operations, merged into one UI action.** `PATCH /records/{id}` (correct) and `POST /records/{id}/revalidate` (re-run validation) are the two distinct endpoints the assignment lists as steps 6 and 7 — both still exist independently and can be called separately (see `/docs`). Early on, the frontend exposed them as two buttons, matching the two-step reading literally; after using it, a single flow made more sense, since there's no realistic case where you'd want to save a correction *without* immediately finding out whether it's now valid. The record drawer's "Save" button now calls both in sequence and shows the final, revalidated status.

**`country` validation**
- **Validated against the real ISO 3166-1 alpha-2 list** (`app/iso_countries.py`, all 249 officially assigned codes), not just a two-letter format — `"ZZ"` or `"XX"` are rejected even though they have the right shape, only actually-assigned codes like `"LU"` or `"GB"` pass.
- **Bank statement PDFs: `country` is inferred from the account's IBAN prefix** (all lines share the account's country, here `LU`), since the statement has no per-line country. `counterparty_name` is *not* guessed this way — it's left null when the statement text doesn't name one, which is what correctly drives those rows to `NEEDS_REVIEW` (see the AI provider table above) rather than silently fabricating a counterparty.

**Cross-document reconciliation** — a problem identified and solved mid-session, worth spelling out:
- **The problem:** a bank statement line and the invoice it pays are two separate documents, extracted independently, with no visibility into each other — so `counterparty_name` was structurally unfillable on the statement side. Example: `bank_statement_july_2026.pdf`'s line `STM-7713` ("Legal fees INV-LX-441", -4,680.00) is the payment for `invoice_legal_services.pdf` (`INV-LX-441`, LexBridge Advisory S.A., +4,680.00), but the AI extracting the statement has no way to know that.
- **The fix:** `app/services/reconciliation.py` re-scans the whole batch after every upload for a record missing `counterparty_name` whose *description* contains another record's `reference` or `invoice_number`, with a matching amount as a safety check, and backfills from the match — regardless of which document was uploaded first. This resolves `STM-7713` (matched against the invoice) and `STM-7716` ("Audit fee APL-Q2-2026", matched against the CSV row carrying that same `invoice_number`) automatically.
- **What's deliberately *not* attempted:** guessing a counterparty from the account holder's own name/IBAN printed in the statement header (`Northbridge Fund SCSp`, `LU12 0010 0012 3456 7891`) — that's *our own* account, not a counterparty, and would be constant, meaningless noise on every line if used that way. The other 6 statement lines correctly remain `NEEDS_REVIEW`: no matching document exists for them anywhere in the batch, so there's genuinely nothing to reconcile against.

**CSV parsing**
- **Numeric parsing does not "fix" malformed input** (e.g. `"1,200.00"` is left as a parse error, not auto-stripped of its thousands separator), because the sample CSV clearly places that row alongside other *intentionally* invalid rows to test error handling, not locale-aware number parsing.
- **`fee_amount`/`tax_amount` default to 0** only when the source field is genuinely blank; if present but invalid (e.g. non-numeric), it's treated as a parse error, not silently defaulted.

## Completed / incomplete features

**Completed:**

- All 9 workflow steps and all 9 required API endpoints from the assignment, plus batch/document delete, a source-document filter, and an edit-history endpoint.
- CSV import that never rejects the whole file; real Anthropic PDF extraction for both invoice types and the multi-line bank statement.
- Full server-side validation shared across every write path (CSV, PDF, edit, reconciliation) via one module.
- Edit → revalidate → validate lifecycle with the 409 guard; batch summary.
- Frontend covering upload, filtering (status + source + source filename), field-level error display, correction, and a record detail drawer that renders the original PDF side-by-side with the extracted fields for PDF-sourced records.
- Batch management (delete with confirmation, search-by-name, sort by date/name); per-document deletion (remove one uploaded file and all the records it produced, without deleting the whole batch).
- **Duplicate-document detection** (optional bonus item, implemented): every upload is hashed (SHA-256) and rejected with a 409 if byte-identical content already exists in the batch — catches the same file under a different name, and duplicates within one multi-file PDF upload, not just an exact filename match.
- **Audit history** (optional bonus item, implemented): every field that actually changes value — through a manual correction or an automatic reconciliation backfill — is logged with its old value, new value, source, and timestamp, retrievable via `GET /records/{id}/history` and shown in the record drawer.
- Cross-document reconciliation: a record missing `counterparty_name` whose description references another same-batch record's reference/invoice_number, with a matching amount, gets it backfilled automatically after every upload, regardless of upload order.
- **Analytics panel** (not in the assignment at all — added beyond spec): a status breakdown (stacked bar) and total volume by category (horizontal bar, sorted descending, restricted to the 15 recognized categories) for the whole batch, independent of the active table filters. Volume is deliberately labeled "absolute," not "spend" or "income" — this sample data mixes invoice-style amounts (recorded at face value) with bank-statement-style amounts (recorded as signed cash flow) for the same real payment (see the `INV-LX-441` / `STM-7713` example under [Assumptions](#assumptions)), so the sign alone can't be trusted to mean expense vs. income without per-category business logic no one asked for here.
- 60 passing tests, run automatically on every push via GitHub Actions (`.github/workflows/tests.yml` — badge above); Dockerfiles + docker-compose.

**Not implemented** (all listed as optional bonus items in the assignment): authentication, pagination, background job processing (extraction is synchronous), multi-tenant isolation, provider fallback, cost/token usage tracking, field-level confidence display (only a record-level confidence is shown), deployment.

## Known limitations

- **No pagination** — `GET /batches/{id}/records` returns the full list. Fine at the assignment's scale (tens of records), not fine at thousands.
- **Synchronous PDF extraction** — a large multi-page bank statement or a slow provider response blocks the upload request for the duration of the API call. There's a 60s client-side timeout, but the user is stuck waiting on that request in the current UI.
- **No retry on transient AI provider failures** — a timeout produces a NEEDS_REVIEW placeholder immediately rather than retrying with backoff.
- **SQLite file-based concurrency** — fine for a single dev instance; concurrent writers would need Postgres (already supported by swapping `DATABASE_URL`, see above).
- **Duplicate-content detection is per-batch, not global.** The SHA-256 hash check (see [Assumptions](#assumptions)) only compares against documents already in *this* batch — uploading the exact same file into two different batches is allowed and not flagged, since a batch is the unit of "one import," not the whole system. The frontend also still has its separate, softer filename-based warning (client-side, skippable) as a first line of defense before the request even reaches the server.
- **`VALID` means "passed the rules we can check mechanically," not "semantically correct."** Real example: the bank statement line `STM-7711`, description "Subscription proceeds," was extracted by Claude with `category = OTHER` instead of the obviously-better-fitting `SUBSCRIPTION` — the exact same description text (`TX-2026-0004` in the sample CSV) is correctly tagged `SUBSCRIPTION` elsewhere, so this wasn't an ambiguous case. `OTHER` is a syntactically valid enum member, so `check_business_rules` has no way to flag it — it only verifies category membership, not whether it's the *right* member. This record also had a missing `counterparty_name`, so it landed in `NEEDS_REVIEW` anyway; but had every required field been present, this same wrong category would have produced a silent `VALID` record, and nothing in the current UI singles out already-`VALID` records for a second look before "Validate." Not a bug to fix (no rule-based validator can verify semantic correctness — that's what human review is for) — just a limit worth being explicit about: `VALID` is a floor, not a correctness guarantee.
- **Frontend enums are hand-duplicated from the backend.** `frontend/src/constants.js`'s `CATEGORIES`/`CURRENCIES`/`PAYMENT_METHODS` mirror `backend/app/models.py`'s enums by copy-paste, not by any shared source. Adding a 16th category means editing both files; forgetting the frontend one wouldn't break validation (the backend still enforces the real list) but would let the drawer's dropdown silently omit a valid option.

## Security basics

**In place:**
- **No raw SQL anywhere.** Every query goes through the SQLAlchemy ORM with bound parameters — there's no string-built SQL for user input (batch names, filenames, filter values, edited field values) to inject into.
- **CORS restricted to known origins** (`app/config.py`'s `cors_origins`, defaulting to the local dev frontend ports) — not `allow_origins=["*"]`.
- **API keys never committed and never logged.** `ANTHROPIC_API_KEY` is read from an environment variable, `.env` is gitignored (verified: `git grep` across the full history finds no API key in this repo), and the Anthropic error-handling paths (`anthropic_provider.py`) log the SDK's own status/message via `logger.exception`, never the request itself — the key is never part of what gets logged.
- **Uploads are validated by content, not just by trusting the client.** `app/upload_guards.py`: every CSV/PDF upload is capped at `MAX_UPLOAD_MB` (20MB by default, configurable — see [Environment variables](#environment-variables)) before it's processed or handed to the AI provider, and every PDF is checked for the actual `%PDF-` file signature in its bytes, not just a `.pdf` string in the filename — a file renamed to end in `.pdf` without being one is rejected with a 400 before it's saved to disk or sent to the AI provider.
- **The uploaded-PDF-serving endpoint only serves what it stored.** `GET /records/{id}/source-file` resolves a path stored server-side against a fixed `uploads/` root (`app/services/storage.py`) — the client never supplies a filesystem path, so there's no path-traversal surface there.

**Explicitly not covered** (all listed as optional bonus items in the assignment, not required, but worth being upfront about rather than silent):
- **No authentication/authorization** — anyone with network access to the API can read, write, or delete any batch. There's no user/tenant concept at all.
- **No rate limiting** — nothing stops one client from hammering the upload endpoint (each PDF upload is a paid Anthropic API call, so this is also a cost-control gap, not just an availability one).
- **No malware/content scanning of uploaded files** beyond the PDF signature check above — a well-formed PDF with malicious embedded content would pass through untouched.
- **No encryption at rest** — the SQLite file and stored PDFs sit as plain files on disk; fine for a local dev instance, not for a real deployment handling real financial documents.
- **No CSRF protection** — not applicable to the current design (no cookies/sessions; the API is fully stateless and unauthenticated), but would need addressing the moment any session-based auth is added.

## Production improvements

Roughly in priority order if this were going to production:

1. **Background job processing for PDF extraction** (e.g. a task queue) so uploads return immediately and the UI polls/streams status — the biggest UX and reliability win, and the natural place to add retry-with-backoff for transient provider errors.
2. **Postgres** instead of SQLite, plus Alembic migrations.
3. **Authentication + multi-tenant isolation** — every batch/record scoped to an org, not globally visible.
4. **Pagination + server-side filtering/sorting** on the records endpoint.
5. **Cost/token usage tracking** per extraction call, and a provider fallback (e.g. Anthropic → OpenAI) on repeated failures.
6. **Structured logging + tracing** around the AI call (latency, token counts, error rates) — currently just Python `logging`.
7. **Field-level confidence** from the provider (currently only record-level) to let the UI highlight exactly which extracted fields are shaky.
8. **Downstream export of `VALIDATED` records.** Today, "Validate" only flips a status flag in place — the record was already persisted at import/extraction time, and validating doesn't move it anywhere. In production, a `VALIDATED` record is the trigger for the next step in the pipeline: exporting/syncing it to the organization's actual accounting system (ERP, general ledger) or emitting an event/webhook for downstream consumers, plus stamping it with an export timestamp so it isn't re-sent. That integration is out of scope here (no target system was specified), but the status field already exists as the natural hook to build it on.
9. **Attribution ("who") on audit history.** `record_edit_history` captures *what* changed, *from what*, *to what*, *when*, and *how* (manual edit vs. automatic reconciliation) — but not *who*, since there's no user/auth concept in this system at all. Real attribution needs the authentication layer from point 3 first; the history table is already shaped to add a `user_id` column to once that exists.
10. **Full invoice ↔ bank statement linking**, beyond the counterparty backfill already implemented. Today, reconciliation fills in a missing `counterparty_name`/`counterparty_account`, but the two records (e.g. the invoice `INV-LX-441` and the statement line `STM-7713`) still exist as fully independent rows with no stored link between them and opposite signs — nothing stops both from being validated and both being counted in a downstream sum. A full solution would store the match itself (e.g. a `reconciled_with_record_id` field) and either suppress one side from totals or make the link explicit in the UI.
11. **Shared enum source between frontend and backend** (see [Known limitations](#known-limitations)) — e.g. generate `constants.js`'s value lists from the OpenAPI schema FastAPI already produces, instead of hand-copying them.

## Tests

`backend/tests/`, 60 tests, run with `pytest` (no real network calls — the AI provider tests use a `FakeProvider` test double injected via FastAPI's dependency override, so the suite is fast and deterministic):

- `test_validation.py` — unit tests directly against the shared validation engine: valid row, invalid date, unsupported currency, inconsistent net_amount (and within-tolerance acceptance), zero/negative amounts, missing required field, duplicate reference, invalid category/country, a syntactically-valid-but-unassigned country code (`"ZZ"`) correctly rejected against the real ISO 3166-1 list, malformed (comma) amount, status transitions including low-confidence PDF forcing review.
- `test_csv_import.py` — the full provided sample CSV (asserts exactly 30 rows imported, 13 NEEDS_REVIEW / 17 VALID, matching the intentionally-invalid rows), source filename/batch association, a file that mixes one valid and one invalid row (whole file not rejected), batch summary endpoint, batch deletion (removes it and cascades to its records; unknown batch → 404), filtering records by source document name, and per-document deletion (removes only that document's records; unknown document → 404).
- `test_correction_flow.py` — validate rejected (409) while NEEDS_REVIEW, full correct → revalidate → VALID → validate → VALIDATED cycle, revalidation that's still invalid, the record-errors endpoint.
- `test_pdf_extraction.py` — provider error/timeout doesn't crash (produces a NEEDS_REVIEW placeholder), invalid structured response handled gracefully, missing required field → NEEDS_REVIEW, low confidence forces NEEDS_REVIEW even with complete fields, a bank-statement-shaped response produces multiple records, duplicate reference across PDF-extracted records is flagged, original PDF is stored and servable via the source-file endpoint, CSV records correctly report no source file, deleting a document removes its records and its stored PDF.
- `test_reconciliation.py` — a statement line uploaded *after* the invoice it references is backfilled immediately; one uploaded *before* is backfilled retroactively once the invoice arrives; a CSV row's `invoice_number` reconciles a PDF statement line; an unrelated description is left alone; a reference match with a mismatched amount is correctly treated as a false positive and not linked.
- `test_upload_guards.py` — an oversized upload is rejected (413) at both the unit level and through the real CSV endpoint; PDF content lacking the `%PDF-` signature is rejected (400) at both the unit level and through the real upload endpoint, even when named `*.pdf`; the size limit is confirmed configurable via `settings.max_upload_mb`.
- `test_audit_history.py` — editing a field creates a history entry with the correct old/new values; saving without changing anything creates none; changing two fields creates two entries; an automatic reconciliation backfill is logged with `source="reconciliation"`; the history endpoint 404s for an unknown record.
- `test_duplicate_detection.py` — byte-identical CSV/PDF content is rejected (409) under a different filename, across separate upload calls, and within the same multi-file PDF upload; different content is always allowed regardless of filename.

The real Anthropic integration (not part of the automated suite, which must stay deterministic and offline) was verified manually against all three sample PDFs — results in the table under [AI provider integration](#ai-provider-integration).

## Sample files

Provided in `samples/`: `transactions_import.csv`, `invoice_legal_services.pdf`, `invoice_software_subscription.pdf`, `bank_statement_july_2026.pdf`, `Data_Dictionary.pdf`, `Technical_Assignment.pdf`. Upload the CSV and/or PDFs to a batch through the UI (or `POST /api/batches/{id}/upload/csv` / `/upload/pdf`) to reproduce everything described above.

## AI tools used

**Claude Code** was used for effectively the entire implementation (backend, frontend, tests, this README), driven interactively: I provided the assignment PDF, data dictionary, and sample files, and worked through the design decisions above (validation architecture, status lifecycle, provider abstraction, assumptions) as explicit choices rather than accepting defaults silently — several of the [Assumptions](#assumptions) above (duplicate-reference handling, edit-not-auto-revalidating, bank-statement country inference) were decisions I reviewed and confirmed rather than boilerplate.

**How it was verified, not just generated:**
- Every backend service module was exercised against the real sample data before moving on — the CSV importer was run against the actual `transactions_import.csv` and its output checked row-by-row against the 13 intentionally-invalid rows (`test_csv_import.py::test_full_sample_csv_import` pins this: 30 imported / 13 NEEDS_REVIEW / 17 VALID).
- The AI provider integration was **run for real** against Anthropic's API with all three sample PDFs (not just unit-tested against a fake) — see the results table above, captured directly from that run.
- The full frontend workflow (create batch → upload CSV → filter to NEEDS_REVIEW → open a record → see the exact invalid field highlighted with its message → correct it → re-run validation → see it become VALID → validate → see it become VALIDATED) was driven end-to-end in a real browser against the running backend, screenshotted at each step, not just assumed to work from the code.
- The full `pytest` suite (60 tests) passes locally.

**Parts that needed correction/redesign during the session:**
- The initial `datetime.utcnow()` usage in `models.py` triggered a deprecation warning under the installed SQLAlchemy/Python versions and was switched to `datetime.now(timezone.utc)`.
- `Settings.env_file` initially resolved `.env` relative to the process's current working directory, which broke when the backend was launched from a different working directory (surfaced concretely as `ANTHROPIC_API_KEY is not configured` errors during manual browser testing even though `backend/.env` was correctly filled in) — fixed to resolve the `.env` path relative to the config module's own location instead.
- The record-detail drawer originally refetched the *filtered* record list after a revalidate/validate action to refresh its state; when a record's status changed such that it no longer matched the active filter (e.g. NEEDS_REVIEW → VALID while filtering to "Needs review"), the drawer would silently close instead of showing the new status. Fixed to fetch the single record by ID directly, so the drawer stays open and the user can immediately continue — this was caught by actually clicking through the flow in a browser, not from reading the code.
- The initial `country` validation only checked *format* (`^[A-Z]{2}$`), which would silently accept an unassigned code like `"ZZ"` — a real gap against the data dictionary's "must be a two-letter ISO code" rule, initially shipped as a documented, deliberate scope trade-off rather than an oversight. When re-checked line-by-line against the data dictionary's rule list, it was upgraded to validate against the actual 249-code ISO 3166-1 alpha-2 list (`app/iso_countries.py`) instead of trusting the format alone.

I can walk through and explain any part of this codebase in the follow-up interview, including the reasoning behind each of the assumptions above.
