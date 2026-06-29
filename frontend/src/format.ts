// Small formatting helpers (unit-tested by Vitest).
export function eur(value: number): string {
  return "€" + value.toFixed(2);
}

export function siteName(sites: { id: number; name: string }[], id: number): string {
  return sites.find((s) => s.id === id)?.name ?? `Site ${id}`;
}
