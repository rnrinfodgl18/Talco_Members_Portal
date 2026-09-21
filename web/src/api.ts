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

/** Fetch a binary endpoint. Always goes through apiUrl, like every other call. */
export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${apiUrl}${path}`);
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json())?.detail ?? ""; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" && detail ? detail : `Request failed (${response.status})`);
  }
  return response.blob();
}

/**
 * Save a blob to the device.
 *
 * The anchor has to be in the document and the object URL has to outlive the
 * click: Android Chrome ignores a click on a detached element, and revoking
 * immediately cancels a download that has not started yet.
 */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  setTimeout(() => { link.remove(); URL.revokeObjectURL(url); }, 60_000);
}

/** True where a PDF cannot be shown inline: Android has no iframe PDF viewer. */
export const canPreviewPdfInline = () =>
  typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;

/** Fetch a text endpoint (an HTML invoice preview) through apiUrl. */
export async function apiText(path: string): Promise<string> {
  const response = await fetch(`${apiUrl}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.text();
}
