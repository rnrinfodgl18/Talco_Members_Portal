import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.importer.models import VoucherRow

_BLOCK_RE = re.compile(r"<DBCFIXED\b.*?(?=<DBCFIXED\b|</ENVELOPE>)", re.IGNORECASE | re.DOTALL)
_INVALID_REF_RE = re.compile(r"&#(?:x0*([0-9a-fA-F]+)|0*([0-9]+));", re.IGNORECASE)

class TallyParseError(ValueError):
    pass

def _decode(path: Path) -> str:
    payload = path.read_bytes()
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return payload.decode("utf-16")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("utf-16")

def _clean_xml(text: str) -> str:
    def replace(match: re.Match) -> str:
        value = int(match.group(1), 16) if match.group(1) else int(match.group(2))
        return "" if value in (*range(0, 9), 11, 12, *range(14, 32)) else match.group(0)
    return _INVALID_REF_RE.sub(replace, text)

def _values(block: str, tag: str) -> list[str]:
    pattern = rf"<{tag}\b[^>]*>(.*?)</{tag}>"
    return [html.unescape(item).strip() for item in re.findall(pattern, block, re.IGNORECASE | re.DOTALL)]

def _required(block: str, tag: str, row_number: int) -> str:
    values = _values(block, tag)
    if not values or not values[0]:
        raise TallyParseError(f"Block {row_number}: missing {tag}")
    return values[0]

def _decimal(value: str, tag: str, row_number: int, absolute: bool = True) -> Decimal:
    try:
        result = Decimal(value.replace(",", "").strip())
        return abs(result) if absolute else result
    except InvalidOperation as exc:
        raise TallyParseError(f"Block {row_number}: invalid {tag} value {value!r}") from exc

def _tax(base: Decimal | None, cgst: Decimal | None, sgst: Decimal | None) -> tuple[Decimal | None, tuple[str, ...]]:
    errors: list[str] = []
    rate = None
    if base is None or cgst is None or sgst is None:
        errors.append("sales row requires taxable amount, CGST and SGST ledger amounts")
    else:
        if cgst != sgst:
            errors.append(f"CGST {cgst} does not equal SGST {sgst}")
        if base:
            rate = ((cgst + sgst) * Decimal("100") / base).quantize(Decimal("1"))
            if abs(base * rate / Decimal("100") - cgst - sgst) > Decimal("1"):
                errors.append(f"base x {rate}% differs from total tax by more than 1")
    return rate, tuple(errors)

