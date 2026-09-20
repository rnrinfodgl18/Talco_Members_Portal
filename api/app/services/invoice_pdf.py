from base64 import b64encode
from html import escape
from decimal import Decimal
from app.models import CompanySetting, Invoice, Party, Receipt, ReceiptAllocation, Tannery, ChargeHead

def _money(value):
    return f"{Decimal(value or 0):,.2f}"

def _company(session):
    return session.get(CompanySetting, 1)

def _header(company):
    address = ", ".join(filter(None, [company.address, company.city, company.state, company.postal_code])) if company else ""
    logo = ""
    if company and company.logo_data:
        logo = f'<img class="logo" src="data:{company.logo_mime or "image/png"};base64,{b64encode(company.logo_data).decode()}">'
    name = escape(company.company_name if company else "TALCO-DINTEC")
    gst = escape(company.gstin or "") if company else ""
    contact = " · ".join(filter(None, [company.phone, company.email])) if company else ""
    return f'<header>{logo}<div><h1>{name}</h1><p>{escape(address)}</p><p>GSTIN: {gst} &nbsp; {escape(contact)}</p></div></header>'

def _styles():
    return """@page{size:A4;margin:11mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#111;font-size:10.5px;margin:0}.sheet{border:1px solid #111;min-height:268mm}header{display:flex;gap:12px;align-items:center;justify-content:center;text-align:center;padding:10px;border-bottom:1px solid #111}.logo{max-width:85px;max-height:55px}h1{font-size:17px;margin:0 0 3px}p{margin:2px 0}.title{text-align:center;font-size:16px;font-weight:700;padding:6px;border-bottom:1px solid #111}.grid{display:grid;grid-template-columns:1fr 1fr}.cell{padding:7px;border-bottom:1px solid #111}.cell:nth-child(odd){border-right:1px solid #111}.label{font-size:9px;color:#444}.strong{font-size:12px;font-weight:700}table{width:100%;border-collapse:collapse}th,td{border:1px solid #111;padding:7px;vertical-align:top}th{font-weight:700;text-align:center}.num{text-align:right;white-space:nowrap}.center{text-align:center}.total td{font-size:12px;font-weight:700}.notes{padding:8px;border-top:1px solid #111}.footer{display:grid;grid-template-columns:1.25fr .75fr;border-top:1px solid #111}.footer>div{padding:8px;min-height:82px}.footer>div+div{border-left:1px solid #111;text-align:right}.sign{padding-top:45px;font-weight:700}.computer{text-align:center;padding:5px;border-top:1px solid #111;font-size:9px}"""

def invoice_pdf(session, invoice: Invoice) -> bytes:
    from weasyprint import HTML
    company=_company(session); party=session.get(Party,invoice.party_id); tannery=session.get(Tannery,invoice.tannery_id); head=session.get(ChargeHead,invoice.charge_head_id)
    html=f'''<!doctype html><html><head><meta charset="utf-8"><style>{_styles()}</style></head><body><div class="sheet">{_header(company)}
    <div class="title">TAX INVOICE</div><div class="grid"><div class="cell"><span class="label">Buyer (Bill to)</span><div class="strong">{escape(party.name if party else "")}</div><p>{escape(tannery.name if tannery else "")}</p><p>GSTIN: {escape(tannery.gstin or "Not provided") if tannery else "Not provided"}</p></div>
    <div class="cell"><p><b>Invoice No:</b> {escape(invoice.voucher_no)}</p><p><b>Dated:</b> {invoice.invoice_date.strftime("%d-%m-%Y")}</p><p><b>Financial Year:</b> {escape(invoice.fy)}</p></div></div>
    <table><thead><tr><th style="width:8%">Sl No.</th><th>Description of Services</th><th style="width:15%">HSN/SAC</th><th style="width:22%">Amount</th></tr></thead><tbody>
    <tr><td class="center">1</td><td><b>{escape(head.name if head else "Treatment Charges")}</b><br><span class="label">Effluent treatment service charges</span></td><td class="center">9994</td><td class="num">₹ {_money(invoice.base_amount)}</td></tr>
    <tr><td></td><td class="num">CGST</td><td></td><td class="num">₹ {_money(invoice.cgst)}</td></tr><tr><td></td><td class="num">SGST</td><td></td><td class="num">₹ {_money(invoice.sgst)}</td></tr>
    <tr class="total"><td></td><td colspan="2">Total</td><td class="num">₹ {_money(invoice.gross_amount)}</td></tr></tbody></table>
    <div class="notes"><b>Amount chargeable (in figures):</b> ₹ {_money(invoice.gross_amount)}<br><span class="label">E. &amp; O.E.</span></div>
    <div class="footer"><div><b>Declaration</b><p>We declare that this invoice shows the actual service charges and that all particulars are true and correct.</p></div><div><b>For {escape(company.short_name if company else "TALCO-DINTEC")}</b><div class="sign">Authorised Signatory</div></div></div>
    <div class="computer">This is a Computer Generated Invoice</div></div></body></html>'''
    return HTML(string=html).write_pdf()

def receipt_pdf(session, receipt: Receipt) -> bytes:
    from weasyprint import HTML
    company=_company(session); party=session.get(Party,receipt.party_id); tannery=session.get(Tannery,receipt.tannery_id)
    allocations=list(session.scalars(__import__("sqlalchemy").select(ReceiptAllocation).where(ReceiptAllocation.receipt_id==receipt.id)))
    refs=", ".join(a.bill_ref for a in allocations) or "On Account"
    html=f'''<!doctype html><html><head><meta charset="utf-8"><style>{_styles()}</style></head><body><div class="sheet">{_header(company)}
    <div class="title">BANK RECEIPT VOUCHER</div><div class="grid"><div class="cell"><b>Voucher No:</b> {escape(receipt.voucher_no)}</div><div class="cell"><b>Dated:</b> {receipt.receipt_date.strftime("%d-%m-%Y")}</div></div>
    <table><thead><tr><th>Particulars</th><th style="width:26%">Amount</th></tr></thead><tbody>
    <tr><td><div class="strong">{escape(party.name if party else "")}</div><p>{escape(tannery.name if tannery else "")}</p><p><b>Against Reference:</b> {escape(refs)}</p><p><b>On Account Of:</b> Payment received towards CETP charges.</p></td><td class="num strong">₹ {_money(receipt.amount)}</td></tr>
    <tr class="total"><td>Total</td><td class="num">₹ {_money(receipt.amount)}</td></tr></tbody></table>
    <div class="notes"><b>Amount received:</b> ₹ {_money(receipt.amount)}<br><span class="label">Payment mode: Bank / Account receipt</span></div>
    <div class="footer"><div><b>Received from</b><p>{escape(party.name if party else "")}</p></div><div><b>For {escape(company.short_name if company else "TALCO-DINTEC")}</b><div class="sign">Authorised Signatory</div></div></div>
    <div class="computer">This is a Computer Generated Receipt Voucher</div></div></body></html>'''
    return HTML(string=html).write_pdf()
