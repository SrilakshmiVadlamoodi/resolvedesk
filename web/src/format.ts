export function formatInr(amount: unknown): string {
  const value = typeof amount === 'number' ? amount : Number(amount)
  if (Number.isNaN(value)) return String(amount)
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}
