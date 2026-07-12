import { computed, ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark'
export type LanguageMode = 'zh-CN' | 'en-US'

const THEME_KEY = 'ai-console-theme'
const LANGUAGE_KEY = 'ai-console-language'

function getStoredValue<T extends string>(key: string, fallback: T): T {
  if (typeof window === 'undefined') {
    return fallback
  }

  const stored = window.localStorage.getItem(key)
  return stored === 'light' || stored === 'dark' || stored === 'zh-CN' || stored === 'en-US'
    ? (stored as T)
    : fallback
}

function detectPreferredTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'dark'
  }

  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const theme = ref<ThemeMode>(getStoredValue(THEME_KEY, detectPreferredTheme()))
export const language = ref<LanguageMode>(getStoredValue(LANGUAGE_KEY, 'zh-CN'))
export const sidebarCollapsed = ref(false)

export const isDarkTheme = computed(() => theme.value === 'dark')

export function setTheme(next: ThemeMode) {
  theme.value = next
}

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

export function setLanguage(next: LanguageMode) {
  language.value = next
}

export function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
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

watch(
  language,
  (value) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_KEY, value)
    }
  },
  { immediate: true },
)
