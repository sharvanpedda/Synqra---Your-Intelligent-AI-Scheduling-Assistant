// Shared date/time formatting helpers.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** "2026-08-14" -> "Aug 14" */
export function shortDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  return `${MONTHS[m - 1]} ${d}`;
}

/** "2026-08-14" -> "Thu, Aug 14" */
export function fullDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  const dt = new Date(y, m - 1, d);
  return `${WEEKDAYS[dt.getDay()]}, ${MONTHS[m - 1]} ${d}`;
}

/** "2026-08-14" -> "Thursday, August 14" */
export function longDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

/** Is dateStr today's local date? */
export function isToday(dateStr: string): boolean {
  const now = new Date();
  const t = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate()
  ).padStart(2, "0")}`;
  return dateStr === t;
}

/** "14:00" -> "2:00 PM" */
export function niceTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  if (h === undefined || m === undefined) return t;
  const mer = h >= 12 ? "PM" : "AM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:${String(m).padStart(2, "0")} ${mer}`;
}

/** "14:00" -> "2 PM" (drops minutes when :00) */
export function shortTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  if (h === undefined || m === undefined) return t;
  const mer = h >= 12 ? "PM" : "AM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return m === 0 ? `${hr} ${mer}` : `${hr}:${String(m).padStart(2, "0")} ${mer}`;
}

/** "09:00" -> "09:00" (24h clock for rail labels) */
export function railHour(h: number): string {
  return `${String(h).padStart(2, "0")}00`;
}

/** "15:00" -> fractional hour 15.0 */
export function toHour(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h + m / 60;
}

/** Local date as YYYY-MM-DD (never UTC — avoids off-by-one near midnight). */
export function localDateStr(d: Date = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function clockTime(d: Date): string {
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
