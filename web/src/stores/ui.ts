import { computed, ref, watch } from 'vue'

export type ThemeMode = 'system' | 'light' | 'soft' | 'dark'
export type ResolvedTheme = 'light' | 'soft' | 'dark'
export type LanguageMode = 'zh-CN' | 'en-US'

const THEME_KEY = 'ai-console-theme'
const LANGUAGE_KEY = 'ai-console-language'

function getStoredValue<T extends string>(key: string, fallback: T): T {
  if (typeof window === 'undefined') {
    return fallback
  }

  const stored = window.localStorage.getItem(key)
  return stored === 'system' || stored === 'light' || stored === 'soft' || stored === 'dark' || stored === 'zh-CN' || stored === 'en-US'
    ? (stored as T)
    : fallback
}

function detectPreferredLanguage(): LanguageMode {
  if (typeof navigator === 'undefined') return 'zh-CN'
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
}

const colorSchemeQuery = typeof window !== 'undefined' ? window.matchMedia?.('(prefers-color-scheme: dark)') : undefined
const systemPrefersDark = ref(colorSchemeQuery?.matches ?? false)

export const theme = ref<ThemeMode>(getStoredValue(THEME_KEY, 'system'))
export const language = ref<LanguageMode>(getStoredValue(LANGUAGE_KEY, detectPreferredLanguage()))
export const sidebarCollapsed = ref(typeof window !== 'undefined' && window.innerWidth < 900)

export const resolvedTheme = computed<ResolvedTheme>(() => {
  if (theme.value === 'system') return systemPrefersDark.value ? 'dark' : 'light'
  return theme.value
})
export const isDarkTheme = computed(() => resolvedTheme.value === 'dark')

export function setTheme(next: ThemeMode) {
  theme.value = next
}

export function setLanguage(next: LanguageMode) {
  language.value = next
}

export function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

export function closeSidebarOnMobile() {
  if (typeof window !== 'undefined' && window.innerWidth < 900) {
    sidebarCollapsed.value = true
  }
}

watch(
  theme,
  (value) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_KEY, value)
    }
  },
  { immediate: true },
)

colorSchemeQuery?.addEventListener('change', (event) => {
  systemPrefersDark.value = event.matches
})

watch(
  language,
  (value) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_KEY, value)
    }
  },
  { immediate: true },
)
