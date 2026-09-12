from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Tannery:
    sno: int
    name: str
    pump_house: str
    internal_id: str | None = None
    factory_id: str | None = None
    tnpcb_user_id: str | None = None
    gps: str | None = None
    gstin: str | None = None
    consent: str | None = None
    original_capacity: str | None = None
    additional_capacity: str | None = None
    original_shares: int | None = None
    additional_shares: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class VoucherRow:
    row_number: int
    voucher_date: date
    party: str
    voucher_type: str
    gstin: str | None
    gross: Decimal
    ledger_amounts: tuple[Decimal, ...]
    base: Decimal | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    gst_rate: Decimal | None = None
    tax_errors: tuple[str, ...] = ()
    voucher_no: str | None = None
    ledger_names: tuple[str, ...] = ()
    source_guid: str | None = None
    source_alter_id: int | None = None
    is_cancelled: bool = False
    charge_ledger: str | None = None
    bill_allocations: tuple[tuple[str, str, Decimal], ...] = ()
    warnings: tuple[str, ...] = ()
    source_format: str = "xml"

    @property
    def is_receipt(self) -> bool:
        return "RECEIPT" in self.voucher_type.upper()


@dataclass(frozen=True)
class PartyParts:
    raw: str
    cleaned: str
    left: str
    right: str | None
    is_step: bool


@dataclass(frozen=True)
class Resolution:
    tannery: Tannery | None
    party_name: str
    is_step: bool
    method: str

    @property
    def matched(self) -> bool:
        return self.tannery is not None

