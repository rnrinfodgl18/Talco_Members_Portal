import {useState} from "react";
import {api,jsonRequest} from "./api";

export default function PhoneVerification({phone,verified,onVerified}:{phone:string;verified:boolean;onVerified:()=>void}){
 const [sent,setSent]=useState(false),[code,setCode]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const request=async()=>{setBusy(true);setMessage("");try{const x=await api("/api/auth/phone-verification/request",{method:"POST"});if(x.status==="already_verified"){onVerified();setMessage("WhatsApp number is already verified.")}else{setSent(true);setMessage("Verification code sent to your WhatsApp number.")}}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}};
 const confirm=async()=>{setBusy(true);setMessage("");try{await api("/api/auth/phone-verification/confirm",jsonRequest("POST",{code}));onVerified();setSent(false);setMessage("WhatsApp number verified successfully.")}catch(e){setMessage((e as Error).message)}finally{setBusy(false)}};
 return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h3 className="text-xl font-bold">WhatsApp verification</h3><p className="mt-2 text-slate-600">Verify your saved phone number to receive official WhatsApp notifications.</p><p className={"mt-4 inline-flex rounded-full px-3 py-1 text-sm font-semibold "+(verified?"bg-emerald-50 text-emerald-700":"bg-amber-50 text-amber-700")}>{verified?"Verified":phone?"Verification pending":"Phone number required"}</p>{phone&&<p className="mt-3 text-sm font-semibold">{phone}</p>}
  {!verified&&!sent&&<button disabled={busy||!phone} onClick={request} className="ui-action ui-action-primary mt-4">{busy?"Sending…":"Send WhatsApp code"}</button>}
  {!verified&&sent&&<div className="mt-4"><label className="text-sm font-semibold">6-digit code<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,"").slice(0,6))} className="mt-2 w-full rounded-lg border p-3 text-center font-mono text-xl tracking-[.35em]"/></label><div className="mt-3 flex gap-2"><button disabled={busy||code.length!==6} onClick={confirm} className="ui-action ui-action-primary">Verify code</button><button disabled={busy} onClick={request} className="ui-action ui-action-secondary">Resend</button></div></div>}
  {message&&<p role="status" className="mt-4 rounded-lg bg-slate-50 p-3 text-sm font-semibold">{message}</p>}
 </section>
}

