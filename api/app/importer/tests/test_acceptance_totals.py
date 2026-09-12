from decimal import Decimal

from app.importer.parser import parse_file


def test_exact_sales_tax_control_totals(fixtures_dir) -> None:
    expected = {
        "Treatment.xml": (Decimal("108109"), Decimal("108109")),
        "Chrome.xml": (Decimal("2890"), Decimal("2890")),
        "Sludge.xml": (Decimal("7532"), Decimal("7532")),
    }
    for filename, (cgst, sgst) in expected.items():
        rows = parse_file(fixtures_dir / filename)
        assert sum(row.cgst or Decimal() for row in rows) == cgst
        assert sum(row.sgst or Decimal() for row in rows) == sgst


def test_optional_new_tally_fields_are_captured(tmp_path) -> None:
    source = tmp_path / "future-export.xml"
    source.write_text(
        "<ENVELOPE><DBCFIXED><DBCDATE>31-Aug-2026</DBCDATE><DBCPARTY>ABC Associates</DBCPARTY>"
        "</DBCFIXED><DBCVCHTYPE>Sales</DBCVCHTYPE><DBCVCHNO>274/2026-2027</DBCVCHNO>"
        "<DBCGSTIN></DBCGSTIN><DBCGROSSAMT>-105</DBCGROSSAMT>"
        "<DBCLEDNAME>Treatment</DBCLEDNAME><DBCLEDAMT>100</DBCLEDAMT>"
        "<DBCLEDNAME>CGST</DBCLEDNAME><DBCLEDAMT>2.5</DBCLEDAMT>"
        "<DBCLEDNAME>SGST</DBCLEDNAME><DBCLEDAMT>2.5</DBCLEDAMT></ENVELOPE>", encoding="utf-8",
    )
    row = parse_file(source)[0]
    assert row.voucher_no == "274/2026-2027"
    assert row.ledger_names == ("Treatment", "CGST", "SGST")

