export function formatBdt(amount: number): string {
  return `৳${amount.toLocaleString('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatPack(unit: string, unitValue: number): string {
  const value = Number.isInteger(unitValue) ? unitValue : unitValue.toFixed(2)
  if (unit === 'pcs') return `${value} pc${unitValue === 1 ? '' : 's'}`
  return `${value}${unit}`
}
