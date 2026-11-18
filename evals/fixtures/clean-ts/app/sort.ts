export function byAmount<T extends { amount: number }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.amount - b.amount);
}

export function money(cents: number): string {
  return (cents / 100).toFixed(2);
}
