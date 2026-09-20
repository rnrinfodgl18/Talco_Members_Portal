import { FormEvent, useEffect, useState } from "react";

type Tannery = {
  id: number; sno: number; name: string; pump_house: string; internal_id: string | null;
  factory_id: string | null; tnpcb_user_id: string | null; gps: string | null; gstin: string | null;
  consent: string | null; original_capacity: string | null; additional_capacity: string | null;
  original_shares: number | null; additional_shares: number | null; phone: string | null; email: string | null;
};
type Pump = {id:number;code:string;name:string};
type Field = Exclude<keyof Tannery, "id">;
type Form = Record<Field, string>;
type QualityIssue = {id:number;tannery_name:string;code:string;detail:string};
const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const groups: {title:string;fields:[Field,string,number?][]}[] = [
  {title:"Tannery details",fields:[["sno","Serial number"],["name","Tannery name",255],["pump_house","Pump house"],["internal_id","Internal tannery ID",100],["factory_id","Factory ID",100]]},
  {title:"Registration & consent",fields:[["gstin","GSTIN",20],["tnpcb_user_id","TNPCB user ID",100],["consent","Consent details",255],["gps","GPS / location",2000]]},
  {title:"Capacity & shares",fields:[["original_capacity","Original capacity",100],["additional_capacity","Additional capacity",100],["original_shares","Original shares"],["additional_shares","Additional shares"]]},
  {title:"Contact details",fields:[["phone","Phone",30],["email","Email",255]]},
];
const blank = ():Form => Object.fromEntries(groups.flatMap(g=>g.fields.map(([key])=>[key,""]))) as Form;
const inputClass="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-slate-100 outline-none focus:border-cyan-400 disabled:text-slate-400";
async function request(path:string, init?:RequestInit) {
  const response=await fetch(`${apiUrl}${path}`,init);
  if(response.status===204)return null;
  const body=await response.json();
  if(!response.ok)throw new Error(typeof body.detail==="string"?body.detail:Array.isArray(body.detail)?body.detail.map((x:{loc:string[];msg:string})=>`${x.loc.slice(1).join(".")}: ${x.msg}`).join("; "):"Request failed. Please try again.");
  return body;
}

