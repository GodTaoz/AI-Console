import type {
  AiQuotaResponse,
  CollectRunResponse,
  DockerResponse,
  HealthResponse,
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
  const details =
    typeof body === 'string'
      ? body
      : body && typeof body === 'object'
        ? JSON.stringify(body)
        : undefined
  const suffix = details ? `: ${details}` : ''
  return new ApiError(`Request failed with ${response.status} ${response.statusText}${suffix}`, {
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
    runCollect: () => requestJson<CollectRunResponse>('/api/collect/run', { method: 'POST' }),
  }
}

export const apiClient = createApiClient()

export const getHealth = apiClient.getHealth
export const getSummary = apiClient.getSummary
export const getResources = apiClient.getResources
export const getDocker = apiClient.getDocker
export const getAiQuota = apiClient.getAiQuota
export const runCollect = apiClient.runCollect

