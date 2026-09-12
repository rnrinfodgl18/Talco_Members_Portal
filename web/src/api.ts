export const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export async function api(path: string, init?: RequestInit) {
  const response = await fetch(`${apiUrl}${path}`, init);
  if (response.status === 204) return null;
  const raw = await response.text();
  let body: any = null;
  if (raw) {
    try { body = JSON.parse(raw); }
    catch {
      throw new Error(response.ok ? "The server returned an invalid response. Please try again." : `Server request failed (${response.status}). Please try again.`);
    }
  }
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map((x: {msg:string}) => x.msg).join("; ") : `Request failed (${response.status})`);
  return body;
}
export const jsonRequest = (method: string, body: unknown): RequestInit => ({method, headers: {"Content-Type":"application/json"}, body: JSON.stringify(body)});
export type Account = {id:number;code:string;name:string;opening_amount:string;opening_side:"Dr"|"Cr";closing_amount:string;closing_side:"Dr"|"Cr";opening_date:string|null;opening_note:string|null;links:{tannery_id:number;tannery_name:string;sno:number;role:string;valid_from:string;valid_to:string|null}[]};
export type Grant = {party_id:number;relationship_role:string};
export const fieldClass="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-emerald-700 focus:ring-2 focus:ring-emerald-100";
