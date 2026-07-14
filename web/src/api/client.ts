import type {
  AiQuotaResponse,
  AgentEntryResponse,
  AgentDiscoveryStatusResponse,
  AgentInspectResponse,
  AgentMessage,
  AgentMessageListResponse,
  AgentMessageType,
  AgentResumeHintResponse,
  AgentHistoryResponse,
  AgentHistorySearchResponse,
  AgentAttachmentPayload,
  AgentModelListResponse,
  AgentRuntimeStatusResponse,
  AgentSession,
  AgentSessionListResponse,
  AgentTurnStartResponse,
  AgentTreeResponse,
  AlertsResponse,
  CollectRunResponse,
  DockerResponse,
  HealthResponse,
  MetricHistoryResponse,
  ResourcesResponse,
  SummaryResponse,
} from '@/types'

export class ApiError extends Error {
  readonly url: string
  readonly status: number
  readonly statusText: string
  readonly body: unknown

  constructor(message: string, options: { url: string; status: number; statusText: string; body?: unknown; cause?: unknown }) {
    super(message, { cause: options.cause })
    this.name = 'ApiError'
    this.url = options.url
    this.status = options.status
    this.statusText = options.statusText
    this.body = options.body
  }
}

export interface ApiClientOptions {
  baseUrl?: string
  fetchImpl?: typeof fetch
}

export interface ApiClient {
  getHealth: () => Promise<HealthResponse>
  getSummary: () => Promise<SummaryResponse>
  getResources: () => Promise<ResourcesResponse>
  getDocker: () => Promise<DockerResponse>
  getAiQuota: () => Promise<AiQuotaResponse>
  getAlerts: () => Promise<AlertsResponse>
  getMetricHistory: (metrics: string[]) => Promise<MetricHistoryResponse>
  getAgentSessions: (includeArchived?: boolean) => Promise<AgentSessionListResponse>
  getAgentTree: () => Promise<AgentTreeResponse>
  getAgentEntry: (sessionId: string) => Promise<AgentEntryResponse>
  getAgentDiscovery: () => Promise<AgentDiscoveryStatusResponse>
  getAgentInspect: (sessionId: string) => Promise<AgentInspectResponse>
  getAgentResumeHint: (sessionId: string) => Promise<AgentResumeHintResponse>
  getAgentMessages: (sessionId: string) => Promise<AgentMessageListResponse>
  sendAgentMessage: (sessionId: string, body: string, messageType?: AgentMessageType) => Promise<AgentMessage>
  ackAgentMessage: (messageId: string) => Promise<AgentMessage>
  getAgentRuntimeStatus: () => Promise<AgentRuntimeStatusResponse>
  getAgentHistory: (sessionId: string, cursor?: string | null) => Promise<AgentHistoryResponse>
  searchAgentHistory: (sessionId: string, query: string) => Promise<AgentHistorySearchResponse>
  startAgentTurn: (sessionId: string, text: string, model?: string | null, attachments?: AgentAttachmentPayload[]) => Promise<AgentTurnStartResponse>
  getAgentModels: (sessionId: string) => Promise<AgentModelListResponse>
  renameAgentSession: (sessionId: string, name: string) => Promise<AgentSession>
  interruptAgentTurn: (runId: string) => Promise<{ run_id: string; status: string }>
  resolveAgentApproval: (runId: string, approvalId: string, decision: 'approve' | 'deny') => Promise<unknown>
  archiveAgentSession: (sessionId: string) => Promise<unknown>
  unarchiveAgentSession: (sessionId: string) => Promise<unknown>
  deleteAgentSourceSession: (sessionId: string, externalSessionId: string) => Promise<AgentSession>
  runCollect: () => Promise<CollectRunResponse>
}

function normalizeBaseUrl(baseUrl?: string): string {
  if (!baseUrl) {
    return ''
  }

  return baseUrl.replace(/\/+$/, '')
}

async function readErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''

  try {
    if (contentType.includes('application/json')) {
      return await response.json()
    }

    const text = await response.text()
    return text.trim() || undefined
  } catch {
    return undefined
  }
}

