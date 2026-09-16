from io import BytesIO
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import select

from app.models import AuditLog, Party, Tannery
from test_tannery_crud import master_api


def opening_book(rows, report_date="1-Apr-2026"):
    book = Workbook()
    sheet = book.active
    sheet.append(["TALCO"])
    sheet.append(["Sundry Debtors"])
    sheet.append([f"For {report_date}"])
    sheet.append(["Particulars", f"For {report_date}", None])
    sheet.append([None, "Closing Balance", None])
    sheet.append([None, "Debit", "Credit"])
    debit = credit = Decimal("0")
    for name, dr, cr in rows:
        sheet.append([name, dr, cr])
        debit += Decimal(str(dr or 0)); credit += Decimal(str(cr or 0))
    sheet.append(["Grand Total", float(debit), float(credit)])
    output = BytesIO(); book.save(output)
    return output.getvalue()


def test_preview_apply_and_approved_overwrite(master_api):
    client, headers, factory = master_api
    with factory() as session:
        session.add_all([
            Tannery(sno=101, name="Alpha Tannery", normalized_key="ALPHATANNERY", pump_house="A"),
            Tannery(sno=102, name="Beta Tannery", normalized_key="BETATANNERY", pump_house="B"),
        ])
        session.commit()
    first = opening_book([("Alpha Account C/o.Alpha Tannery", 1000, None),
                          ("Beta Account C/o.Beta Tannery", None, 250)])
    upload = {"file": ("opening.xlsx", first,
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    preview = client.post("/api/accounts/opening-import/preview", files=upload,
                          headers=headers["talco_admin"])
    assert preview.status_code == 200, preview.text
    assert preview.json()["create_count"] == 2
    assert preview.json()["debit_total"] == "1000.00"
    assert preview.json()["credit_total"] == "250.00"

    applied = client.post("/api/accounts/opening-import/apply", files=upload,
                          data={"approve_overwrite": "false", "reason": ""},
                          headers=headers["talco_admin"])
    assert applied.status_code == 200, applied.text
    assert applied.json()["updated_count"] == 2
    with factory() as session:
        alpha = session.scalar(select(Party).where(Party.name == "Alpha Account"))
        beta = session.scalar(select(Party).where(Party.name == "Beta Account"))
        assert alpha.opening_amount == Decimal("1000.00")
        assert beta.opening_amount == Decimal("-250.00")
        assert alpha.opening_date == date(2026, 4, 1)

    changed = opening_book([("Alpha Account C/o.Alpha Tannery", 1200, None),
                            ("Beta Account C/o.Beta Tannery", None, 250)])
    changed_upload = {"file": ("opening-corrected.xlsx", changed,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    second = client.post("/api/accounts/opening-import/preview", files=changed_upload,
                         headers=headers["talco_admin"])
    assert second.json()["overwrite_count"] == 1
    assert second.json()["unchanged_count"] == 1
    rejected = client.post("/api/accounts/opening-import/apply", files=changed_upload,
                           data={"approve_overwrite": "false", "reason": ""},
                           headers=headers["talco_admin"])
    assert rejected.status_code == 422
    approved = client.post("/api/accounts/opening-import/apply", files=changed_upload,
                           data={"approve_overwrite": "true", "reason": "Tally balance corrected"},
                           headers=headers["talco_admin"])
    assert approved.status_code == 200, approved.text
    assert approved.json()["updated_count"] == 1
    with factory() as session:
        alpha = session.scalar(select(Party).where(Party.name == "Alpha Account"))
        assert alpha.opening_amount == Decimal("1200.00")
        log = session.scalar(select(AuditLog).where(AuditLog.entity_id == alpha.id,
                                                    AuditLog.action == "opening_overwrite"))
        assert log is not None and "Tally balance corrected" in log.changes


def test_opening_import_blocks_unmatched_and_non_admin(master_api):
    client, headers, _ = master_api
    content = opening_book([("Unknown Account", 100, None)])
    upload = {"file": ("opening.xlsx", content,
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    assert client.post("/api/accounts/opening-import/preview", files=upload,
                       headers=headers["talco_staff"]).status_code == 403
    preview = client.post("/api/accounts/opening-import/preview", files=upload,
                          headers=headers["talco_admin"])
    assert preview.json()["unmatched_count"] == 1
    applied = client.post("/api/accounts/opening-import/apply", files=upload,
                          data={"approve_overwrite": "true", "reason": "Approved"},
                          headers=headers["talco_admin"])
    assert applied.status_code == 422
