import {useState} from "react";
import {api,jsonRequest} from "./api";

type Channels={circular_email_enabled:boolean;circular_whatsapp_enabled:boolean;email_to_unverified:boolean};

const switches:{key:keyof Channels;label:string;hint:string}[]=[
  {key:"circular_email_enabled",label:"Email published circulars",
   hint:"Sends the title, the notice text and a portal link. Attachments stay in the portal."},
  {key:"circular_whatsapp_enabled",label:"Send circulars on WhatsApp",
   hint:"Text and a portal link only, paced 8–15s apart. The gateway is unofficial, so a large burst risks the number."},
  {key:"email_to_unverified",label:"Email addresses that are not verified",
   hint:"Off means a circular only reaches members who clicked a verification link — in practice, very few."}];

export default function CircularChannels({initial}:{initial:Channels|undefined}){
  const [state,setState]=useState<Channels>(initial??{circular_email_enabled:true,circular_whatsapp_enabled:true,email_to_unverified:true});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
  const save=async(next:Channels)=>{
    setBusy(true);setMessage("");setError("");
    const previous=state;setState(next);
    try{await api("/api/settings/channels",jsonRequest("PUT",next));setMessage("Circular delivery updated.")}
    catch(e){setState(previous);setError((e as Error).message)}
    finally{setBusy(false)}};
  return <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <h3 className="text-xl font-bold">Circular delivery</h3>
    <p className="mt-1 text-sm text-slate-500">In-app notices and push always go out. These control the outside channels.</p>
    <div className="mt-4 space-y-4">{switches.map(item=>
      <label key={item.key} className="flex gap-3">
        <input type="checkbox" className="mt-1" disabled={busy} checked={state[item.key]}
               onChange={e=>save({...state,[item.key]:e.target.checked})}/>
        <span><b className="block text-slate-900">{item.label}</b>
          <span className="text-sm text-slate-500">{item.hint}</span></span>
      </label>)}</div>
    {message&&<p role="status" className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{message}</p>}
    {error&&<p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
  </section>;
}