function createRequestError(url: string, response: Response, body: unknown): ApiError {
  return new ApiError(`Request failed with ${response.status} ${response.statusText}`, {
    url,
    status: response.status,
    statusText: response.statusText,
    body,
  })
}

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch
  const baseUrl = normalizeBaseUrl(options.baseUrl)

  const resolveUrl = (path: string) => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    return baseUrl ? new URL(normalizedPath, baseUrl).toString() : normalizedPath
  }

  const requestJson = async <T>(path: string, init: RequestInit = {}): Promise<T> => {
    const url = resolveUrl(path)
    let response: Response

    try {
      response = await fetchImpl(url, {
        headers: {
          Accept: 'application/json',
          ...(init.headers ?? {}),
        },
        cache: 'no-store',
        ...init,
      })
    } catch (cause) {
      throw new ApiError(`Request failed for ${url}`, {
        url,
        status: 0,
        statusText: 'NetworkError',
        body: undefined,
        cause,
      })
    }

    if (!response.ok) {
      throw createRequestError(url, response, await readErrorBody(response))
    }

    if (response.status === 204) {
      return undefined as T
    }

    try {
      return (await response.json()) as T
    } catch (cause) {
      throw new ApiError(`Failed to parse JSON response from ${url}`, {
        url,
        status: response.status,
        statusText: response.statusText,
        cause,
      })
    }
  }

  return {
    getHealth: () => requestJson<HealthResponse>('/health'),
    getSummary: () => requestJson<SummaryResponse>('/api/summary'),
    getResources: () => requestJson<ResourcesResponse>('/api/resources'),
    getDocker: () => requestJson<DockerResponse>('/api/docker'),
    getAiQuota: () => requestJson<AiQuotaResponse>('/api/ai-quota'),
    getAlerts: () => requestJson<AlertsResponse>('/api/alerts'),
    getMetricHistory: (metrics) => requestJson<MetricHistoryResponse>(`/api/metrics/history?range=24h&metrics=${encodeURIComponent(metrics.join(','))}`),
    getAgentSessions: (includeArchived = false) => requestJson<AgentSessionListResponse>(`/api/v1/agent-sessions?limit=500&include_archived=${includeArchived}`),
    getAgentTree: () => requestJson<AgentTreeResponse>('/api/v1/agent-tree'),
    getAgentEntry: (sessionId) => requestJson<AgentEntryResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/entry`),
    getAgentDiscovery: () => requestJson<AgentDiscoveryStatusResponse>('/api/v1/agent-discovery'),
    getAgentInspect: (sessionId) => requestJson<AgentInspectResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/inspect`, { headers: { 'X-Agent-Source': 'web' } }),
    getAgentResumeHint: (sessionId) => requestJson<AgentResumeHintResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/resume-hint`, { headers: { 'X-Agent-Source': 'web' } }),
    getAgentMessages: (sessionId) => requestJson<AgentMessageListResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/messages?mark_read=false`, { headers: { 'X-Agent-Source': 'web' } }),
    sendAgentMessage: (sessionId, body, messageType = 'note') => requestJson<AgentMessage>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Agent-Source': 'web' },
      body: JSON.stringify({ body, message_type: messageType, from_session_id: null, metadata: {} }),
    }),
    ackAgentMessage: (messageId) => requestJson<AgentMessage>(`/api/v1/agent-messages/${encodeURIComponent(messageId)}/ack`, { method: 'POST', headers: { 'X-Agent-Source': 'web' } }),
    getAgentRuntimeStatus: () => requestJson<AgentRuntimeStatusResponse>('/api/v1/agent-runtime/status'),
    getAgentHistory: (sessionId, cursor) => requestJson<AgentHistoryResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/history?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, { headers: { 'X-Agent-Source': 'web' } }),
    searchAgentHistory: (sessionId, query) => requestJson<AgentHistorySearchResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/history/search?q=${encodeURIComponent(query)}&limit=50`, { headers: { 'X-Agent-Source': 'web' } }),
    startAgentTurn: (sessionId, text, model = null, attachments = []) => requestJson<AgentTurnStartResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/turns`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Agent-Source': 'web' }, body: JSON.stringify({ text, model, attachments }) }),
    getAgentModels: (sessionId) => requestJson<AgentModelListResponse>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/models`),
    renameAgentSession: (sessionId, name) => requestJson<AgentSession>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/name`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-Agent-Source': 'web' }, body: JSON.stringify({ name }) }),
    interruptAgentTurn: (runId) => requestJson<{ run_id: string; status: string }>(`/api/v1/agent-turns/${encodeURIComponent(runId)}/interrupt`, { method: 'POST', headers: { 'X-Agent-Source': 'web' } }),
    resolveAgentApproval: (runId, approvalId, decision) => requestJson(`/api/v1/agent-turns/${encodeURIComponent(runId)}/approvals/${encodeURIComponent(approvalId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Agent-Source': 'web' }, body: JSON.stringify({ decision }) }),
    archiveAgentSession: (sessionId) => requestJson(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/archive`, { method: 'POST', headers: { 'X-Agent-Source': 'web' } }),
    unarchiveAgentSession: (sessionId) => requestJson(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/unarchive`, { method: 'POST', headers: { 'X-Agent-Source': 'web' } }),
    deleteAgentSourceSession: (sessionId, externalSessionId) => requestJson<AgentSession>(`/api/v1/agent-sessions/${encodeURIComponent(sessionId)}/delete-source`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Agent-Source': 'web' }, body: JSON.stringify({ confirm_external_session_id: externalSessionId }) }),
    runCollect: () => requestJson<CollectRunResponse>('/api/collect/run', { method: 'POST' }),
  }
}

export const apiClient = createApiClient()

export const getHealth = apiClient.getHealth
export const getSummary = apiClient.getSummary
export const getResources = apiClient.getResources
export const getDocker = apiClient.getDocker
export const getAiQuota = apiClient.getAiQuota
export const getAlerts = apiClient.getAlerts
export const getMetricHistory = apiClient.getMetricHistory
export const getAgentSessions = apiClient.getAgentSessions
export const getAgentTree = apiClient.getAgentTree
export const getAgentEntry = apiClient.getAgentEntry
export const getAgentDiscovery = apiClient.getAgentDiscovery
export const getAgentInspect = apiClient.getAgentInspect
export const getAgentResumeHint = apiClient.getAgentResumeHint
export const getAgentMessages = apiClient.getAgentMessages
export const sendAgentMessage = apiClient.sendAgentMessage
export const ackAgentMessage = apiClient.ackAgentMessage
export const getAgentRuntimeStatus = apiClient.getAgentRuntimeStatus
export const getAgentHistory = apiClient.getAgentHistory
export const searchAgentHistory = apiClient.searchAgentHistory
export const startAgentTurn = apiClient.startAgentTurn
export const getAgentModels = apiClient.getAgentModels
export const renameAgentSession = apiClient.renameAgentSession
export const interruptAgentTurn = apiClient.interruptAgentTurn
export const resolveAgentApproval = apiClient.resolveAgentApproval
export const archiveAgentSession = apiClient.archiveAgentSession
export const unarchiveAgentSession = apiClient.unarchiveAgentSession
export const deleteAgentSourceSession = apiClient.deleteAgentSourceSession
export const runCollect = apiClient.runCollect
