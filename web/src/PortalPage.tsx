import { useEffect, useState } from "react";
import { api, apiBlob, canPreviewPdfInline, fieldClass, saveBlob } from "./api";
import { StatementTable, HistoryTable } from "./LedgerTable";
import LedgerPrint from "./LedgerPrint";
import { StatementEntry, HistoryEntry, balanceLabel, formatDate, formatMoney } from "./ledgerPresentation";

type Account={id:number;code:string;name:string;relationship_role:string|null;tanneries:{name:string;role:string}[]};
type Dashboard={party:{id:number;code:string;name:string};outstanding:string;opening_balance:string;opening_date:string|null;scope_note:string|null;last_bill:{voucher_no:string;date:string;amount:string}|null};
type InvoiceDetail={id:number;voucher_no:string;fy:string;date:string;account:string;account_code:string;tannery:string;tannery_gstin:string|null;charge_head:string;base:string;cgst:string;sgst:string;gross:string;revision_count:number;revisions:{date:string;reason:string|null;revised_by:string|null}[]};
type Tab="statement"|"invoices"|"receipts";
const relationship=(role:string)=>({owner:"Owner",lessee:"Lessee",account_holder:"Account holder",staff:"Staff",member_staff:"Staff"}[role]??role);
const sourceDisplay=(value:string)=>value.startsWith("legacy-")?"Not provided":value;

