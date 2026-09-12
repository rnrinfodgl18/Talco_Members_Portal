from html import escape
from app.models import CompanySetting, Invoice, Party, Tannery, ChargeHead


def invoice_pdf(session, invoice: Invoice) -> bytes:
    from weasyprint import HTML
    company=session.get(CompanySetting,1);party=session.get(Party,invoice.party_id);tannery=session.get(Tannery,invoice.tannery_id);head=session.get(ChargeHead,invoice.charge_head_id)
    address=', '.join(filter(None,[company.address,company.city,company.state,company.postal_code])) if company else ''
    logo=''
    if company and company.logo_data:
        import base64
        logo=f'<img class="logo" src="data:{company.logo_mime or "image/png"};base64,{base64.b64encode(company.logo_data).decode()}">'
    money=lambda x:f'{float(x):,.2f}'
    html=f'''<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:A4;margin:16mm}}body{{font-family:Arial;color:#17202a;font-size:11px}}.head{{display:flex;justify-content:space-between;border-bottom:3px solid #087f5b;padding-bottom:12px}}.logo{{max-width:110px;max-height:70px}}h1{{font-size:20px;margin:0;color:#087f5b}}h2{{text-align:center;letter-spacing:2px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;border:1px solid #ccd5d2;padding:12px}}table{{width:100%;border-collapse:collapse;margin-top:18px}}th,td{{border:1px solid #aebbb7;padding:9px}}th{{background:#e6f4ef;text-align:left}}.num{{text-align:right}}.total{{font-weight:bold;font-size:14px}}.sign{{margin-top:70px;text-align:right}}small{{color:#53615d}}</style></head><body><div class="head"><div>{logo}</div><div style="text-align:right"><h1>{escape(company.company_name if company else 'TALCO-DINTEC')}</h1><div>{escape(address)}</div><div>GSTIN: {escape(company.gstin or '') if company else ''}</div></div></div><h2>TAX INVOICE</h2><div class="grid"><div><small>Bill To</small><b style="display:block;font-size:14px">{escape(party.name)}</b><div>{escape(tannery.name)}</div><div>GSTIN: {escape(tannery.gstin or 'Not provided')}</div></div><div><b>Invoice No:</b> {escape(invoice.voucher_no)}<br><b>Date:</b> {invoice.invoice_date.strftime('%d-%m-%Y')}<br><b>Financial Year:</b> {escape(invoice.fy)}</div></div><table><thead><tr><th>Description</th><th class="num">Taxable Value</th></tr></thead><tbody><tr><td>{escape(head.name)}</td><td class="num">₹ {money(invoice.base_amount)}</td></tr><tr><td>CGST</td><td class="num">₹ {money(invoice.cgst)}</td></tr><tr><td>SGST</td><td class="num">₹ {money(invoice.sgst)}</td></tr><tr class="total"><td>Total</td><td class="num">₹ {money(invoice.gross_amount)}</td></tr></tbody></table><p><small>This is a computer-generated invoice issued from the TALCO member portal.</small></p><div class="sign">For {escape(company.short_name if company else 'TALCO-DINTEC')}<br><br><br>Authorised Signatory</div></body></html>'''
    return HTML(string=html).write_pdf()
