import { useI18n } from 'vue-i18n'

import { formatDateTime, formatDurationSeconds } from '@/api/format'

export function useConsoleFormatters() {
  const { locale, t, te } = useI18n()

  return {
    dateTime: (value: string | null | undefined, fallback?: string) =>
      formatDateTime(value, fallback ?? t('common.notCollected'), locale.value),
    duration: (value: number | null | undefined, fallback?: string) =>
      formatDurationSeconds(value, fallback ?? '—', locale.value),
    statusText: (status: string | null | undefined) => t(`status.${status || 'unknown'}`),
    issueText: (code: string, fallback: string) => te(`issues.${code}`) ? t(`issues.${code}`) : fallback,
  }
}
