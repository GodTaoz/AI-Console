import { createApp, watch } from 'vue'

import App from './App.vue'
import { createConsoleI18n } from './i18n'
import { language, theme } from './stores/ui'
import './styles/global.css'
import './styles/tokens.css'

const i18n = createConsoleI18n(language.value)

watch(
  language,
  (value) => {
    i18n.global.locale.value = value
    document.documentElement.lang = value
  },
  { immediate: true },
)

watch(
  theme,
  (value) => {
    document.documentElement.dataset.theme = value
  },
  { immediate: true },
)

void createApp(App).use(i18n).mount('#app')
