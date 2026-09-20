"""Send freshly posted bills to the members and lessees they belong to.

Email carries the regenerated invoice PDF as an attachment. WhatsApp carries
text and a portal link only: the gateway is an unofficial self-hosted one and
pushing documents through it raises the number-ban risk for no benefit, since
the member can open the same bill in the portal.

Dispatch is admin-triggered rather than automatic, and every send is recorded
as a notification so re-running it never sends the same bill twice.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChargeHead, ImportBatch, Invoice, Notification, Party, StagingRow
from app.models.auth import User
from app.services.invoice_pdf import invoice_pdf
from app.services.notifications import send_email, send_push
from app.services.scope import lease_window_filter
from app.services.whatsapp import send_whatsapp

KIND = "bill"


def _portal_link() -> str:
    return get_settings().public_url.rstrip("/") + "/portal"


def recipients_for(session: Session, invoice: Invoice) -> list[User]:
    """Users entitled to this invoice: ledger grantees, the lessee, the owner.

    The lease window is re-applied per user, so a lessee is never mailed a bill
    they would not be allowed to open in the portal.
    """
    candidates = session.scalars(select(User).where(User.active.is_(True))).unique().all()
    entitled = []
    for user in candidates:
        if user.role in {"talco_admin", "talco_staff"}:
            continue
        if getattr(user, "ledger_access_configured", False):
            if invoice.party_id not in {g.party_id for g in user.ledger_access}:
                continue
        elif user.role == "lessee":
            if user.party_id != invoice.party_id or user.tannery_id != invoice.tannery_id:
                continue
        elif user.role in {"member", "member_staff"}:
            if user.tannery_id != invoice.tannery_id:
                continue
        else:
            continue
        visible = session.scalar(lease_window_filter(
            select(Invoice.id).where(Invoice.id == invoice.id), Invoice, user))
        if visible is not None:
            entitled.append(user)
    return entitled


def _already_sent(session: Session, user_id: int, invoice_id: int) -> bool:
    return session.scalar(select(Notification.id).where(
        Notification.user_id == user_id, Notification.kind == KIND,
        Notification.entity_type == "invoice", Notification.entity_id == invoice_id)) is not None


def posted_invoices(session: Session, batch: ImportBatch) -> list[Invoice]:
    """Invoices this batch posted, resolved the same way the importer resolves them."""
    from app.services.import_pipeline import _find_invoice

    found = {}
    for row in session.scalars(select(StagingRow).where(
            StagingRow.batch_id == batch.id, StagingRow.status == "posted")):
        payload = json.loads(row.payload or "{}")
        if payload.get("is_receipt"):
            continue
        invoice = _find_invoice(session, payload)
        if invoice is not None and not invoice.is_cancelled:
            found[invoice.id] = invoice
    return list(found.values())


def dispatch_batch(session: Session, batch: ImportBatch) -> dict:
    """Send every unsent bill in this batch. Returns per-channel counts."""
    result = {"invoices": 0, "recipients": 0, "emailed": 0, "whatsapp": 0,
              "skipped_already_sent": 0, "no_contact": 0}
    link = _portal_link()
    for invoice in posted_invoices(session, batch):
        result["invoices"] += 1
        party = session.get(Party, invoice.party_id)
        head = session.get(ChargeHead, invoice.charge_head_id)
        pdf = None
        for user in recipients_for(session, invoice):
            if _already_sent(session, user.id, invoice.id):
                result["skipped_already_sent"] += 1
                continue
            result["recipients"] += 1
            subject = f"TALCO invoice {invoice.voucher_no} - {head.name if head else 'charges'}"
            body = (f"Dear {party.name if party else 'Member'},\n\n"
                    f"Invoice {invoice.voucher_no} dated "
                    f"{invoice.invoice_date.strftime('%d-%m-%Y')} for "
                    f"Rs. {invoice.gross_amount:,.2f} has been raised.\n\n"
                    f"The invoice is attached. You can also view it in the portal: {link}\n")
            notification = Notification(user_id=user.id, kind=KIND,
                title=f"Invoice {invoice.voucher_no}",
                message=f"Rs. {invoice.gross_amount:,.2f} dated "
                        f"{invoice.invoice_date.strftime('%d-%m-%Y')}",
                link="/portal", entity_type="invoice", entity_id=invoice.id)
            session.add(notification)
            session.flush()
            sent_any = False
            if user.email:
                if pdf is None:
                    pdf = invoice_pdf(session, invoice)
                filename = f"invoice-{invoice.voucher_no.replace('/', '-')}.pdf"
                if send_email(session, user, subject, body, notification.id,
                              attachments=[(filename, "application/pdf", pdf)]):
                    result["emailed"] += 1
                    sent_any = True
            if user.phone:
                # Text and a link only - the PDF never goes over the WhatsApp gateway.
                text = (f"TALCO: invoice {invoice.voucher_no} dated "
                        f"{invoice.invoice_date.strftime('%d-%m-%Y')} for "
                        f"Rs. {invoice.gross_amount:,.2f} is ready. View it here: {link}")
                if send_whatsapp(session, user, text):
                    result["whatsapp"] += 1
                    sent_any = True
            send_push(session, user, notification)
            if not sent_any and not user.email and not user.phone:
                result["no_contact"] += 1
    session.commit()
    return result
