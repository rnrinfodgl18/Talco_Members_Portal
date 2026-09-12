from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TannerySerialCounter(Base):
    __tablename__ = "tannery_serial_counter"
    id: Mapped[int] = mapped_column(primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class Pump(Base):
    __tablename__ = "pump"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class Tannery(Base):
    __tablename__ = "tannery"

    id: Mapped[int] = mapped_column(primary_key=True)
    sno: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    pump_house: Mapped[str] = mapped_column(String(20), ForeignKey("pump.code", onupdate="CASCADE", ondelete="RESTRICT"), index=True, nullable=False)
    internal_id: Mapped[str | None] = mapped_column(String(100))
    factory_id: Mapped[str | None] = mapped_column(String(100))
    tnpcb_user_id: Mapped[str | None] = mapped_column(String(100))
    gps: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(String(20))
    consent: Mapped[str | None] = mapped_column(String(255))
    original_capacity: Mapped[str | None] = mapped_column(String(100))
    additional_capacity: Mapped[str | None] = mapped_column(String(100))
    original_shares: Mapped[int | None] = mapped_column(Integer)
    additional_shares: Mapped[int | None] = mapped_column(Integer)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Party(Base):
    __tablename__ = "party"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    opening_date: Mapped[date | None] = mapped_column(Date)
    opening_note: Mapped[str | None] = mapped_column(String(500))


class TanneryPartyLink(Base):
    __tablename__ = "tannery_party_link"
    id: Mapped[int] = mapped_column(primary_key=True)
    tannery_id: Mapped[int] = mapped_column(ForeignKey("tannery.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("tannery_id", "party_id", "valid_from"),)


class PartyAlias(Base):
    __tablename__ = "party_alias"
    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"))
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChargeHead(Base):
    __tablename__ = "charge_head"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class ImportBatch(Base):
    __tablename__ = "import_batch"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    charge_head_id: Mapped[int | None] = mapped_column(ForeignKey("charge_head.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StagingRow(Base):
    __tablename__ = "staging_row"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_party: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("batch_id", "row_number"),)


class Invoice(Base):
    __tablename__ = "invoice"
    id: Mapped[int] = mapped_column(primary_key=True)
    tannery_id: Mapped[int] = mapped_column(ForeignKey("tannery.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), nullable=False)
    charge_head_id: Mapped[int] = mapped_column(ForeignKey("charge_head.id"), nullable=False)
    voucher_no: Mapped[str] = mapped_column(String(100), nullable=False)
    fy: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    source_guid: Mapped[str | None] = mapped_column(String(100), unique=True)
    source_alter_id: Mapped[int | None] = mapped_column(Integer)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    __table_args__ = (
        UniqueConstraint("voucher_no", "fy"),
        Index("ix_invoice_tannery_date", "tannery_id", "invoice_date"),
        Index("ix_invoice_party_date", "party_id", "invoice_date"),
    )


class InvoiceRevision(Base):
    __tablename__ = "invoice_revision"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    replacement: Mapped[str | None] = mapped_column(Text)
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey('import_batch.id'))
    reason: Mapped[str | None] = mapped_column(String(500))
    revised_by: Mapped[str | None] = mapped_column(String(255))
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipt"
    id: Mapped[int] = mapped_column(primary_key=True)
    tannery_id: Mapped[int] = mapped_column(ForeignKey("tannery.id"), nullable=False)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), nullable=False)
    voucher_no: Mapped[str] = mapped_column(String(100), nullable=False)
    fy: Mapped[str] = mapped_column(String(20), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_step: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_guid: Mapped[str | None] = mapped_column(String(100), unique=True)
    source_alter_id: Mapped[int | None] = mapped_column(Integer)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    __table_args__ = (
        UniqueConstraint("voucher_no", "fy"),
        Index("ix_receipt_tannery_date", "tannery_id", "receipt_date"),
        Index("ix_receipt_party_date", "party_id", "receipt_date"),
    )


class ReceiptAllocation(Base):
    __tablename__ = "receipt_allocation"
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoice.id"))
    bill_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    allocation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    __table_args__ = (UniqueConstraint("receipt_id", "bill_ref", "allocation_type"),)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issue"
    id: Mapped[int] = mapped_column(primary_key=True)
    tannery_id: Mapped[int] = mapped_column(ForeignKey("tannery.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("tannery_id", "code", "detail"),)


class CompanySetting(Base):
    __tablename__ = "company_setting"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="TALCO-DINTEC")
    short_name: Mapped[str] = mapped_column(String(100), nullable=False, default="TALCO")
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    gstin: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_mime: Mapped[str | None] = mapped_column(String(50))
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password: Mapped[str | None] = mapped_column(Text)
    smtp_from_email: Mapped[str | None] = mapped_column(String(255))
    smtp_from_name: Mapped[str | None] = mapped_column(String(255))
    smtp_security: Mapped[str] = mapped_column(String(20), default="starttls", server_default="starttls", nullable=False)
    smtp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Circular(Base):
    __tablename__ = "circular"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="general", server_default="general", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal", nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published", nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_mime: Mapped[str | None] = mapped_column(String(100))
    attachment_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CircularRecipient(Base):
    __tablename__ = "circular_recipient"
    circular_id: Mapped[int] = mapped_column(ForeignKey("circular.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)


class CircularRead(Base):
    __tablename__ = "circular_read"
    circular_id: Mapped[int] = mapped_column(ForeignKey("circular.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
