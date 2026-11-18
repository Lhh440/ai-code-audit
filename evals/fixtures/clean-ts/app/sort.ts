export function byAmount<T extends { amount: number }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.amount - b.amount);
}

export function money(cents: number): string {
  return (cents / 100).toFixed(2);
}

// These mentions in prose are not calls: fetch(, innerHTML, .sort().
export const NOTE = "see net.ts for the HTTP wrapper";
