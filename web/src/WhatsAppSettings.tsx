import {FormEvent,useState} from "react";
import {api,fieldClass,jsonRequest} from "./api";

export default function WhatsAppSettings({initial,defaultPhone}:{initial:any;defaultPhone:string}){
 const [config,setConfig]=useState(initial||{}),[testPhone,setTestPhone]=useState(defaultPhone||""),[busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
 const set=(key:string,value:any)=>setConfig({...config,[key]:value});
 const run=async(fn:()=>Promise<any>,ok:string)=>{setBusy(true);setMessage("");setError("");try{const next=await fn();setMessage(ok);return next}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 const save=async(e:FormEvent)=>{e.preventDefault();const next=await run(()=>api("/api/settings/whatsapp",jsonRequest("PUT",config)),"WhatsApp configuration saved.");if(next)setConfig(next)};
 const test=async()=>{await run(()=>api("/api/settings/whatsapp/test",jsonRequest("POST",{phone:testPhone})),"Test WhatsApp message sent successfully.")};
 return <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
  <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-xl font-bold">WhatsApp API</h3><p className="mt-1 text-sm text-slate-600">Use the connected FII Tech WhatsApp device for phone verification and portal alerts.</p></div><span className={"rounded-full px-3 py-1 text-xs font-bold "+(config.whatsapp_enabled?"bg-emerald-50 text-emerald-700":"bg-slate-100 text-slate-600")}>{config.whatsapp_enabled?"Enabled":"Disabled"}</span></div>
  {(message||error)&&<p role="status" className={"mt-4 rounded-lg border p-3 text-sm font-semibold "+(error?"border-rose-200 bg-rose-50 text-rose-700":"border-emerald-200 bg-emerald-50 text-emerald-700")}>{error||message}</p>}
  <form onSubmit={save}><label className="mt-5 flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={!!config.whatsapp_enabled} onChange={e=>set("whatsapp_enabled",e.target.checked)}/>Enable WhatsApp delivery</label><div className="mt-4 grid gap-4 md:grid-cols-2">
   <label className="text-sm text-slate-600">Base URL<input required className={fieldClass} placeholder="https://wapi.example.com" value={config.whatsapp_base_url||""} onChange={e=>set("whatsapp_base_url",e.target.value)}/></label>
   <label className="text-sm text-slate-600">Device ID<input type="number" min="1" className={fieldClass} value={config.whatsapp_device_id||""} onChange={e=>set("whatsapp_device_id",e.target.value?Number(e.target.value):null)}/></label>
   <label className="text-sm text-slate-600 md:col-span-2">API key<input type="password" className={fieldClass} placeholder={config.api_key_configured?"Saved — leave blank to keep":"Enter Bearer API key"} value={config.whatsapp_api_key||""} onChange={e=>set("whatsapp_api_key",e.target.value)}/></label>
  </div><button disabled={busy} className="ui-action ui-action-primary mt-5">Save WhatsApp configuration</button></form>
  <div className="mt-6 border-t pt-5"><h4 className="font-bold">Connection test</h4><p className="mt-1 text-sm text-slate-600">A short test message will be sent to this WhatsApp number.</p><div className="mt-3 flex flex-col gap-3 sm:flex-row"><input className={fieldClass+" mt-0"} placeholder="919876543210" value={testPhone} onChange={e=>setTestPhone(e.target.value)}/><button type="button" disabled={busy||!testPhone} onClick={test} className="ui-action ui-action-view shrink-0">Send test message</button></div></div>
 </section>
}

