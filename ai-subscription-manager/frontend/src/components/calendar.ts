// Date-only arithmetic: use UTC to avoid browser timezone and DST shifts.
export function previewExpiry(
  start: string,
  count: string,
  unit: string,
): string {
  const n = Number(count);
  if (!start || !Number.isInteger(n) || n < 1) return "";
  const [y, m, d] = start.split("-").map(Number);
  let result: Date;
  if (unit === "day" || unit === "week")
    result = new Date(Date.UTC(y, m - 1, d + n * (unit === "week" ? 7 : 1)));
  else {
    const target = m - 1 + n * (unit === "year" ? 12 : 1);
    const last = new Date(Date.UTC(y, target + 1, 0)).getUTCDate();
    result = new Date(Date.UTC(y, target, Math.min(d, last)));
  }
  if (Number.isNaN(result.valueOf())) return "";
  return result.toISOString().slice(0, 10);
}
