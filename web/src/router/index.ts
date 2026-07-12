import { shallowRef, type Component } from 'vue'

import AgentsPage from '@/pages/AgentsPage.vue'
import AlertsPage from '@/pages/AlertsPage.vue'
import AiServicesPage from '@/pages/AiServicesPage.vue'
import ContainersPage from '@/pages/ContainersPage.vue'
import HostsPage from '@/pages/HostsPage.vue'
import NetworkStoragePage from '@/pages/NetworkStoragePage.vue'
import OverviewPage from '@/pages/OverviewPage.vue'
import SettingsPage from '@/pages/SettingsPage.vue'

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
}

export const appRoutes: AppRoute[] = [
  {
    name: 'overview',
    path: '/overview',
    titleKey: 'pages.overview.title',
    descriptionKey: 'pages.overview.liveDescription',
    statusKey: 'shell.liveData',
    component: OverviewPage,
  },
  {
    name: 'hosts',
    path: '/hosts',
    titleKey: 'pages.hosts.title',
    descriptionKey: 'pages.hosts.description',
    component: HostsPage,
  },
  {
    name: 'containers',
    path: '/containers',
    titleKey: 'pages.containers.title',
    descriptionKey: 'pages.containers.description',
    component: ContainersPage,
  },
  {
    name: 'agents',
    path: '/agents',
    titleKey: 'pages.agents.title',
    descriptionKey: 'pages.agents.description',
    component: AgentsPage,
  },
  {
    name: 'ai-services',
    path: '/ai-services',
    titleKey: 'pages.aiServices.title',
    descriptionKey: 'pages.aiServices.description',
    component: AiServicesPage,
  },
  {
    name: 'network-storage',
    path: '/network-storage',
    titleKey: 'pages.networkStorage.title',
    descriptionKey: 'pages.networkStorage.description',
    component: NetworkStoragePage,
  },
  {
    name: 'alerts',
    path: '/alerts',
    titleKey: 'pages.alerts.title',
    descriptionKey: 'pages.alerts.description',
    component: AlertsPage,
  },
  {
    name: 'settings',
    path: '/settings',
    titleKey: 'pages.settings.title',
    descriptionKey: 'pages.settings.description',
    component: SettingsPage,
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
  const route = target.startsWith('/') ? resolveRoute(target) : routeByName.get(target) ?? defaultRoute
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

