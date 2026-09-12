from decimal import Decimal

import pytest

from app.importer.parser import TallyParseError, parse_file


@pytest.mark.parametrize(
    ("filename", "count", "base", "gross", "rate"),
    [
        ("Treatment.xml", 37, "4324121", "4540339", Decimal("5")),
        ("Chrome.xml", 8, "115600", "121380", Decimal("5")),
        ("Sludge.xml", 16, "83694", "98758", Decimal("18")),
        ("Receipt.xml", 53, "0", "5766381", None),
    ],
)
def test_real_file_control_totals(fixtures_dir, filename, count, base, gross, rate) -> None:
    rows = parse_file(fixtures_dir / filename)
    assert len(rows) == count
    assert sum((row.base or Decimal()) for row in rows) == Decimal(base)
    assert sum(row.gross for row in rows) == Decimal(gross)
    assert all(not row.tax_errors for row in rows)
    assert {row.gst_rate for row in rows if row.gst_rate is not None} == ({rate} if rate else set())


def test_corrupt_tax_is_reported_not_dropped(tmp_path) -> None:
    source = tmp_path / "bad-tax.xml"
    source.write_text(
        "<ENVELOPE><DBCFIXED><DBCDATE>31-Aug-2026</DBCDATE>"
        "<DBCPARTY>ABC Associates</DBCPARTY></DBCFIXED><DBCVCHTYPE>Sales</DBCVCHTYPE>"
        "<DBCGSTIN></DBCGSTIN><DBCGROSSAMT>-105</DBCGROSSAMT>"
        "<DBCLEDAMT>100</DBCLEDAMT><DBCLEDAMT>2</DBCLEDAMT>"
        "<DBCLEDAMT>3</DBCLEDAMT></ENVELOPE>",
        encoding="utf-8",
    )
    rows = parse_file(source)
    assert len(rows) == 1
    assert rows[0].tax_errors
    assert "does not equal" in rows[0].tax_errors[0]


def test_truncated_xml_has_block_number_or_clear_file_error(tmp_path) -> None:
    source = tmp_path / "truncated.xml"
    source.write_text("<ENVELOPE><DBCFIXED><DBCDATE>31-Aug-2026</DBCDATE>", encoding="utf-8")
    with pytest.raises(TallyParseError, match="DBCFIXED blocks"):
        parse_file(source)


def test_excel_sales_calculates_tally_tax_and_warns_for_missing_voucher(tmp_path) -> None:
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet["A7"] = "Treatment Charges Raised A/c"
    sheet.append(["Date", "Particulars", "", "Vch Type", "Vch No.", "Debit", "Credit"])
    sheet.append([__import__("datetime").datetime(2026, 8, 31), "By", "ABC Associates", "Sales", None, None, 96300])
    path = tmp_path / "sales.xlsx"
    book.save(path)
    rows = parse_file(path)
    assert len(rows) == 1
    assert rows[0].base == Decimal("96300")
    assert rows[0].cgst == Decimal("2408")
    assert rows[0].sgst == Decimal("2408")
    assert rows[0].gross == Decimal("101116")
    assert rows[0].charge_ledger == "Treatment charges"
    assert any("Voucher" in warning for warning in rows[0].warnings)


def test_excel_receipt_without_bill_reference_is_warning_only(tmp_path) -> None:
    from datetime import datetime
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.append(["Receipt Register"])
    sheet.append(["Date", "Particulars", "Vch Type", "Vch No.", "Debit", "Credit"])
    sheet.append([datetime(2026, 8, 1), "ABC Associates", "Bank Receipt", "228", None, 50000])
    path = tmp_path / "receipts.xlsx"
    book.save(path)
    rows = parse_file(path)
    assert len(rows) == 1
    assert rows[0].is_receipt
    assert rows[0].gross == Decimal("50000")
    assert not rows[0].tax_errors
    assert any("unallocated" in warning for warning in rows[0].warnings)
