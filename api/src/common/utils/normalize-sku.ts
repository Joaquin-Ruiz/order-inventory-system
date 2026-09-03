export function normalizeSku(value: string): string {
  const normalized = value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');

  const match = normalized.match(/^([A-Z]+)(\d+)$/);

  if (!match) {
    return normalized;
  }

  const [, prefix, number] = match;

  return `${prefix}-${Number(number).toString().padStart(4, '0')}`;
}