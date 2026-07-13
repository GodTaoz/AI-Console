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

export interface SnapshotMetadata {
  collected_at?: string
  stale?: boolean
}

export interface ResourceIssue {
  code: string
  message: string
  status: ApiStatus
}

export interface CpuSnapshot {
  total_jiffies: number
  idle_jiffies: number
  usage_percent: number | null
  logical_cores: number
  model: string
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
  rx_bytes_per_second: number | null
  tx_bytes_per_second: number | null
  ip_address: string | null
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

export interface DiskIoSnapshot {
  read_bytes_per_second: number | null
  write_bytes_per_second: number | null
  devices: string[]
  status: ApiStatus
}

export interface SystemInfoSnapshot {
  hostname: string
  manufacturer: string
  model: string
  os_name: string
  kernel: string
  primary_ip: string | null
  uptime_seconds: number
}

export interface ProcessSnapshot {
  pid: number
  name: string
  cpu_percent: number
  memory_percent: number
  rss_bytes: number
}

export interface ProcessRankings {
  top_cpu: ProcessSnapshot[]
  top_memory: ProcessSnapshot[]
}

export interface FirewallRule {
  port: number | string
  protocol: string
  source: string
  family: string
}

export interface FirewallSnapshot {
  provider: string
  enabled: boolean | null
  status: ApiStatus
  rules: FirewallRule[]
}

export interface ListeningPort {
  port: number
  protocol: string
  address: string
  scope: 'loopback' | 'all_interfaces' | 'specific_address'
}

export interface SecuritySnapshot {
  firewall: FirewallSnapshot
  listening_ports: ListeningPort[]
}

export interface ResourcesResponse extends SnapshotMetadata {
  status: ApiStatus
  cpu: CpuSnapshot
  memory: MemorySnapshot
  filesystems: FilesystemSnapshot[]
  network: NetworkSnapshot
  thermal: ThermalSnapshot
  power: PowerSnapshot
  disk_io: DiskIoSnapshot
  system: SystemInfoSnapshot
  processes: ProcessRankings
  security: SecuritySnapshot
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
  core: boolean
  uptime_seconds: number | null
}

export interface DockerIssue {
  code: string
  message: string
  status: ApiStatus
  container: string | null
}

export interface DockerResponse extends SnapshotMetadata {
  status: ApiStatus
  containers: DockerContainerSnapshot[]
  issues: DockerIssue[]
  core_summary: {
    expected: number
    present: number
    healthy: number
  }
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

export interface AiQuotaResponse extends SnapshotMetadata {
  status: ApiStatus
  source: 'cpa-management-api'
  accounts: CpaQuotaAccount[]
  issues: CpaQuotaIssue[]
}

export interface SummaryModuleEntry<TPayload = unknown> {
  status: ApiStatus
  updated_at: string
  stale: boolean
  payload: TPayload
}

export type SummaryModules = Partial<{
  resources: SummaryModuleEntry<ResourcesResponse>
  docker: SummaryModuleEntry<DockerResponse>
  ai_quota: SummaryModuleEntry<AiQuotaResponse>
}> & Record<string, SummaryModuleEntry<unknown> | undefined>

export interface SummaryResponse {
  status: ApiStatus
  stale: boolean
  generated_at: string
  modules: SummaryModules
}

export interface CollectRunModuleSnapshot<TPayload = unknown> {
  status: ApiStatus
  payload: TPayload
}

export interface CollectRunResponse {
  status: ApiStatus
  run_id: number
  collected_at: string
  duration_ms: number
  modules: {
    resources: CollectRunModuleSnapshot<ResourcesResponse>
    docker: CollectRunModuleSnapshot<DockerResponse>
    ai_quota: CollectRunModuleSnapshot<AiQuotaResponse>
  }
}

export interface AlertEvent {
  fingerprint: string
  source: string
  severity: ApiStatus
  code: string
  title: string
  state: 'active' | 'resolved'
  first_seen_at: string
  last_seen_at: string
  resolved_at: string | null
  occurrence_count: number
  details: Record<string, unknown>
}

export interface AlertsResponse {
  status: 'ok'
  generated_at: string
  active_count: number
  events: AlertEvent[]
}

export interface MetricPoint {
  timestamp: string
  value: number
}

export interface MetricSeries {
  metric: string
  labels: Record<string, string>
  unit: string
  points: MetricPoint[]
}

export interface MetricHistoryResponse {
  generated_at: string
  range: '24h'
  bucket_seconds: number
  series: MetricSeries[]
}