export default function MasterPage({canEdit}:{canEdit:boolean}) {
  const [pumps,setPumps]=useState<Pump[]>([]);
  const [rows,setRows]=useState<Tannery[]>([]),[search,setSearch]=useState(""),[pump,setPump]=useState("");
  const [loading,setLoading]=useState(true),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [editor,setEditor]=useState<{mode:"add"|"edit"|"view";row:Tannery|null}|null>(null),[form,setForm]=useState<Form>(blank);
  const [busy,setBusy]=useState(false),[formError,setFormError]=useState(""),[deleting,setDeleting]=useState<Tannery|null>(null);
  const [version,setVersion]=useState(0),[quality,setQuality]=useState<QualityIssue[]|null>(null);
  useEffect(()=>{let active=true;setLoading(true);setError("");Promise.all([request("/api/tanneries"),request("/api/pumps")]).then(([data,pumpData])=>{if(active){setRows(data);setPumps(pumpData)}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[version]);
  useEffect(()=>{if(!editor&&!deleting)return;const handler=(e:KeyboardEvent)=>{if(e.key==="Escape"&&!busy){setEditor(null);setDeleting(null)}};window.addEventListener("keydown",handler);return()=>window.removeEventListener("keydown",handler)},[editor,deleting,busy]);
  const visible=rows.filter(row=>(!pump||row.pump_house===pump)&&`${row.name} ${row.sno} ${row.gstin??""}`.toLowerCase().includes(search.trim().toLowerCase()));
  const open=(mode:"add"|"edit"|"view",row:Tannery|null=null)=>{
    const next=blank();if(row)for(const key of Object.keys(next) as Field[])next[key]=String(row[key]??"");
    setForm(next);setFormError("");setEditor({mode,row});setNotice("");
  };
  const save=async(e:FormEvent)=>{
    e.preventDefault();if(!editor||busy)return;setBusy(true);setFormError("");
    const payload:Record<string,string|number|null>={};
    for(const [key,value] of Object.entries(form)){
      if(key==="sno")continue;
      payload[key]=["sno","original_shares","additional_shares"].includes(key)?(value===""?null:Number(value)):(value.trim()||null);
    }
    try{const saved=await request(editor.mode==="add"?"/api/tanneries":`/api/tanneries/${editor.row!.id}`,{method:editor.mode==="add"?"POST":"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});setNotice(editor.mode==="add"?`Tannery created successfully. S.No ${saved.sno}.`:"Tannery details saved.");setEditor(null);setVersion(x=>x+1)}catch(e){setFormError((e as Error).message)}finally{setBusy(false)}
  };
  const remove=async()=>{if(!deleting||busy)return;setBusy(true);setFormError("");try{await request(`/api/tanneries/${deleting.id}`,{method:"DELETE"});setNotice(`${deleting.name} deleted.`);setDeleting(null);setVersion(x=>x+1)}catch(e){setFormError((e as Error).message)}finally{setBusy(false)}};
  const importMasters=async(files:FileList|null)=>{
    if(!files?.length||busy)return;setBusy(true);setError("");setNotice("");
    const formData=new FormData();Array.from(files).forEach(file=>formData.append("files",file));
    try{const result=await request("/api/tanneries/import-master",{method:"POST",body:formData});setNotice(`${result.files} workbook(s) imported. ${result.pumps_created} pumps created; ${result.tanneries_created} tanneries created; ${result.tanneries_updated} updated.`);setVersion(x=>x+1)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  };
  return <section className="mx-auto max-w-7xl p-5 lg:p-8">
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.2em] text-cyan-400">Master data</p><h2 className="mt-2 text-3xl font-bold">Tannery Master</h2><p className="mt-2 text-slate-400">Manage tannery details, registrations and contacts.</p></div>{canEdit&&<div className="flex flex-wrap gap-3"><label className={`cursor-pointer rounded-xl border border-cyan-700 bg-white px-5 py-3 font-bold text-cyan-800 ${busy?"pointer-events-none opacity-50":""}`}>Import Pump & Tannery Excel<input type="file" multiple accept=".xlsx,.xlsm" className="hidden" onChange={e=>{importMasters(e.target.files);e.currentTarget.value=""}}/></label><button onClick={()=>open("add")} className="rounded-xl bg-cyan-400 px-5 py-3 font-bold text-slate-950">+ Add Tannery</button></div>}</header>
    <div className="mb-5 flex flex-wrap gap-3"><label className="min-w-48 flex-1"><span className="sr-only">Search tanneries</span><input className={inputClass+" !mt-0"} value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, serial number or GSTINâ€¦"/></label><label><span className="sr-only">Filter by pump house</span><select className={inputClass+" !mt-0"} value={pump} onChange={e=>setPump(e.target.value)}><option value="">All pump houses</option>{pumps.map(x=><option key={x.id} value={x.code}>{x.code} · {x.name}</option>)}</select></label><button onClick={async()=>{if(quality){setQuality(null);return}try{setQuality(await request("/api/tanneries/quality"))}catch(e){setError((e as Error).message)}}} className="rounded-xl border border-slate-700 px-4 py-2 text-sm">Source data quality</button></div>
    {!loading&&!error&&pumps.length===0&&<p className="mb-4 rounded-xl bg-amber-400/10 p-4 text-amber-200">Add a pump in Pump Master before creating a tannery.</p>}
    {notice&&<p role="status" className="mb-4 rounded-xl bg-emerald-400/10 p-4 text-emerald-300">{notice}</p>}
    {error&&<p role="alert" className="mb-4 rounded-xl bg-rose-400/10 p-4 text-rose-300">{error} <button className="underline" onClick={()=>setVersion(x=>x+1)}>Retry</button></p>}
    {quality&&<div className="mb-5 max-h-64 overflow-auto rounded-xl border border-amber-400/30 p-4"><p className="mb-3 text-sm text-amber-200">Last source-load report Â· {quality.length} issues. This report reflects the original import.</p>{quality.map(x=><p key={x.id} className="mb-2 text-sm text-slate-300">{x.tannery_name}: {x.detail}</p>)}</div>}
    <div className="overflow-x-auto rounded-2xl border border-slate-800"><table className="w-full min-w-[800px] text-left text-sm"><thead className="bg-slate-800 text-slate-400"><tr>{["S.No","Tannery name","Pump","GSTIN","Phone","Actions"].map(x=><th key={x} className="px-4 py-4">{x}</th>)}</tr></thead><tbody>{loading?<tr><td colSpan={6} className="p-10 text-center text-slate-400">Loading tanneriesâ€¦</td></tr>:visible.length===0?<tr><td colSpan={6} className="p-10 text-center text-slate-400">{rows.length?"No tanneries match your search.":"No tanneries yet. Add your first tannery to get started."}</td></tr>:visible.map(row=><tr key={row.id} className="border-t border-slate-800 bg-slate-900/60 hover:bg-slate-900"><td className="p-4">{row.sno}</td><td className="p-4 font-semibold">{row.name}</td><td className="p-4">{row.pump_house}</td><td className="p-4 text-slate-400">{row.gstin||"â€”"}</td><td className="p-4 text-slate-400">{row.phone||"â€”"}</td><td className="p-4"><div className="flex gap-3"><button className="ui-action ui-action-view" onClick={()=>open("view",row)}>View</button>{canEdit&&<><button className="ui-action ui-action-edit" onClick={()=>open("edit",row)}>Edit</button><button className="ui-action ui-action-danger" onClick={()=>{setFormError("");setDeleting(row)}}>Delete</button></>}</div></td></tr>)}</tbody></table></div><p className="mt-3 text-sm text-slate-500">Showing {visible.length} of {rows.length} tanneries</p>
    {editor&&<div className="fixed inset-0 z-20 overflow-y-auto bg-black/75 p-4 sm:p-8"><section role="dialog" aria-modal="true" aria-labelledby="tannery-title" className="mx-auto max-w-3xl rounded-2xl border border-slate-700 bg-slate-900 p-5 sm:p-8"><div className="mb-6 flex justify-between gap-4"><h2 id="tannery-title" className="text-2xl font-bold">{editor.mode==="add"?"Add Tannery":editor.mode==="edit"?"Edit Tannery":"Tannery Details"}</h2><button disabled={busy} aria-label="Close tannery form" onClick={()=>setEditor(null)} className="text-slate-400">Close âœ•</button></div><form onSubmit={save}>{editor.mode==="add"&&<p className="mb-5 text-sm text-slate-400">Serial number will be assigned automatically when you save.</p>}
      {groups.map(group=><fieldset disabled={busy||editor.mode==="view"} key={group.title} className="mb-6"><legend className="mb-4 font-semibold text-cyan-300">{group.title}</legend><div className="grid gap-4 sm:grid-cols-2">{group.fields.filter(([key])=>key!=="sno"||editor.mode!=="add").map(([key,label,max])=><label key={key} className={key==="name"||key==="consent"||key==="gps"?"text-sm text-slate-400 sm:col-span-2":"text-sm text-slate-400"}>{label}{["sno","name","pump_house"].includes(key)&&" *"}{key==="pump_house"?<select required className={inputClass} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}><option value="">Select pump house</option>{pumps.map(x=><option key={x.id} value={x.code}>{x.code} · {x.name}</option>)}</select>:key==="consent"||key==="gps"?<textarea className={inputClass} rows={2} maxLength={max} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/>:<input autoFocus={key==="name"} required={["sno","name"].includes(key)} disabled={key==="sno"&&editor.mode!=="add"} type={["sno","original_shares","additional_shares"].includes(key)?"number":key==="email"?"email":key==="phone"?"tel":"text"} min={key==="sno"?1:0} step={1} maxLength={max} className={inputClass} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/>} {key==="sno"&&editor.mode!=="add"&&<span className="mt-1 block text-xs">Permanent serial number used by import mappings.</span>}</label>)}</div></fieldset>)}
      {formError&&<p role="alert" className="mb-4 rounded-xl bg-rose-400/10 p-3 text-rose-300">{formError}</p>}<div className="flex justify-end gap-3 border-t border-slate-800 pt-5"><button type="button" disabled={busy} onClick={()=>setEditor(null)} className="rounded-xl bg-slate-800 px-5 py-3">{editor.mode==="view"?"Close":"Cancel"}</button>{editor.mode!=="view"&&<button disabled={busy} className="rounded-xl bg-cyan-400 px-5 py-3 font-bold text-slate-950 disabled:opacity-50">{busy?"Savingâ€¦":editor.mode==="add"?"Create Tannery":"Save Changes"}</button>}{editor.mode==="view"&&canEdit&&<button type="button" onClick={()=>open("edit",editor.row)} className="rounded-xl bg-cyan-400 px-5 py-3 font-bold text-slate-950">Edit Details</button>}</div>
    </form></section></div>}
    {deleting&&<div className="fixed inset-0 z-30 grid place-items-center bg-black/75 p-4"><section role="alertdialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6"><h2 id="delete-title" className="text-xl font-bold">Delete tannery?</h2><p className="mt-3 text-slate-300">{deleting.name} Â· S.No {deleting.sno}</p><p className="mt-3 text-sm text-slate-400">This permanently removes this master record. Tanneries linked to imports, accounts or transactions cannot be deleted.</p>{formError&&<p role="alert" className="mt-4 text-rose-300">{formError}</p>}<div className="mt-6 flex justify-end gap-3"><button disabled={busy} onClick={()=>setDeleting(null)} className="rounded-xl bg-slate-800 px-4 py-2">Cancel</button><button disabled={busy} onClick={remove} className="rounded-xl bg-rose-500 px-4 py-2 font-bold disabled:opacity-50">{busy?"Deletingâ€¦":"Delete Tannery"}</button></div></section></div>}
  </section>;
}
