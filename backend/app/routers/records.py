from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import FinancialRecord, RecordStatus
from app.schemas import RecordOut, RecordUpdate, ValidationError
from app.services.validation import (
    check_business_rules,
    determine_status,
    parse_record_fields,
    record_to_raw_dict,
)

router = APIRouter(prefix="/api/records", tags=["records"])


def _get_record_or_404(record_id: str, db: Session) -> FinancialRecord:
    record = db.get(FinancialRecord, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    return record


def _other_references(db: Session, batch_id: str, record_id: str) -> set[str]:
    rows = db.scalars(
        select(FinancialRecord.reference).where(
            FinancialRecord.batch_id == batch_id,
            FinancialRecord.id != record_id,
            FinancialRecord.reference.is_not(None),
        )
    ).all()
    return set(rows)


@router.get("/{record_id}", response_model=RecordOut)
def get_record(record_id: str, db: Session = Depends(get_db)):
    return _get_record_or_404(record_id, db)


@router.get("/{record_id}/errors", response_model=list[ValidationError])
def get_record_errors(record_id: str, db: Session = Depends(get_db)):
    record = _get_record_or_404(record_id, db)
    return record.validation_errors


@router.patch("/{record_id}", response_model=RecordOut)
def edit_record(record_id: str, payload: RecordUpdate, db: Session = Depends(get_db)):
    """Apply corrections to a record's fields. Does NOT re-run validation:
    the record is marked NEEDS_REVIEW until POST /records/{id}/revalidate is
    called, matching the assignment's explicit correct-then-revalidate flow.
    """
    record = _get_record_or_404(record_id, db)

    merged = record_to_raw_dict(record)
    updates = payload.model_dump(exclude_unset=True)
    merged.update(updates)

    typed, raw_kept, _parse_errors = parse_record_fields(merged)

    for field, value in typed.items():
        setattr(record, field, value if value is not None else (0 if field in ("fee_amount", "tax_amount") else None))
    record.raw_values = raw_kept
    record.status = RecordStatus.NEEDS_REVIEW

    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/revalidate", response_model=RecordOut)
def revalidate_record(record_id: str, db: Session = Depends(get_db)):
    record = _get_record_or_404(record_id, db)

    raw = record_to_raw_dict(record)
    typed, raw_kept, parse_errors = parse_record_fields(raw)
    other_refs = _other_references(db, record.batch_id, record.id)
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
    db.refresh(record)
    return record


@router.post("/{record_id}/validate", response_model=RecordOut)
def validate_record(record_id: str, db: Session = Depends(get_db)):
    record = _get_record_or_404(record_id, db)

    if record.status != RecordStatus.VALID:
        current = record.status.value if hasattr(record.status, "value") else record.status
        raise HTTPException(
            409,
            f"Record must be VALID before it can be validated (current status: {current}). "
            "Fix the reported errors and re-run validation first.",
        )

    record.status = RecordStatus.VALIDATED
    db.commit()
    db.refresh(record)
    return record
