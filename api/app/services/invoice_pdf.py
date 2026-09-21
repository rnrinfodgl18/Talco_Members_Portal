from base64 import b64encode
from html import escape
from decimal import Decimal
from app.models import CompanySetting, Invoice, Party, Receipt, ReceiptAllocation, Tannery, ChargeHead

def _money(value):
    return f"{Decimal(value or 0):,.2f}"

def _service_line(name):
    """Tally ledger names already carry "Raised"; seeded head names do not.
    Append only the suffix the name is missing, so neither doubles up."""
    text = (name or "Treatment Charges").strip()
    low = text.lower()
    if low.endswith("a/c"):
        return text
    return text + (" A/c" if low.endswith("raised") else " Raised A/c")

def _or_dash(value):
    """Bank block falls back to an em dash until the admin stores real values."""
    text = (value or "").strip()
    return escape(text) if text else "\u2014"

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

def _invoice_mobile_styles():
    """Screen-only layout for the in-app phone preview; PDF output stays A4."""
    return """@media screen and (max-width:700px){
body{font-size:8.5px;width:100%;overflow-x:hidden}
.invoice{width:100%;overflow:hidden}
.title{font-size:16px}
.top{grid-template-columns:46% 54%;min-height:0}
.party{min-height:0;padding:5px;overflow-wrap:anywhere}
.party b,.meta strong{font-size:10px;overflow-wrap:anywhere}
.party p{line-height:1.2}
.meta{grid-auto-rows:minmax(34px,auto)}
.meta>div{min-width:0;padding:4px;overflow-wrap:anywhere}
.label{font-size:7px}
.items th,.items td{padding:4px}
.items thead th{height:auto;font-size:9px}
.items tbody tr.main td{height:145px}
.sl{width:5%}.desc{width:55%}.hsn{width:12%}.amt{width:28%}
.charge-lines,.amount-lines{display:grid;grid-template-rows:42px 32px 32px}
.line{display:block;font-size:10px;line-height:1.25;margin:0;overflow-wrap:anywhere}
.line .detail-amount{display:none}
.amount-lines>*{display:block;font-size:10px;font-weight:700;line-height:1.25;text-align:right;white-space:nowrap}
.items tfoot td{font-size:11px}
.items tfoot .amt{white-space:nowrap}
.words,.bottom{grid-template-columns:1fr 1fr;min-height:0}
.words strong{font-size:10px;overflow-wrap:anywhere}
.bank p{font-size:9px;overflow-wrap:anywhere}
.bottom{min-height:100px}
.computer{font-size:8px}
}"""