export default function PortalPage({initialAccountId,initialTab="statement"}:{initialAccountId?:number;initialTab?:Tab}){
 const [accounts,setAccounts]=useState<Account[]>([]),[selected,setSelected]=useState("");
 const [company,setCompany]=useState<any>({});
 const [dashboard,setDashboard]=useState<Dashboard|null>(null),[ledger,setLedger]=useState<StatementEntry[]>([]),[history,setHistory]=useState<HistoryEntry[]>([]);
 const [error,setError]=useState(""),[loading,setLoading]=useState(true),[accountsLoading,setAccountsLoading]=useState(true);
 const [version,setVersion]=useState(0),[tab,setTab]=useState<Tab>(initialTab),[invoice,setInvoice]=useState<InvoiceDetail|null>(null),[invoicePdfUrl,setInvoicePdfUrl]=useState(""),[invoiceBlob,setInvoiceBlob]=useState<Blob|null>(null);
 useEffect(()=>{api("/api/settings/public").then(setCompany).catch(()=>{})},[]);
 useEffect(()=>setTab(initialTab),[initialTab]);
 useEffect(()=>{let active=true;setAccountsLoading(true);setError("");api("/api/portal/accounts").then((items:Account[])=>{if(!active)return;setAccounts(items);setSelected(current=>items.some(item=>String(item.id)===current)?current:String(items.find(item=>item.id===initialAccountId)?.id??items[0]?.id??""))}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setAccountsLoading(false)});return()=>{active=false}},[initialAccountId,version]);
 useEffect(()=>{if(!selected){setDashboard(null);setLedger([]);return}let active=true;setLoading(true);setError("");setDashboard(null);setLedger([]);setHistory([]);const query="?party_id="+selected;Promise.all([api("/api/portal/dashboard"+query),api("/api/portal/ledger"+query),tab==="statement"?Promise.resolve([]):api("/api/portal/"+tab+query)]).then(([summary,entries,records])=>{if(active){setDashboard(summary);setLedger(entries);setHistory(records)}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[selected,tab,version]);
 const account=accounts.find(item=>String(item.id)===selected);
 const premises=account?[...new Set(account.tanneries.map(item=>item.name+" ("+relationship(item.role)+")"))].join(" / "):"";
 const printView=(kind:"ledger"|"invoice")=>{document.body.dataset.print=kind;const cleanup=()=>{delete document.body.dataset.print};window.addEventListener("afterprint",cleanup,{once:true});window.print();setTimeout(cleanup,1000)};
 const showInvoice=async(id:number)=>{try{setError("");
   const [detail,blob]=await Promise.all([api("/api/portal/invoices/"+id),apiBlob(`/api/portal/invoices/${id}/pdf`)]);
   setInvoice(detail);setInvoiceBlob(blob);
   // Android has no iframe PDF viewer, so on a phone the file is handed to
   // the system viewer instead of being framed in a panel that stays blank.
   if(canPreviewPdfInline()){if(invoicePdfUrl)URL.revokeObjectURL(invoicePdfUrl);setInvoicePdfUrl(URL.createObjectURL(blob))}
   else saveBlob(blob,`TALCO-Invoice-${sourceDisplay(detail.voucher_no)}.pdf`);
 }catch(e){setError(`Invoice PDF preview failed: ${(e as Error).message}`)}};
 const closeInvoice=()=>{if(invoicePdfUrl)URL.revokeObjectURL(invoicePdfUrl);setInvoicePdfUrl("");setInvoiceBlob(null);setInvoice(null)};
 const printInvoice=()=>{const frame=document.getElementById("official-invoice-preview") as HTMLIFrameElement|null;frame?.contentWindow?.focus();frame?.contentWindow?.print()};
 const showReceipt=async(id:number)=>{try{setError("");
   const blob=await apiBlob(`/api/portal/receipts/${id}/pdf`);
   // window.open after an await is treated as an unrequested popup on mobile
   // and silently blocked, so the file is saved instead.
   if(canPreviewPdfInline()){const url=URL.createObjectURL(blob);
     const opened=window.open(url,"_blank");
     if(!opened)saveBlob(blob,`TALCO-Receipt-${id}.pdf`);
     setTimeout(()=>URL.revokeObjectURL(url),60000);
   } else saveBlob(blob,`TALCO-Receipt-${id}.pdf`);
 }catch(e){setError(`Receipt PDF failed: ${(e as Error).message}`)}};
 const downloadInvoice=async()=>{if(!invoice)return;try{setError("");
   const blob=invoiceBlob??await apiBlob(`/api/portal/invoices/${invoice.id}/pdf`);
   saveBlob(blob,`TALCO-Invoice-${sourceDisplay(invoice.voucher_no)}.pdf`);
 }catch(e){setError(`PDF download failed: ${(e as Error).message}`)}};
 return <section className="ledger-print mx-auto max-w-7xl p-5 lg:p-8">
  <LedgerPrint company={company} accountCode={dashboard?.party.code} accountName={account?.name} premises={premises} rows={ledger} closing={dashboard?.outstanding}/>
  <header><p className="text-xs uppercase tracking-widest text-[var(--erp-primary)]">Bills & payments</p><h2 className="mt-2 text-3xl font-bold">Account Statement</h2><p className="mt-2 text-slate-400">See your bills, payments and the balance after each entry.</p></header>
  <label className="no-print mt-5 block max-w-2xl text-sm text-slate-400">Select account<select className={fieldClass} disabled={accountsLoading} value={selected} onChange={e=>{setSelected(e.target.value);setTab("statement")}}>{accounts.length===0&&<option value="">No assigned accounts</option>}{accounts.map(item=><option key={item.id} value={item.id}>{item.name} · {item.code}{item.relationship_role?" ("+relationship(item.relationship_role)+")":""}</option>)}</select></label>
  {premises&&<p className="mt-3 text-sm text-slate-400">{premises}</p>}
  {error&&<p role="alert" className="no-print mt-5 text-rose-300">{error} <button className="underline" onClick={()=>setVersion(value=>value+1)}>Retry</button></p>}
  {accountsLoading?<p className="mt-6 text-slate-400">Loading accounts…</p>:accounts.length===0&&!error?<p className="mt-6 rounded-xl border border-slate-800 p-6 text-slate-400">No accounts are assigned to this login. Contact the TALCO administrator.</p>:selected&&loading?<p className="mt-6 text-slate-400">Loading statement…</p>:dashboard&&<>
   <div className="mt-6 grid gap-4 md:grid-cols-3"><Card label={balanceLabel(dashboard.outstanding)} value={formatMoney(dashboard.outstanding)} tone={Number(dashboard.outstanding)<0?"credit":Number(dashboard.outstanding)>0?"due":undefined} detail="Based on the entries in this statement"/><Card label="Opening balance" value={dashboard.opening_date?formatMoney(dashboard.opening_balance):"Not entered"} detail={dashboard.opening_date?balanceLabel(dashboard.opening_balance)+" · "+formatDate(dashboard.opening_date):"No starting balance has been recorded"}/><Card label="Latest bill" value={dashboard.last_bill?formatMoney(dashboard.last_bill.amount):"No bills yet"} detail={dashboard.last_bill?formatDate(dashboard.last_bill.date):"In this statement"}/></div>
   {dashboard.scope_note&&<p className="mt-4 text-sm text-amber-200">{dashboard.scope_note}</p>}
   {dashboard.opening_date?<p className="mt-4 text-sm text-slate-400">Statement starts on {formatDate(dashboard.opening_date)}. Earlier entries are available under All bills and All payments.</p>:!dashboard.scope_note&&<p className="no-print mt-4 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-200">No opening balance has been entered. The balance shown uses only the bills and payments recorded here.</p>}
   <nav aria-label="Statement views" className="no-print mb-4 mt-6 flex flex-wrap gap-2">{([["statement","Statement"],["invoices","All bills"],["receipts","All payments"]] as [Tab,string][]).map(([key,label])=><button key={key} aria-current={tab===key?"page":undefined} onClick={()=>setTab(key)} className={"rounded-xl px-4 py-2 "+(tab===key?"bg-[var(--erp-primary)] font-bold text-slate-950":"bg-slate-800 text-slate-300")}>{label}</button>)}{tab==="statement"&&<button onClick={()=>printView("ledger")} className="ui-action ui-action-print">Print / Save PDF</button>}</nav>
   {tab==="statement"?<><p className="no-print mb-4 text-sm text-slate-400">Charges increase the amount due. Payments reduce it. Extra payments appear as advance / credit.</p><StatementTable rows={ledger}/></>:<HistoryTable rows={history} kind={tab==="invoices"?"invoice":"receipt"} onView={tab==="invoices"?showInvoice:showReceipt}/>}
  </>}
  {invoice&&<div className="no-print fixed inset-0 z-50 flex flex-col bg-slate-950/90 p-2 sm:p-4">
   <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-2 rounded-t-xl bg-white p-3 shadow-xl">
    <div className="mr-auto min-w-0"><b className="block truncate text-slate-900">Tax Invoice · {sourceDisplay(invoice.voucher_no)}</b><span className="text-xs text-slate-500">{invoice.account} · {formatDate(invoice.date)}</span></div>
    <button onClick={downloadInvoice} className="ui-action ui-action-print">Download PDF</button>
    {invoicePdfUrl&&<button onClick={printInvoice} className="ui-action ui-action-print">Print Invoice</button>}
    <button onClick={closeInvoice} className="btn btn-md btn-secondary">Close</button>
   </div>
   <div className="mx-auto min-h-0 w-full max-w-5xl flex-1 overflow-hidden rounded-b-xl bg-slate-200 shadow-xl">
    {invoicePdfUrl
     ?<iframe id="official-invoice-preview" title="Official tax invoice preview" src={invoicePdfUrl} className="h-full min-h-[70vh] w-full border-0 bg-white"/>
     :invoiceBlob
      ?<div className="grid h-full min-h-[40vh] place-items-center p-6 text-center"><div>
        <p className="font-semibold text-slate-800">The invoice has been saved to this device.</p>
        <p className="mt-2 text-sm text-slate-600">Phones cannot show a PDF inside the app, so open it from your Downloads or notification tray.</p>
        <button onClick={downloadInvoice} className="ui-action ui-action-print mt-4">Save it again</button>
       </div></div>
      :<div className="grid h-full place-items-center text-slate-600">Preparing official invoice…</div>}
   </div>
  </div>}
 </section>;
}

function Card({label,value,detail,tone}:{label:string;value:string;detail:string;tone?:"credit"|"due"}){
 return <div className={"rounded-2xl border bg-slate-900 p-5 "+(tone==="credit"?"border-emerald-400/30":tone==="due"?"border-amber-400/30":"border-slate-800")}><p className="text-sm text-slate-400">{label}</p><p className={"mt-2 text-2xl font-bold "+(tone==="credit"?"text-emerald-700":tone==="due"?"text-rose-700":"text-slate-100")}>{value}</p><p className="mt-2 text-xs text-slate-500">{detail}</p></div>
}
