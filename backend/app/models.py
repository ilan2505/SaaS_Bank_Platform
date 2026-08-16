import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SourceType(str, enum.Enum):
    CSV = "CSV"
    PDF = "PDF"


class RecordStatus(str, enum.Enum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VALID = "VALID"
    VALIDATED = "VALIDATED"


class Currency(str, enum.Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"


class Category(str, enum.Enum):
    MANAGEMENT_FEE = "MANAGEMENT_FEE"
    BANK_FEE = "BANK_FEE"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"
    SUBSCRIPTION = "SUBSCRIPTION"
    SOFTWARE = "SOFTWARE"
    AUDIT = "AUDIT"
    INTEREST_PAYMENT = "INTEREST_PAYMENT"
    EXPENSE_REIMBURSEMENT = "EXPENSE_REIMBURSEMENT"
    REGULATORY_FEE = "REGULATORY_FEE"
    REDEMPTION = "REDEMPTION"
    CORPORATE_SERVICES = "CORPORATE_SERVICES"
    FX_ADJUSTMENT = "FX_ADJUSTMENT"
    INSURANCE = "INSURANCE"
    ADMINISTRATION_FEE = "ADMINISTRATION_FEE"
    OTHER = "OTHER"


class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    DIRECT_DEBIT = "DIRECT_DEBIT"
    CARD = "CARD"
    INTERNAL = "INTERNAL"


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    records: Mapped[list["FinancialRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)

    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    gross_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True, default=0)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True, default=0)
    net_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String, nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String, nullable=True)

    source_type: Mapped[str] = mapped_column(SAEnum(SourceType), nullable=False)
    source_document_name: Mapped[str] = mapped_column(String, nullable=False)
    # Path (relative to backend/) to the stored original PDF, so the review UI
    # can show the source document next to the extracted fields. Only set for
    # PDF-sourced records; CSV rows have no separate "document" to display.
    source_document_path: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    status: Mapped[str] = mapped_column(
        SAEnum(RecordStatus), nullable=False, default=RecordStatus.NEEDS_REVIEW
    )
    validation_errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Raw string values as originally parsed, kept for fields that failed to
    # convert to their proper type (e.g. "not-a-date"). Lets the UI show the
    # user what was actually in the source instead of a blank field.
    raw_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    batch: Mapped["ImportBatch"] = relationship(back_populates="records")

    @property
    def has_source_file(self) -> bool:
        return self.source_document_path is not None