def _integer_words(n):
    o=["Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"];t=["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]
    def small(v):
        z=[]
        if v>=100:z += [o[v//100],"Hundred"];v%=100
        if v>=20:z += [t[v//10]]+([o[v%10]] if v%10 else [])
        elif v:z += [o[v]]
        return " ".join(z)
    if not n:return "Zero"
    z=[]
    for d,l in ((10000000,"Crore"),(100000,"Lakh"),(1000,"Thousand")):
        if n>=d:q,n=divmod(n,d);z += [small(q),l]
    if n:z += [small(n)]
    return " ".join(z)

def _amount_words(v):
    v=Decimal(v or 0).quantize(Decimal(".01"));r=int(v);p=int((v-r)*100)
    return "Rupees "+_integer_words(r)+((" and "+_integer_words(p)+" Paise") if p else "")+" Only"

def _invoice_styles():
    return "@page{size:A4;margin:9mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#000;font-size:11px;margin:0}.invoice{border:1px solid #555}.title{text-align:center;font-size:18px;font-weight:700;padding:5px;border-bottom:1px solid #555}.top{display:grid;grid-template-columns:1fr 1fr;min-height:66mm;border-bottom:1px solid #555}.seller{border-right:1px solid #555}.party{padding:8px;min-height:31mm}.party+.party{border-top:1px solid #aaa}.party b{display:block;font-size:12.5px}.party p{margin:1px 0;line-height:1.25}.meta{display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:minmax(9.5mm,auto)}.meta>div{padding:6px;border-bottom:1px solid #aaa}.meta>div:nth-child(odd){border-right:1px solid #aaa}.label{display:block;font-size:8.5px;margin-bottom:2px}.meta strong{font-size:12px}.items{width:100%;border-collapse:collapse;table-layout:fixed}.items th,.items td{border-right:1px solid #777;padding:6px;vertical-align:top}.items th:last-child,.items td:last-child{border-right:0}.items thead th{height:11mm;font-size:11px;border-bottom:1px solid #555;text-align:center;font-weight:400}.items tbody tr.main td{height:38mm}.sl{width:7%;text-align:center}.desc{width:68%}.hsn{width:10%;text-align:center}.amt{width:15%;text-align:right}.line{display:flex;justify-content:space-between;gap:8px;font-weight:700;font-size:12px;margin-bottom:7px}.items tfoot td{border-top:1px solid #555;font-size:13px;font-weight:700}.words,.bottom{display:grid;grid-template-columns:1.05fr .95fr;border-top:1px solid #555}.words{min-height:24mm}.bottom{min-height:27mm}.words>div,.bottom>div{padding:5px}.words>div+div,.bottom>div+div{border-left:1px solid #555}.words strong{display:block;margin-top:4px;font-size:12.5px}.bank p{margin:3px 0;font-size:11px}.declaration{display:flex;flex-direction:column;justify-content:flex-end}.signature{display:flex;flex-direction:column;justify-content:space-between;text-align:right}.computer{text-align:center;border-top:1px solid #555;padding:6px;font-size:10px}"

def invoice_html(session, invoice: Invoice) -> str:
    """The invoice as HTML. WeasyPrint prints it, and a phone can display it."""
    c=_company(session);p=session.get(Party,invoice.party_id);t=session.get(Tannery,invoice.tannery_id);h=session.get(ChargeHead,invoice.charge_head_id)
    cn=escape(c.company_name if c else "TALCO-DINTEC");ad=", ".join(filter(None,[c.address,c.city,c.state,c.postal_code])) if c else "";contact=" · ".join(filter(None,[c.phone,c.email])) if c else ""
    buyer=escape(p.name if p else "");prem=escape(t.name if t else "");gst=escape(t.gstin or "Not provided") if t else "Not provided";desc=escape(_service_line(h.name if h else None))
    bank_name=_or_dash(c.bank_name if c else None);bank_ac=_or_dash(c.bank_account_number if c else None)
    branch_ifsc=" / ".join(x for x in [(c.bank_branch or "").strip() if c else "", (c.bank_ifsc or "").strip() if c else ""] if x)
    branch_ifsc=escape(branch_ifsc) if branch_ifsc else "\u2014"
    html=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>{_invoice_styles()}{_invoice_mobile_styles()}</style></head><body><div class="invoice"><div class="title">Tax Invoice</div>
<div class="top"><div class="seller"><div class="party"><b>{cn}</b><p>{escape(ad)}</p><p>GSTIN: {escape(c.gstin or "") if c else ""}</p><p>{escape(contact)}</p><p>State Name: Tamil Nadu, Code: 33</p></div><div class="party"><span class="label">Buyer (Bill to)</span><b>{buyer}</b><p>{prem}</p><p>GSTIN/UIN: {gst}</p><p>State Name: Tamil Nadu, Code: 33</p></div></div>
<div class="meta"><div><span class="label">Invoice No.</span><strong>{escape(invoice.voucher_no)}</strong></div><div><span class="label">Dated</span><strong>{invoice.invoice_date.strftime("%d-%b-%Y")}</strong></div><div><span class="label">Delivery Note</span></div><div><span class="label">Mode/Terms of Payment</span></div><div><span class="label">Reference No. &amp; Date.</span></div><div><span class="label">Other References</span></div><div><span class="label">Buyer's Order No.</span></div><div><span class="label">Dated</span></div><div><span class="label">Dispatch Doc No.</span></div><div><span class="label">Delivery Note Date</span></div><div><span class="label">Dispatched through</span></div><div><span class="label">Destination</span></div></div></div>
<table class="items"><thead><tr><th class="sl">Sl<br><span class="label">No.</span></th><th class="desc">Description of<br>Services</th><th class="hsn">HSN/SAC</th><th class="amt">Amount</th></tr></thead><tbody><tr class="main"><td class="sl">1</td><td class="desc"><div class="charge-lines"><div class="line"><span>{desc}</span><span class="detail-amount">₹ {_money(invoice.base_amount)}</span></div><div class="line"><span>OUTPUT CGST A/C</span><span class="detail-amount">₹ {_money(invoice.cgst)}</span></div><div class="line"><span>OUTPUT SGST A/C</span><span class="detail-amount">₹ {_money(invoice.sgst)}</span></div></div></td><td class="hsn">9994</td><td class="amt"><div class="amount-lines"><span>₹ {_money(invoice.base_amount)}</span><span>₹ {_money(invoice.cgst)}</span><span>₹ {_money(invoice.sgst)}</span></div></td></tr></tbody><tfoot><tr><td></td><td colspan="2" style="text-align:right">Total</td><td class="amt">₹ {_money(invoice.gross_amount)}</td></tr></tfoot></table>
<div class="words"><div><span class="label">Amount Chargeable (in words)</span><strong>{escape(_amount_words(invoice.gross_amount))}</strong></div><div class="bank"><span class="label">Company's Bank Details</span><p><b>Bank Name:</b> {bank_name}</p><p><b>A/c No.:</b> {bank_ac}</p><p><b>Branch &amp; IFSC:</b> {branch_ifsc}</p><p><b>for {cn}</b></p></div></div><div class="bottom"><div class="declaration"><span class="label">Declaration</span><p>We declare that this invoice shows the actual service charges and that all particulars are true and correct.</p></div><div class="signature"><b>for {cn}</b><span>Authorised Signatory</span></div></div><div class="computer">This is a Computer Generated Invoice</div></div></body></html>"""
    return html


def invoice_pdf(session, invoice: Invoice) -> bytes:
    from weasyprint import HTML

    return HTML(string=invoice_html(session, invoice)).write_pdf()

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
