const DATE = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });

export function formatDate(iso: string): string {
  return DATE.format(new Date(`${iso.slice(0, 10)}T12:00:00`));
}

export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

export function validity(from: string, to: string | null): string {
  return to ? `${formatDate(from)} bis ${formatDate(to)}` : `seit ${formatDate(from)}`;
}

/** Position of a date on a band from `start` to `end`, as a share between 0 and 1. */
export function share(iso: string, start: string, end: string): number {
  const t = (d: string) => new Date(`${d}T12:00:00`).getTime();
  const span = t(end) - t(start);
  return span <= 0 ? 0 : Math.min(1, Math.max(0, (t(iso) - t(start)) / span));
}
