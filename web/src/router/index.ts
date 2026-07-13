import { defineAsyncComponent, shallowRef, type Component } from 'vue'

export type AppRouteName =
  | 'overview'
  | 'hosts'
  | 'containers'
  | 'agents'
  | 'ai-services'
  | 'network-storage'
  | 'alerts'
  | 'settings'

export interface AppRoute {
  name: AppRouteName
  path: string
  titleKey: string
  descriptionKey: string
  statusKey?: string
  component: Component
  showInNavigation?: boolean
}

export const appRoutes: AppRoute[] = [
  {
    name: 'overview',
    path: '/overview',
    titleKey: 'pages.overview.title',
    descriptionKey: 'pages.overview.liveDescription',
    statusKey: 'shell.liveData',
    component: defineAsyncComponent(() => import('@/pages/OverviewPage.vue')),
  },
  {
    name: 'hosts',
    path: '/hosts',
    titleKey: 'pages.hosts.title',
    descriptionKey: 'pages.hosts.description',
    statusKey: 'shell.liveData',
    component: defineAsyncComponent(() => import('@/pages/HostsPage.vue')),
  },
  {
    name: 'containers',
    path: '/containers',
    titleKey: 'pages.containers.title',
    descriptionKey: 'pages.containers.description',
    statusKey: 'shell.liveData',
    component: defineAsyncComponent(() => import('@/pages/ContainersPage.vue')),
  },
  {
    name: 'agents',
    path: '/agents',
    titleKey: 'pages.agents.title',
    descriptionKey: 'pages.agents.description',
    component: defineAsyncComponent(() => import('@/pages/AgentsPage.vue')),
    showInNavigation: false,
  },
  {
    name: 'ai-services',
    path: '/ai-services',
    titleKey: 'pages.aiServices.title',
    descriptionKey: 'pages.aiServices.description',
    statusKey: 'shell.liveData',
    component: defineAsyncComponent(() => import('@/pages/AiServicesPage.vue')),
  },
  {
    name: 'network-storage',
    path: '/network-storage',
    titleKey: 'pages.networkStorage.title',
    descriptionKey: 'pages.networkStorage.description',
    statusKey: 'shell.liveData',
    component: defineAsyncComponent(() => import('@/pages/NetworkStoragePage.vue')),
  },
  {
    name: 'alerts',
    path: '/alerts',
    titleKey: 'pages.alerts.title',
    descriptionKey: 'pages.alerts.description',
    component: defineAsyncComponent(() => import('@/pages/AlertsPage.vue')),
  },
  {
    name: 'settings',
    path: '/settings',
    titleKey: 'pages.settings.title',
    descriptionKey: 'pages.settings.description',
    component: defineAsyncComponent(() => import('@/pages/SettingsPage.vue')),
    showInNavigation: false,
  },
]

const defaultRoute = appRoutes[0]
const routeByPath = new Map(appRoutes.map((route) => [route.path, route]))
const routeByName = new Map(appRoutes.map((route) => [route.name, route]))

export const currentRoute = shallowRef<AppRoute>(defaultRoute)

function normalizePath(pathname: string) {
  const next = pathname.replace(/\/+$/, '')
  return next.length > 0 ? next : '/'
}

export function resolveRoute(target: string) {
  const normalized = target.startsWith('/') ? normalizePath(target) : `/${target}`
  return routeByPath.get(normalized) ?? defaultRoute
}

export function navigate(target: string | AppRouteName, replace = false) {
  const route = target.startsWith('/') ? resolveRoute(target) : routeByName.get(target as AppRouteName) ?? defaultRoute
  if (typeof window !== 'undefined') {
    const historyMethod = replace ? window.history.replaceState : window.history.pushState
    historyMethod.call(window.history, {}, '', route.path)
  }

  currentRoute.value = route
}

export function initializeRouter() {
  if (typeof window === 'undefined') {
    return
  }

  const initialRoute = resolveRoute(window.location.pathname)
  currentRoute.value = initialRoute

  if (normalizePath(window.location.pathname) !== initialRoute.path) {
    window.history.replaceState({}, '', initialRoute.path)
  }

  window.addEventListener('popstate', () => {
    currentRoute.value = resolveRoute(window.location.pathname)
  })
}
