import {useEffect,useState} from "react";
import {api} from "./api";

type LogRow={id:number;recipient:string;email:string|null;destination:string|null;channel:string;status:string;detail:string|null;attempted_at:string|null;notification_id:number|null;kind:string|null;subject:string|null;entity_type:string|null;entity_id:number|null};
type LogPage={total:number;page:number;pages:number;page_size:number;items:LogRow[]};
type Options={channels:string[];statuses:string[];kinds:string[]};
type ChannelResult={status:string;detail:string|null;destination:string|null;attempted_at:string|null};
type Recipient={user_id:number;recipient:string;email:string|null;phone:string|null;channels:Record<string,ChannelResult>;read:boolean;read_at:string|null};
type Detail={entity_type:string;entity_id:number;subject:string|null;recipients:Recipient[];totals:Record<string,number>};

const when=(value:string|null)=>value?new Date(value).toLocaleString("en-IN"):"—";
const statusClass=(status:string)=>status==="sent"?"bg-emerald-50 text-emerald-700"
  :status==="failed"?"bg-rose-50 text-rose-700":"bg-slate-100 text-slate-600";
const label=(value:string|null)=>value?value.charAt(0).toUpperCase()+value.slice(1):"—";

function Pill({status}:{status:string}){
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${statusClass(status)}`}>{status}</span>;
}

function DrillDown({entityType,entityId,onClose}:{entityType:string;entityId:number;onClose:()=>void}){
  const [detail,setDetail]=useState<Detail|null>(null),[error,setError]=useState("");
  useEffect(()=>{setDetail(null);setError("");
    api(`/api/notifications/deliveries/${entityType}/${entityId}`).then(setDetail).catch(e=>setError((e as Error).message));
  },[entityType,entityId]);
  const channels=["email","whatsapp","push"];
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 sm:items-center sm:p-6">
    <div className="max-h-[88vh] w-full max-w-4xl overflow-auto rounded-t-2xl bg-white p-5 sm:rounded-2xl sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{entityType==="circular"?"Circular":"Invoice"} #{entityId}</p>
          <h2 className="text-xl font-bold">{detail?.subject??"Delivery detail"}</h2></div>
        <button onClick={onClose} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold">Close</button>
      </div>
      {error&&<p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      {!detail&&!error&&<p className="mt-6 text-sm text-slate-500">Loading…</p>}
      {detail&&<>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[["Recipients",detail.totals.recipients],["Read",detail.totals.read],["Unread",detail.totals.unread],
            ["Email sent",detail.totals.email_sent],["Email failed",detail.totals.email_failed],
            ["WhatsApp sent",detail.totals.whatsapp_sent],["WhatsApp failed",detail.totals.whatsapp_failed],
            ["Push sent",detail.totals.push_sent]].map(([text,value])=>
            <div key={text as string} className="rounded-lg border border-slate-200 p-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{text}</p>
              <p className="text-lg font-bold">{value as number}</p></div>)}
        </div>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full min-w-[40rem] text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2.5">Recipient</th>{channels.map(c=><th key={c} className="px-3 py-2.5">{label(c)}</th>)}<th className="px-3 py-2.5">Read</th>
            </tr></thead>
            <tbody>{detail.recipients.map(row=><tr key={row.user_id} className="border-b border-slate-100 last:border-0 align-top">
              <td className="px-3 py-3"><b className="block">{row.recipient}</b>
                <span className="text-xs text-slate-500">{row.email??row.phone??"no contact on file"}</span></td>
              {channels.map(c=><td key={c} className="px-3 py-3">
                {row.channels[c]?<><Pill status={row.channels[c].status}/>
                  {row.channels[c].detail&&<span className="mt-1 block text-xs text-rose-600">{row.channels[c].detail}</span>}
                  <span className="mt-1 block text-[11px] text-slate-400">{when(row.channels[c].attempted_at)}</span></>
                  :<span className="text-xs text-slate-400">not attempted</span>}</td>)}
              <td className="px-3 py-3">{row.read
                ?<span className="text-xs font-semibold text-emerald-700">Read<span className="block font-normal text-slate-400">{when(row.read_at)}</span></span>
                :<span className="text-xs font-semibold text-amber-700">Unread</span>}</td>
            </tr>)}</tbody>
          </table>
          {!detail.recipients.length&&<p className="p-6 text-center text-sm text-slate-500">This item has not been sent to anyone yet.</p>}
        </div>
      </>}
    </div>
  </div>;
}

export default function NotificationLogPage(){
  const [data,setData]=useState<LogPage|null>(null),[options,setOptions]=useState<Options|null>(null);
  const [channel,setChannel]=useState(""),[status,setStatus]=useState(""),[kind,setKind]=useState("");
  const [search,setSearch]=useState(""),[query,setQuery]=useState(""),[page,setPage]=useState(1);
  const [error,setError]=useState(""),[open,setOpen]=useState<{type:string;id:number}|null>(null);
  useEffect(()=>{api("/api/notifications/delivery-log/filters").then(setOptions).catch(()=>{})},[]);
  useEffect(()=>{const timer=setTimeout(()=>{setQuery(search);setPage(1)},300);return()=>clearTimeout(timer)},[search]);
  useEffect(()=>{setError("");
    const params=new URLSearchParams({page:String(page),page_size:"50"});
    if(channel)params.set("channel",channel);
    if(status)params.set("status",status);
    if(kind)params.set("kind",kind);
    if(query)params.set("search",query);
    api(`/api/notifications/delivery-log?${params}`).then(setData).catch(e=>setError((e as Error).message));
  },[channel,status,kind,query,page]);
  const reset=()=>{setChannel("");setStatus("");setKind("");setSearch("");setPage(1)};
  const select=(value:string,setter:(x:string)=>void)=>{setter(value);setPage(1)};
  const filterClass="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm";
  return <section className="p-5 lg:p-8">
    <h1 className="text-2xl font-bold lg:text-3xl">Notification log</h1>
    <p className="mt-1 text-sm text-slate-500">Every email, WhatsApp and push attempt. Open a row to see who an item reached and who has read it.</p>
    <div className="mt-5 flex flex-wrap gap-3">
      <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search recipient, number or subject" className={`${filterClass} min-w-[14rem] flex-1`}/>
      <select value={channel} onChange={e=>select(e.target.value,setChannel)} className={filterClass}>
        <option value="">All channels</option>{options?.channels.map(x=><option key={x} value={x}>{label(x)}</option>)}</select>
      <select value={status} onChange={e=>select(e.target.value,setStatus)} className={filterClass}>
        <option value="">All statuses</option>{options?.statuses.map(x=><option key={x} value={x}>{label(x)}</option>)}</select>
      <select value={kind} onChange={e=>select(e.target.value,setKind)} className={filterClass}>
        <option value="">All types</option>{options?.kinds.map(x=><option key={x} value={x}>{label(x)}</option>)}</select>
      <button onClick={reset} className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold">Clear</button>
    </div>
    {error&&<p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {data&&<p className="mt-4 text-sm text-slate-500">{data.total} attempt{data.total===1?"":"s"}{data.pages>1?` · page ${data.page} of ${data.pages}`:""}</p>}
    <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-[52rem] text-sm">
        <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
          <th className="px-3 py-3">When</th><th className="px-3 py-3">Recipient</th><th className="px-3 py-3">Subject</th>
          <th className="px-3 py-3">Channel</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Detail</th><th className="px-3 py-3"></th>
        </tr></thead>
        <tbody>{(data?.items??[]).map(row=><tr key={row.id} className="border-b border-slate-100 last:border-0">
          <td className="whitespace-nowrap px-3 py-3 text-slate-600">{when(row.attempted_at)}</td>
          <td className="px-3 py-3"><b className="block">{row.recipient}</b><span className="text-xs text-slate-500">{row.destination??row.email??"—"}</span></td>
          <td className="px-3 py-3">{row.subject??"—"}<span className="block text-xs text-slate-500">{label(row.kind)}</span></td>
          <td className="px-3 py-3">{label(row.channel)}</td>
          <td className="px-3 py-3"><Pill status={row.status}/></td>
          <td className="max-w-xs px-3 py-3 text-xs text-slate-500">{row.detail??"—"}</td>
          <td className="px-3 py-3">{row.entity_type&&row.entity_id
            ?<button onClick={()=>setOpen({type:row.entity_type!,id:row.entity_id!})} className="whitespace-nowrap rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold">View recipients</button>
            :null}</td>
        </tr>)}</tbody>
      </table>
      {data&&!data.items.length&&<p className="p-8 text-center text-sm text-slate-500">No delivery attempts match these filters.</p>}
    </div>
    {data&&data.pages>1&&<div className="mt-4 flex items-center gap-3">
      <button disabled={data.page<=1} onClick={()=>setPage(p=>p-1)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40">Previous</button>
      <button disabled={data.page>=data.pages} onClick={()=>setPage(p=>p+1)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-40">Next</button>
    </div>}
    {open&&<DrillDown entityType={open.type} entityId={open.id} onClose={()=>setOpen(null)}/>}
  </section>;
}
