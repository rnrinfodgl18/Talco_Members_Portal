import { StatementEntry, HistoryEntry, balanceLabel, formatDate, formatMoney, sourceNumber, transactionLabel } from "./ledgerPresentation";

function Reference({value, opening = false}: {value:string;opening?:boolean}) {
  if (opening) return <span className="text-slate-950">-</span>;
  const number = sourceNumber(value);
  return number ? <span className="break-words font-medium text-slate-950">{number}</span> : <span className="text-xs text-slate-950">Not provided</span>;
}
function RunningBalance({value}: {value:string}) {
  return <div className={Number(value) < 0 ? "text-emerald-700" : Number(value) > 0 ? "text-rose-700" : "text-slate-950"}>
    <p className="whitespace-nowrap font-semibold tabular-nums">{formatMoney(value)}</p>
    <p className="mt-1 text-xs font-normal">{balanceLabel(value)}</p>
  </div>;
}
export function StatementTable({rows}: {rows:StatementEntry[]}) {
  const missingNumbers = rows.some(row => row.kind !== "opening" && !sourceNumber(row.voucher_no));
  return <>
    <div className="overflow-x-auto rounded-2xl border border-slate-800 text-slate-950">
      <table className="w-full min-w-[880px] text-left text-sm">
        <thead className="bg-slate-800 text-xs uppercase tracking-wide text-slate-950">
          <tr><th className="px-4 py-4">Date</th><th className="px-4 py-4">Transaction</th><th className="px-4 py-4">Bill / receipt no.</th><th className="px-4 py-4 text-right">Charges</th><th className="px-4 py-4 text-right">Payments / credits</th><th className="px-4 py-4 text-right">Balance after entry</th></tr>
        </thead>
        <tbody>{rows.length === 0 ? <tr><td colSpan={6} className="p-8 text-center text-slate-950">No transactions in this statement.</td></tr> : rows.map(row => <tr key={`${row.kind}-${row.id}`} className={`border-t border-slate-800 ${row.kind === "opening" ? "bg-cyan-400/10" : "bg-slate-900/40 hover:bg-slate-900"}`}>
          <td className="whitespace-nowrap px-4 py-4 text-slate-950">{formatDate(row.date)}</td>
          <td className="px-4 py-4"><span className={`inline-block rounded-lg px-2.5 py-1.5 font-medium ${row.kind === "receipt" ? "bg-emerald-100 text-slate-950" : row.kind === "opening" ? "bg-cyan-100 text-slate-950" : "bg-slate-100 text-slate-950"}`}>{transactionLabel(row.kind, row.description, row.is_step)}</span></td>
          <td className="max-w-[220px] px-4 py-4"><Reference value={row.voucher_no} opening={row.kind === "opening"}/></td>
          <td className="whitespace-nowrap px-4 py-4 text-right text-slate-950 tabular-nums">{Number(row.debit) ? formatMoney(row.debit) : <span className="text-slate-950">-</span>}</td>
          <td className="whitespace-nowrap px-4 py-4 text-right text-slate-950 tabular-nums">{Number(row.credit) ? formatMoney(row.credit) : <span className="text-slate-950">-</span>}</td>
          <td className="px-4 py-4 text-right"><RunningBalance value={row.balance}/></td>
        </tr>)}</tbody>
      </table>
    </div>
    {missingNumbers && <p className="mt-3 text-xs text-slate-950">“Not provided” means the uploaded record did not include a bill or receipt number.</p>}
  </>;
}
export function HistoryTable({rows,kind,onView}: {rows:HistoryEntry[];kind:"invoice"|"receipt";onView?:(id:number)=>void}) {
  return <>
    <div className="overflow-x-auto rounded-2xl border border-slate-800 text-slate-950"><table className="w-full min-w-[640px] text-left text-sm">
      <thead className="bg-slate-800 text-slate-950"><tr><th className="p-4">Date</th><th className="p-4">Transaction</th><th className="p-4">{kind === "invoice" ? "Bill number" : "Receipt number"}</th><th className="p-4 text-right">{kind === "invoice" ? "Bill amount" : "Payment received"}</th>{kind === "invoice" && <th className="no-print p-4 text-right">Invoice</th>}</tr></thead>
      <tbody>{rows.length === 0 ? <tr><td colSpan={kind === "invoice" ? 5 : 4} className="p-8 text-center text-slate-950">No records.</td></tr> : rows.map(row => <tr key={row.id} className="border-t border-slate-800">
        <td className="whitespace-nowrap p-4">{formatDate(row.date)}</td><td className="p-4">{transactionLabel(kind, row.description, row.is_step)}</td><td className="p-4"><Reference value={row.voucher_no}/></td><td className="whitespace-nowrap p-4 text-right tabular-nums">{formatMoney(row.gross ?? row.amount ?? "0")}</td>{kind === "invoice" && <td className="no-print p-4 text-right"><button onClick={() => onView?.(row.id)} className="ui-action ui-action-view">View / Print</button></td>}
      </tr>)}</tbody>
    </table></div>
    {rows.some(row => !sourceNumber(row.voucher_no)) && <p className="mt-3 text-xs text-slate-950">“Not provided” means the uploaded record did not include a bill or receipt number.</p>}
  </>;
}

