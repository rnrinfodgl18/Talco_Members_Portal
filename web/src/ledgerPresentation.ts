export type StatementEntry = {
  id: number;
  kind: string;
  date: string;
  voucher_no: string;
  description?: string;
  debit: string;
  credit: string;
  balance: string;
  is_step: boolean;
};
export type HistoryEntry = {
  id: number;
  date: string;
  voucher_no: string;
  description?: string;
  gross?: string;
  amount?: string;
  is_step?: boolean;
};
export const formatMoney = (value: string) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2,
}).format(Math.abs(Number(value)));
export function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
  }).format(date);
}
export function sourceNumber(value: string) {
  return !value || value.startsWith("legacy-") ? null : value;
}
export function balanceLabel(value: string) {
  return Number(value) < 0 ? "Advance / credit available" : Number(value) > 0 ? "Amount due" : "Nothing due";
}
export function transactionLabel(kind: string, description?: string, step?: boolean) {
  if (kind === "opening") return "Opening balance";
  if (kind === "receipt") return step ? "Payment received (STEP)" : "Payment received";
  return description ? `${description} bill` : "Bill raised";
}
