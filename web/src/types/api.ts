export type ApiStatus =
  | 'ok'
  | 'warning'
  | 'critical'
  | 'unsupported'
  | 'permission_denied'
  | 'unknown'

export interface HealthResponse {
  status: 'ok'
  service: 'ai-console'
}

export interface ResourceIssue {
  code: string
  message: string
  status: ApiStatus
}

export interface CpuSnapshot {
  total_jiffies: number
  idle_jiffies: number
}

export interface MemorySnapshot {
  total_bytes: number
  available_bytes: number
  swap_total_bytes: number
  swap_free_bytes: number
}

export interface FilesystemSnapshot {
  mount: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  status: ApiStatus
}

export interface NetworkSnapshot {
  primary_interface: string
  rx_bytes: number
  tx_bytes: number
  status: ApiStatus
}

export interface ThermalSnapshot {
  temperatures_c: Record<string, number>
  status: ApiStatus
}

export interface PowerSnapshot {
  ac_online: boolean | null
  battery_percent: number | null
  battery_health_percent: number | null
  rapl_status: ApiStatus
}

export interface ResourcesResponse {
  status: ApiStatus
  cpu: CpuSnapshot
  memory: MemorySnapshot
  filesystems: FilesystemSnapshot[]
  network: NetworkSnapshot
  thermal: ThermalSnapshot
  power: PowerSnapshot
  issues: ResourceIssue[]
}

export interface DockerPort {
  private_port: number
  public_port: number | null
  ip: string | null
  type: string
}

export interface DockerContainerSnapshot {
  name: string
  image: string
  state: string
  status_text: string
  status: ApiStatus
  health: string | null
  ports: DockerPort[]
}

export interface DockerIssue {
  code: string
  message: string
  status: ApiStatus
  container: string | null
}

export interface DockerResponse {
  status: ApiStatus
  containers: DockerContainerSnapshot[]
  issues: DockerIssue[]
}

export interface CpaQuotaIssue {
  code: string
  message: string
  status: ApiStatus
  account_id: string | null
}

export interface CpaQuotaAccount {
  id: string
  name: string
  provider: string
  status: ApiStatus
  email: string | null
  used_percent: number | null
  remaining_percent: number | null
  reset_after_seconds: number | null
  reset_at: string | null
  reset_credits_available: number | null
  success_count: number | null
  failed_count: number | null
  message: string
  details: Record<string, unknown>
}

export interface AiQuotaResponse {
  status: ApiStatus
  source: 'cpa-management-api'
  accounts: CpaQuotaAccount[]
  issues: CpaQuotaIssue[]
}

export interface SummaryModuleEntry<TPayload = unknown> {
  status: ApiStatus
  updated_at: string
  payload: TPayload
}

export type SummaryModules = Partial<{
  resources: SummaryModuleEntry<ResourcesResponse>
  docker: SummaryModuleEntry<DockerResponse>
  ai_quota: SummaryModuleEntry<AiQuotaResponse>
}> & Record<string, SummaryModuleEntry<unknown> | undefined>

export interface SummaryResponse {
  status: ApiStatus
  modules: SummaryModules
}

export interface CollectRunModuleSnapshot<TPayload = unknown> {
  status: ApiStatus
  payload: TPayload
}

export interface CollectRunResponse {
  status: ApiStatus
  modules: {
    resources: CollectRunModuleSnapshot<ResourcesResponse>
    docker: CollectRunModuleSnapshot<DockerResponse>
    ai_quota: CollectRunModuleSnapshot<AiQuotaResponse>
  }
}

