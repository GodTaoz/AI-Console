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

export function formatBytesPerSecond(value: number | null | undefined, fractionDigits = 1, fallback = '—'): string {
  const formatted = formatBytes(value, fractionDigits, fallback)
  return formatted === fallback ? fallback : `${formatted}/s`
}

export function formatTemperatureCelsius(value: number | null | undefined, fractionDigits = 1, fallback = '—'): string {
  if (!Number.isFinite(value ?? Number.NaN)) return fallback
  return `${Number(value).toFixed(fractionDigits)} ℃`
}

export function shortAccountName(name: string | null | undefined, maxLength = 18): string {
  const value = (name ?? '')
    .replace(/^codex-/, '')
    .replace(/-plus\.json$/, '')
    .replace(/@.*/, '')

  return value.length > maxLength ? value.slice(0, maxLength) : value
}

export function formatDurationSeconds(value: number | null | undefined, fallback = '—', locale = 'zh-CN'): string {
  if (!Number.isFinite(value ?? Number.NaN)) {
    return fallback
  }

  const total = Math.max(0, Math.round(Number(value)))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60

  const zh = locale.startsWith('zh')
  if (days > 0) return zh ? `${days} 天 ${hours} 小时` : `${days}d ${hours}h`
  if (hours > 0) return zh ? `${hours} 小时 ${minutes} 分钟` : `${hours}h ${minutes}m`
  if (minutes > 0) return zh ? `${minutes} 分钟 ${seconds} 秒` : `${minutes}m ${seconds}s`
  return zh ? `${seconds} 秒` : `${seconds}s`
}

export function formatDateTime(value: string | null | undefined, fallback = '尚未采集', locale = 'zh-CN'): string {
  if (!value) return fallback
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return fallback
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date)
}

export function statusLabel(status: string | null | undefined): string {
  if (status === 'ok') return '正常'
  if (status === 'warning') return '警告'
  if (status === 'critical') return '严重'
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
