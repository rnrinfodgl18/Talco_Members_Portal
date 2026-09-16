import {useEffect,useState} from "react";
import AccountsPage from "./AccountsPage";
import AuthPage from "./AuthPage";
import CircularsPage from "./CircularsPage";
import DashboardPage from "./DashboardPage";
import NotificationBell from "./NotificationBell";
import ImportsPage from "./ImportsPage";
import MappingPage from "./MappingPage";
import MasterPage from "./MasterPage";
import PortalPage from "./PortalPage";
import PumpsPage from "./PumpsPage";
import UsersPage from "./UsersPage";
import SettingsPage from "./SettingsPage";
import HelpPage from "./HelpPage";

const apiUrl=import.meta.env.VITE_API_URL??"http://localhost:8000";
const browserWindow=window as typeof window&{__talcoFetch?:typeof fetch};
if(!browserWindow.__talcoFetch){const original=window.fetch.bind(window);browserWindow.__talcoFetch=original;window.fetch=(input,init={})=>{const headers=new Headers(init.headers);const token=localStorage.getItem("talco_token");if(token)headers.set("Authorization",`Bearer ${token}`);return original(input,{...init,headers})}}

type Page="dashboard"|"circulars"|"portal"|"imports"|"mappings"|"masters"|"pumps"|"accounts"|"users"|"settings"|"help";
type User={email:string;display_name?:string|null;phone?:string|null;role:string;tannery_id:number|null;party_id:number|null;email_verified?:boolean};