def _parse_full_tally(text: str, source_name: str) -> list[VoucherRow]:
    try:
        root = ET.fromstring(_clean_xml(text))
    except ET.ParseError as exc:
        raise TallyParseError(f"Invalid Tally XML in {source_name}: {exc}") from exc
    rows: list[VoucherRow] = []
    for voucher in root.iter("VOUCHER"):
        voucher_type = (voucher.findtext("VOUCHERTYPENAME") or "").strip()
        if voucher_type.upper() not in {"SALES", "RECEIPT"}:
            continue
        number = len(rows) + 1
        raw_date = (voucher.findtext("DATE") or "").strip()
        try:
            voucher_date = datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError as exc:
            raise TallyParseError(f"Voucher {number}: invalid DATE {raw_date!r}") from exc
        party = (voucher.findtext("PARTYLEDGERNAME") or "").strip()
        if not party:
            raise TallyParseError(f"Voucher {number}: missing PARTYLEDGERNAME")
        entry_nodes = voucher.findall("LEDGERENTRIES.LIST") or voucher.findall("ALLLEDGERENTRIES.LIST")
        entries: list[tuple[str, Decimal]] = []
        allocations: list[tuple[str, str, Decimal]] = []
        for entry in entry_nodes:
            name = (entry.findtext("LEDGERNAME") or "").strip()
            raw_amount = (entry.findtext("AMOUNT") or "0").strip()
            amount = _decimal(raw_amount, "AMOUNT", number, absolute=False)
            entries.append((name, amount))
            for allocation in entry.findall("BILLALLOCATIONS.LIST"):
                reference = (allocation.findtext("NAME") or "").strip()
                allocation_type = (allocation.findtext("BILLTYPE") or "").strip()
                raw_alloc = (allocation.findtext("AMOUNT") or "").strip()
                if reference and allocation_type and raw_alloc:
                    allocations.append((reference, allocation_type, abs(_decimal(raw_alloc, "BILL AMOUNT", number, False))))
        is_receipt = voucher_type.upper() == "RECEIPT"
        party_amount = next((abs(amount) for name, amount in entries if name.casefold() == party.casefold()), None)
        cgst = next((abs(amount) for name, amount in entries if name.strip().upper() == "CGST"), None)
        sgst = next((abs(amount) for name, amount in entries if name.strip().upper() == "SGST"), None)
        excluded = {party.casefold(), "cgst", "sgst"}
        charge_entries = [(name, abs(amount)) for name, amount in entries
                          if name and name.casefold() not in excluded and amount > 0]
        charge_ledger = charge_entries[0][0] if charge_entries and not is_receipt else None
        base = charge_entries[0][1] if charge_entries and not is_receipt else None
        gross = party_amount if party_amount is not None else sum(abs(amount) for _, amount in entries if amount > 0)
        rate, tax_errors = (None, ()) if is_receipt else _tax(base, cgst, sgst)
        rows.append(VoucherRow(
            row_number=number, voucher_date=voucher_date, party=party, voucher_type=voucher_type,
            gstin=(voucher.findtext("PARTYGSTIN") or "").strip() or None, gross=gross,
            ledger_amounts=tuple(abs(amount) for _, amount in entries), base=base, cgst=cgst, sgst=sgst,
            gst_rate=rate, tax_errors=tax_errors,
            voucher_no=(voucher.findtext("VOUCHERNUMBER") or "").strip() or None,
            ledger_names=tuple(name for name, _ in entries if name),
            source_guid=(voucher.findtext("GUID") or "").strip() or None,
            source_alter_id=int((voucher.findtext("ALTERID") or "0").strip() or 0) or None,
            is_cancelled=(voucher.findtext("ISCANCELLED") or "No").strip().casefold() == "yes"
                         or (voucher.findtext("ISDELETED") or "No").strip().casefold() == "yes",
            charge_ledger=charge_ledger, bill_allocations=tuple(allocations),
        ))
    if not rows:
        raise TallyParseError(f"No Sales or Receipt vouchers found in {source_name}")
    return rows

def _parse_legacy(text: str, source_name: str) -> list[VoucherRow]:
    blocks = _BLOCK_RE.findall(text)
    if not blocks:
        raise TallyParseError(f"No DBCFIXED blocks or supported vouchers found in {source_name}")
    rows: list[VoucherRow] = []
    for number, block in enumerate(blocks, start=1):
        try:
            voucher_date = datetime.strptime(_required(block, "DBCDATE", number), "%d-%b-%Y").date()
        except ValueError as exc:
            raise TallyParseError(f"Block {number}: invalid DBCDATE") from exc
        party = _required(block, "DBCPARTY", number)
        voucher_type = _required(block, "DBCVCHTYPE", number)
        gross = _decimal(_required(block, "DBCGROSSAMT", number), "DBCGROSSAMT", number)
        gstin_values = _values(block, "DBCGSTIN")
        voucher_values = _values(block, "DBCVCHNO")
        ledger_names = tuple(value for value in _values(block, "DBCLEDNAME") if value)
        amounts = tuple(_decimal(value, "DBCLEDAMT", number) for value in _values(block, "DBCLEDAMT") if value)
        base = cgst = sgst = rate = None
        errors: tuple[str, ...] = ()
        if "RECEIPT" not in voucher_type.upper():
            if len(amounts) >= 3:
                base, cgst, sgst = amounts[:3]
            rate, errors = _tax(base, cgst, sgst)
        rows.append(VoucherRow(number, voucher_date, party, voucher_type,
            gstin_values[0] if gstin_values and gstin_values[0] else None, gross, amounts,
            base, cgst, sgst, rate, errors,
            voucher_values[0] if voucher_values and voucher_values[0] else None, ledger_names))
    return rows

def parse_file(path: str | Path) -> list[VoucherRow]:
    source = Path(path)
    if source.suffix.casefold() in {".xlsx", ".xlsm"}:
        from app.importer.excel_parser import parse_excel
        return parse_excel(source)
    text = _decode(source)
    if "<VOUCHER" in text.upper():
        return _parse_full_tally(text, source.name)
    return _parse_legacy(text, source.name)
