export function formatPercent(value: number | null | undefined, fractionDigits = 1, fallback = '—'): string {
  if (!Number.isFinite(value ?? Number.NaN)) {
    return fallback
  }

  return `${Number(value).toFixed(fractionDigits)}%`
}

const BINARY_UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'] as const

export function formatBytes(value: number | null | undefined, fractionDigits = 1, fallback = '—'): string {
  if (!Number.isFinite(value ?? Number.NaN)) {
    return fallback
  }

  let size = Number(value)
  let unitIndex = 0
  while (size >= 1024 && unitIndex < BINARY_UNITS.length - 1) {
    size /= 1024
    unitIndex += 1
  }

  const formatted = unitIndex === 0 ? `${Math.round(size)}` : size.toFixed(fractionDigits)
  return `${formatted} ${BINARY_UNITS[unitIndex]}`
}

export function shortAccountName(name: string | null | undefined, maxLength = 18): string {
  const value = (name ?? '')
    .replace(/^codex-/, '')
    .replace(/-plus\.json$/, '')
    .replace(/@.*/, '')

  return value.length > maxLength ? value.slice(0, maxLength) : value
}

