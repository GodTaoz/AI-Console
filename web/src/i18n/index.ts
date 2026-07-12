import { createI18n } from 'vue-i18n'

export type LocaleCode = 'zh-CN' | 'en-US'

const messages = {
  'zh-CN': {
    app: {
      title: 'AI-Console',
      subtitle: '面向本机基础设施的轻量控制台',
      phase: 'Phase 1',
      phaseDescription: '前端骨架已就绪',
      heroEyebrow: '本地优先 / 只读状态面板',
      heroDescription: '保留后端边界不变，先把导航、主题与多语言入口搭起来。',
    },
    nav: {
      overview: '总览',
      hosts: '主机监控',
      containers: '容器服务',
      agents: '智能体',
      aiServices: 'AI 服务',
      networkStorage: '网络与存储',
      alerts: '告警记录',
      settings: '系统设置',
    },
    controls: {
      theme: '主题',
      language: '语言',
    },
    theme: {
      light: '浅色模式',
      dark: '深色模式',
    },
    dashboard: {
      overview: '控制台概览',
      routeCount: '侧边栏路由',
      localFirst: '存储策略',
      localFirstValue: 'LocalStorage',
      backendReady: '后端状态',
      backendReadyValue: '保持不变',
      nextStep: '下一步',
      nextStepCopy: 'Phase 2 再接入真实数据源、图表和服务状态视图。',
    },
  },
  'en-US': {
    app: {
      title: 'AI-Console',
      subtitle: 'A lightweight console for local infrastructure',
      phase: 'Phase 1',
      phaseDescription: 'Frontend scaffold ready',
      heroEyebrow: 'Local-first / read-only status panel',
      heroDescription: 'Keep the backend boundary intact and bring up navigation, theme, and language entry points first.',
    },
    nav: {
      overview: 'Overview',
      hosts: 'Host Monitoring',
      containers: 'Container Services',
      agents: 'Agents',
      aiServices: 'AI Services',
      networkStorage: 'Network & Storage',
      alerts: 'Alert Records',
      settings: 'System Settings',
    },
    controls: {
      theme: 'Theme',
      language: 'Language',
    },
    theme: {
      light: 'Light mode',
      dark: 'Dark mode',
    },
    dashboard: {
      overview: 'Console Overview',
      routeCount: 'Sidebar routes',
      localFirst: 'Storage strategy',
      localFirstValue: 'LocalStorage',
      backendReady: 'Backend status',
      backendReadyValue: 'Unchanged',
      nextStep: 'Next step',
      nextStepCopy: 'Phase 2 will connect real data sources, charts, and service status views.',
    },
  },
} as const

export function createConsoleI18n(locale: LocaleCode) {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en-US',
    messages,
  })
}
