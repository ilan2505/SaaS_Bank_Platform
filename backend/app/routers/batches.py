from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FinancialRecord, ImportBatch, RecordStatus
from app.schemas import BatchCreate, BatchOut, BatchSummary, RecordOut, UploadResult
from app.services.ai_provider import AIProvider
from app.services.csv_import import import_csv
from app.services.pdf_extraction import get_provider, import_pdf
from app.services.storage import delete_batch_uploads, save_pdf

router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    batch = ImportBatch(name=payload.name)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=list[BatchSummary])
def list_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc())).all()
    return [_summarize(batch) for batch in batches]


@router.delete("/{batch_id}", status_code=204)
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")

    db.delete(batch)  # cascades to its records via the ORM relationship
    db.commit()
    delete_batch_uploads(batch_id)


@router.get("/{batch_id}", response_model=BatchSummary)
def get_batch_summary(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return _summarize(batch)


@router.get("/{batch_id}/records", response_model=list[RecordOut])
def list_records(
    batch_id: str,
    status: str | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")

    query = select(FinancialRecord).where(FinancialRecord.batch_id == batch_id)
    if status:
        query = query.where(FinancialRecord.status == status)
    if source_type:
        query = query.where(FinancialRecord.source_type == source_type)
    query = query.order_by(FinancialRecord.created_at)

    return db.scalars(query).all()


@router.post("/{batch_id}/upload/csv", response_model=UploadResult)
async def upload_csv(batch_id: str, file: UploadFile, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Expected a .csv file")

    content = await file.read()
    records = import_csv(content, file.filename, batch_id)

    db.add_all(records)
    db.commit()
    for r in records:
        db.refresh(r)

    return UploadResult(batch_id=batch_id, records_created=len(records), records=records)


@router.post("/{batch_id}/upload/pdf", response_model=UploadResult)
async def upload_pdfs(
    batch_id: str,
    files: list[UploadFile],
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_provider),
):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")

    existing_refs = {
        r.reference
        for r in db.scalars(
            select(FinancialRecord).where(
                FinancialRecord.batch_id == batch_id, FinancialRecord.reference.is_not(None)
            )
        ).all()
    }

    all_records = []
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"'{file.filename}' is not a PDF")
        content = await file.read()
        stored_path = save_pdf(batch_id, file.filename, content)
        records = import_pdf(provider, content, file.filename, batch_id, existing_refs)
        for r in records:
            r.source_document_path = stored_path
            if r.reference:
                existing_refs.add(r.reference)
        all_records.extend(records)

    db.add_all(all_records)
    db.commit()
    for r in all_records:
        db.refresh(r)

    return UploadResult(batch_id=batch_id, records_created=len(all_records), records=all_records)


def _summarize(batch: ImportBatch) -> BatchSummary:
    records = batch.records
    return BatchSummary(
        id=batch.id,
        name=batch.name,
        created_at=batch.created_at,
        total_records=len(records),
        needs_review_count=sum(1 for r in records if r.status == RecordStatus.NEEDS_REVIEW),
        valid_count=sum(1 for r in records if r.status == RecordStatus.VALID),
        validated_count=sum(1 for r in records if r.status == RecordStatus.VALIDATED),
        source_documents=sorted({r.source_document_name for r in records}),
    )