export default function App(){
 const [selectedAccount,setSelectedAccount]=useState<number|undefined>(),[mobileOpen,setMobileOpen]=useState(false);
 const [user,setUser]=useState<User|null>(null),[checking,setChecking]=useState(true),[page,setPage]=useState<Page>("portal");
 const [brand,setBrand]=useState<{short_name?:string;has_logo?:boolean}>({});
 useEffect(()=>{let frame=0;const enhance=()=>{frame=0;document.querySelectorAll<HTMLTableElement>("main table").forEach(table=>{if(table.closest(".invoice-sheet,.ledger-paper"))return;if(!table.classList.contains("mobile-card-table"))table.classList.add("mobile-card-table");const headers=Array.from(table.querySelectorAll("thead th")).map(x=>x.textContent?.trim()||"");table.querySelectorAll("tbody tr").forEach(row=>Array.from(row.children).forEach((cell,index)=>{if(cell instanceof HTMLTableCellElement&&!cell.colSpan&&cell.dataset.label!==(headers[index]||""))cell.dataset.label=headers[index]||""}))})};const schedule=()=>{if(!frame)frame=requestAnimationFrame(enhance)};schedule();const observer=new MutationObserver(schedule);observer.observe(document.body,{childList:true,subtree:true});return()=>{observer.disconnect();if(frame)cancelAnimationFrame(frame)}},[]);
 useEffect(()=>{const token=localStorage.getItem("talco_token");if(!token){setChecking(false);return}fetch(`${apiUrl}/api/auth/me`).then(async r=>{if(!r.ok)throw new Error();const next=await r.json();setUser(next);setPage(new URLSearchParams(location.search).get("page")==="circulars"?"circulars":"dashboard")}).catch(()=>localStorage.removeItem("talco_token")).finally(()=>setChecking(false))},[]);
 useEffect(()=>{fetch(apiUrl+"/api/settings/public").then(r=>r.json()).then(setBrand).catch(()=>{})},[]);
 const authenticated=(next:User,token:string)=>{localStorage.setItem("talco_token",token);setUser(next);setPage(new URLSearchParams(location.search).get("page")==="circulars"?"circulars":"dashboard")};
 const logout=async()=>{try{await fetch(`${apiUrl}/api/auth/logout`,{method:"POST"})}finally{localStorage.removeItem("talco_token");setUser(null);setMobileOpen(false)}};
 if(checking)return <main className="grid min-h-screen place-items-center bg-slate-950 text-slate-400">Checking session…</main>;
 if(!user)return <AuthPage onAuthenticated={authenticated}/>;
 const admin=user.role==="talco_admin",staff=user.role==="talco_staff"||admin;
 const tabs:Array<[Page,string]>=staff?[["dashboard","Dashboard"],["masters","Tannery Master"],["pumps","Pump Master"],["accounts","Ledger Master"],["portal","Account Ledgers"],["imports","Imports"],["mappings","Mapping queue"],["circulars","Circulars"],...(admin?[["users","Users"] as [Page,string]]:[]),["settings","Settings"],["help","Help / உதவி"]]:[["dashboard","Dashboard"],["portal","My portal"],["circulars","Notice Board"],["settings","Settings"],["help","Help / உதவி"]];
 const navigate=(next:Page)=>{setPage(next);setMobileOpen(false)};
 return <div className="min-h-screen bg-stone-50 text-slate-800 md:flex">
  <header className="no-print sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-3 shadow-sm md:hidden"><button aria-label="Open main menu" aria-expanded={mobileOpen} onClick={()=>setMobileOpen(true)} className="grid h-11 w-11 place-items-center rounded-lg border border-slate-200 text-2xl">☰</button><div className="flex min-w-0 items-center gap-2">{brand.has_logo&&<img src={apiUrl+"/api/settings/logo"} className="h-9 w-11 object-contain"/>}<b className="truncate text-sm">{brand.short_name||"TALCO"}</b></div><NotificationBell onOpen={()=>navigate("circulars")}/></header>
  {mobileOpen&&<button aria-label="Close main menu" className="no-print fixed inset-0 z-40 bg-slate-950/40 md:hidden" onClick={()=>setMobileOpen(false)}/>}
  <aside className={`no-print fixed inset-y-0 left-0 z-50 flex h-dvh w-[280px] shrink-0 flex-col border-r border-emerald-900 bg-emerald-950 p-5 shadow-xl transition-transform md:sticky md:top-0 md:z-20 md:h-screen md:w-[250px] md:translate-x-0 md:shadow-sm ${mobileOpen?"translate-x-0":"-translate-x-full"}`}>
   <div className="mb-6 flex items-start justify-between gap-3"><div>{brand.has_logo&&<img src={apiUrl+"/api/settings/logo"} className="mb-4 max-h-16 max-w-44 rounded bg-white p-1"/>}<p className="text-xs font-bold uppercase tracking-[.25em] text-cyan-400">Dindigul CETP</p><h1 className="mt-2 text-lg font-bold text-slate-900">{staff?(brand.short_name||"TALCO")+" Administration":"Member Portal"}</h1></div><button aria-label="Close menu" onClick={()=>setMobileOpen(false)} className="grid h-10 w-10 place-items-center rounded-lg border border-slate-200 text-xl md:hidden">×</button></div>
   <nav aria-label="Main navigation" className="flex flex-col gap-2 overflow-y-auto">{tabs.map(([key,label])=><button key={key} aria-current={page===key?"page":undefined} onClick={()=>navigate(key)} className={`min-h-11 rounded-lg px-3 py-2.5 text-left text-sm ${page===key?"bg-cyan-400 font-bold text-slate-950":"text-slate-300 hover:bg-slate-800"}`}>{label}</button>)}</nav>
   <div className="mt-auto border-t border-slate-800 pt-5"><p className="break-all text-sm text-slate-400">{user.display_name||user.email}</p><p className="mt-1 break-all text-xs text-slate-500">{user.display_name&&user.email}</p><button onClick={logout} className="mt-3 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700">Log out</button></div>
  </aside>
  <main className="min-w-0 flex-1"><div className="no-print absolute right-4 top-3 z-30 hidden md:block"><NotificationBell onOpen={()=>navigate("circulars")}/></div>{page==="dashboard"?<DashboardPage staff={staff} onAccount={id=>{setSelectedAccount(id);navigate("portal")}} onCirculars={()=>navigate("circulars")} onSettings={()=>navigate("settings")} onNavigate={key=>navigate(key as Page)}/>:page==="portal"?<PortalPage initialAccountId={selectedAccount}/>:page==="circulars"?<CircularsPage staff={staff} admin={admin}/>:page==="imports"?<ImportsPage/>:page==="mappings"?<MappingPage/>:page==="masters"?<MasterPage canEdit={admin}/>:page==="accounts"?<AccountsPage canEdit={admin} onLedger={id=>{setSelectedAccount(id);navigate("portal")}}/>:page==="pumps"?<PumpsPage canEdit={admin}/>:page==="users"?<UsersPage/>:page==="settings"?<SettingsPage user={user} admin={admin} onUser={setUser}/>:<HelpPage/>}<footer className="no-print mx-4 mt-8 border-t border-slate-200 px-2 py-5 text-center text-xs font-medium text-slate-600 sm:mx-6 lg:mx-8"><span>Developed by <a className="font-bold text-emerald-800" href="https://smartiva.in" target="_blank" rel="noreferrer">Smartiva.in</a></span><span className="mx-2 text-slate-300">•</span><span>Powered by <a className="font-bold text-emerald-800" href="https://fiitech.in" target="_blank" rel="noreferrer">FII Tech.in</a></span></footer></main>
 </div>;
}
