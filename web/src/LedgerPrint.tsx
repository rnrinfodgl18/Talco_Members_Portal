import {StatementEntry,balanceLabel,formatDate,formatMoney,sourceNumber,transactionLabel} from "./ledgerPresentation";
type Company={company_name?:string;address?:string|null;city?:string|null;state?:string|null;postal_code?:string|null;gstin?:string|null;phone?:string|null;email?:string|null};
export default function LedgerPrint({company,accountCode,accountName,premises,rows,closing}:{company:Company;accountCode?:string;accountName?:string;premises:string;rows:StatementEntry[];closing?:string}){
 const debits=rows.reduce((sum,row)=>sum+Number(row.debit),0),credits=rows.reduce((sum,row)=>sum+Number(row.credit),0);
 const period=rows.length?`${formatDate(rows[0].date)} to ${formatDate(rows[rows.length-1].date)}`:"No entries";
 return <div className="ledger-paper print-only">
  <header className="ledger-letterhead"><h1>{company.company_name||"TALCO-DINTEC CETP"}</h1><p>{[company.address,company.city,company.state,company.postal_code].filter(Boolean).join(", ")}</p><p>{company.gstin&&`GSTIN: ${company.gstin}`}{company.phone&&` · Phone: ${company.phone}`}{company.email&&` · ${company.email}`}</p></header>
  <div className="ledger-print-title"><h2>Ledger Account</h2><p>{period}</p></div>
  <div className="ledger-party"><div><small>Account</small><b>{accountName}</b><span>{accountCode}</span></div><div><small>Tannery / relationship</small><b>{premises||"—"}</b></div></div>
  <table className="formal-ledger-table"><thead><tr><th>Date</th><th>Particulars</th><th>Vch Type</th><th>Vch No.</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{rows.map(row=><tr key={`${row.kind}-${row.id}`}><td>{formatDate(row.date)}</td><td>{transactionLabel(row.kind,row.description,row.is_step)}</td><td>{row.kind==="invoice"?"Sales":row.kind==="receipt"?"Receipt":"Opening"}</td><td>{row.kind==="opening"?"—":sourceNumber(row.voucher_no)||"Not provided"}</td><td>{Number(row.debit)?formatMoney(row.debit):""}</td><td>{Number(row.credit)?formatMoney(row.credit):""}</td></tr>)}</tbody><tfoot><tr><th colSpan={4}>Current totals</th><th>{formatMoney(String(debits))}</th><th>{formatMoney(String(credits))}</th></tr><tr className="closing-row"><th colSpan={4}>Closing Balance · {balanceLabel(closing||"0")}</th><th colSpan={2}>{formatMoney(closing||"0")} {Number(closing||0)<0?"Cr":"Dr"}</th></tr></tfoot></table>
  <footer className="ledger-print-footer"><p>This is a computer-generated ledger statement.</p><div><span>Prepared by</span><span>Authorised Signatory</span></div></footer>
 </div>
}
