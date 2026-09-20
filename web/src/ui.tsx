import {ButtonHTMLAttributes,ReactNode} from "react";

export type IconName="dashboard"|"master"|"pump"|"ledger"|"invoice"|"receipt"|"import"|"mapping"|"notice"|"users"|"settings"|"menu"|"close"|"search"|"edit"|"view"|"print"|"delete"|"bell";
const paths:Record<IconName,ReactNode>={
 dashboard:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
 master:<><path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-6h6v6M8 10h.01M12 10h.01M16 10h.01"/></>,
 pump:<><path d="M5 20V9h9v11M8 9V5h8v5M14 12h3a3 3 0 0 1 3 3v5"/><path d="M3 20h19"/></>,
 ledger:<><path d="M5 3h14a2 2 0 0 1 2 2v16H7a2 2 0 0 1-2-2V3Z"/><path d="M5 17h16M9 7h8M9 11h8"/></>,
 invoice:<><path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>,
 receipt:<><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18M7 15h3"/></>,
 import:<><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/></>,
 mapping:<><path d="M7 7h10M7 17h10M7 7l3-3M7 7l3 3M17 17l-3-3M17 17l-3 3"/></>,
 notice:<><path d="M4 5h16v14H4zM8 9h8M8 13h6"/></>,
 users:<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
 settings:<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.36.35.7.6 1 .28.28.64.43 1 .4H21v4h-.09a1.7 1.7 0 0 0-1.51.6Z"/></>,
 menu:<path d="M4 6h16M4 12h16M4 18h16"/>,close:<path d="M6 6l12 12M18 6 6 18"/>,search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,edit:<><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></>,view:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,print:<><path d="M6 9V2h12v7M6 18h12v4H6z"/><rect x="3" y="9" width="18" height="9" rx="2"/></>,delete:<><path d="M3 6h18M8 6V3h8v3M19 6l-1 16H6L5 6M10 11v6M14 11v6"/></>,bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>};
export function Icon({name,className="h-5 w-5"}:{name:IconName;className?:string}){return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>}

type ActionTone="primary"|"edit"|"view"|"print"|"danger"|"secondary";
export function ActionButton({tone="secondary",icon,children,className="",...props}:ButtonHTMLAttributes<HTMLButtonElement>&{tone?:ActionTone;icon?:IconName}){return <button {...props} className={`ui-action ui-action-${tone} ${className}`}>{icon&&<Icon name={icon} className="h-4 w-4"/>}{children}</button>}
