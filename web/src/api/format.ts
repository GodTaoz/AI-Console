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

export function formatDurationSeconds(value: number | null | undefined, fallback = '—'): string {
  if (!Number.isFinite(value ?? Number.NaN)) {
    return fallback
  }

  const total = Math.max(0, Math.round(Number(value)))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)

  if (days > 0) return `${days}天${hours}小时`
  if (hours > 0) return `${hours}小时${minutes}分钟`
  return `${minutes}分钟`
}

export function statusLabel(status: string | null | undefined): string {
  if (status === 'ok') return '正常'
  if (status === 'warning') return '关注'
  if (status === 'critical') return '异常'
  if (status === 'unsupported') return '不支持'
  if (status === 'permission_denied') return '无权限'
  if (status === 'running') return '运行中'
  if (status === 'healthy') return '健康'
  if (status === 'online') return '在线'
  if (!status || status === 'unknown') return '未知'
  return String(status)
}

export function filesystemUsedPercent(item: { total_bytes: number; used_bytes: number } | null | undefined) {
  if (!item?.total_bytes) return null
  return (item.used_bytes / item.total_bytes) * 100
}

