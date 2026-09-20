import {useEffect,useState} from "react";
import {apiUrl,api} from "./api";

type Row={party_id:number;code:string;name:string;tanneries:string[];opening:string;billed:string;collected:string;outstanding:string;last_receipt_date:string|null};
type Report={rows:Row[];totals:Record<string,string>;accounts:number;accounts_with_dues:number};
type SortKey="name"|"opening"|"billed"|"collected"|"outstanding"|"last_receipt_date";

const money=(value:string)=>Number(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2});
const columns:{key:SortKey;label:string;numeric?:boolean}[]=[
  {key:"name",label:"Ledger account"},
  {key:"opening",label:"Opening",numeric:true},
  {key:"billed",label:"Billed",numeric:true},
  {key:"collected",label:"Collected",numeric:true},
  {key:"outstanding",label:"Outstanding",numeric:true},
  {key:"last_receipt_date",label:"Last receipt"}];

export default function ReportsPage(){
  const [report,setReport]=useState<Report|null>(null);
  const [sort,setSort]=useState<SortKey>("outstanding");
  const [direction,setDirection]=useState<"asc"|"desc">("desc");
  const [error,setError]=useState("");
  const [filter,setFilter]=useState("");
  // A plain link would not carry the session token, so fetch and save the blob.
  const download=async()=>{try{
    const response=await fetch(`${apiUrl}/api/reports/outstanding.csv?sort=${sort}&direction=${direction}`);
    if(!response.ok)throw new Error(`Download failed (${response.status})`);
    const url=URL.createObjectURL(await response.blob());
    const link=document.createElement("a");
    link.href=url;link.download="outstanding-summary.csv";link.click();
    URL.revokeObjectURL(url);
  }catch(e){setError((e as Error).message)}};
  useEffect(()=>{setError("");api(`/api/reports/outstanding?sort=${sort}&direction=${direction}`).then(setReport).catch(e=>setError((e as Error).message))},[sort,direction]);
  const choose=(key:SortKey)=>{if(key===sort)setDirection(direction==="asc"?"desc":"asc");else{setSort(key);setDirection(key==="name"?"asc":"desc")}};
  const term=filter.trim().toLowerCase();
  const rows=(report?.rows??[]).filter(row=>!term||row.name.toLowerCase().includes(term)||row.tanneries.some(x=>x.toLowerCase().includes(term)));
  return <section className="p-5 lg:p-8">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-bold lg:text-3xl">Outstanding summary</h1>
        <p className="mt-1 text-sm text-slate-500">Opening balance plus bills raised, less payments received, for every ledger account.</p></div>
      <button onClick={download} className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">Download CSV</button>
    </div>
    {error&&<p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {report&&<>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[["Total outstanding",money(report.totals.outstanding)],["Total billed",money(report.totals.billed)],["Total collected",money(report.totals.collected)],["Accounts with dues",`${report.accounts_with_dues} of ${report.accounts}`]].map(([label,value])=>
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-xl font-bold text-slate-900">{value}</p></div>)}
      </div>
      <input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Filter by ledger or unit name" className="mt-5 w-full rounded-lg border border-slate-300 px-3 py-2.5 sm:max-w-sm"/>
      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[46rem] text-sm">
          <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            {columns.map(column=><th key={column.key} className={column.numeric?"px-3 py-3 text-right":"px-3 py-3"}>
              <button onClick={()=>choose(column.key)} className="font-semibold hover:text-slate-900">{column.label}{sort===column.key?(direction==="asc"?" ▲":" ▼"):""}</button></th>)}
          </tr></thead>
          <tbody>{rows.map(row=><tr key={row.party_id} className="border-b border-slate-100 last:border-0">
            <td className="px-3 py-3"><b className="block text-slate-900">{row.name}</b><span className="text-xs text-slate-500">{row.code}{row.tanneries.length?` · ${row.tanneries.join(", ")}`:""}</span></td>
            <td className="px-3 py-3 text-right tabular-nums">{money(row.opening)}</td>
            <td className="px-3 py-3 text-right tabular-nums">{money(row.billed)}</td>
            <td className="px-3 py-3 text-right tabular-nums">{money(row.collected)}</td>
            <td className={`px-3 py-3 text-right font-bold tabular-nums ${Number(row.outstanding)>0?"text-rose-700":"text-emerald-700"}`}>{money(row.outstanding)}</td>
            <td className="px-3 py-3 text-slate-600">{row.last_receipt_date??"—"}</td></tr>)}
          </tbody>
        </table>
        {!rows.length&&<p className="p-8 text-center text-sm text-slate-500">No ledger accounts match this filter.</p>}
      </div>
    </>}
  </section>;
}
