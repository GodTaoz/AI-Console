<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NCheckbox, NDrawer, NDrawerContent, NDropdown, NEmpty, NIcon, NInput, NModal, NSelect, NSpin, NTabPane, NTabs, NTag, useNotification } from 'naive-ui'
import { AttachOutline, ChevronBackOutline, ChevronForwardOutline, MenuOutline, SendOutline, StopCircleOutline } from '@vicons/ionicons5'

import AgentMarkdown from '@/components/agents/AgentMarkdown.vue'
import AgentModuleNav from '@/components/agents/AgentModuleNav.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import {
  ApiError,
  archiveAgentSession,
  deleteAgentSourceSession,
  getAgentHistory,
  getAgentMessages,
  getAgentModels,
  getAgentResumeHint,
  getAgentRuntimeStatus,
  getAgentTurnStatus,
  getAgentSessions,
  interruptAgentTurn,
  resolveAgentApproval,
  renameAgentSession,
  searchAgentHistory,
  sendAgentMessage,
  startAgentTurn,
  unarchiveAgentSession,
} from '@/api'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type {
  AgentHistoryMessage,
  AgentAttachmentPayload,
  AgentLifecycleStatus,
  AgentMessage,
  AgentMessageType,
  AgentModelOption,
  AgentRuntimeStatusResponse,
  AgentSession,
  AgentSessionListResponse,
  AgentTurnEvent,
} from '@/types'

type TurnPhase = 'thinking' | 'tool_running' | 'waiting_approval' | 'responding'

interface LiveTool {
  name: string
  status: string
}

interface TurnMetrics {
  sessionId: string
  previousAssistantId: string
  thinkingMs: number
  totalMs: number
}

interface PendingApproval {
  runId: string
  approvalId: string
  kind: string
  summary: string
  resolving: boolean
}

interface PendingAttachment extends AgentAttachmentPayload {
  id: string
  size: number
}

const { t } = useI18n()
const notification = useNotification()
const { dateTime } = useConsoleFormatters()
const sessions = ref<AgentSessionListResponse | null>(null)
const runtimeStatus = ref<AgentRuntimeStatusResponse | null>(null)
const selectedSession = ref<AgentSession | null>(null)
const history = ref<AgentHistoryMessage[]>([])
const nextCursor = ref<string | null>(null)
const inbox = ref<AgentMessage[]>([])
const pendingApprovals = ref<PendingApproval[]>([])
const loading = ref(false)
const historyLoading = ref(false)
const searchText = ref('')
const historyQuery = ref('')
const runtimeFilter = ref('all')
const statusFilter = ref<AgentLifecycleStatus | 'all'>('all')
const showArchived = ref(false)
const composerText = ref('')
const currentRunId = ref('')
const startingSessionId = ref('')
const streamingText = ref('')
const models = ref<AgentModelOption[]>([])
const selectedModel = ref<string | null>(null)
const selectedReasoningEffort = ref<string | null>(null)
const modelLoading = ref(false)
const attachments = ref<PendingAttachment[]>([])
const attachmentInput = ref<HTMLInputElement | null>(null)
const taskBody = ref('')
const taskType = ref<AgentMessageType>('task')
const workspaceTab = ref<'conversation' | 'tasks'>('conversation')
const sendingTask = ref(false)
const resumeCommand = ref('')
const copyState = ref<'idle' | 'copied' | 'failed'>('idle')
const deleteVisible = ref(false)
const deleteConfirmation = ref('')
const deleting = ref(false)
const renameVisible = ref(false)
const renameValue = ref('')
const renaming = ref(false)
const sessionPaneWidth = ref(320)
const sessionPaneCollapsed = ref(false)
const mobileDrawerOpen = ref(false)
const resizing = ref(false)
const turnPhase = ref<TurnPhase | null>(null)
const turnPhaseDetail = ref('')
const turnStartedAt = ref(0)
const phaseStartedAt = ref(0)
const turnElapsedMs = ref(0)
const phaseElapsedMs = ref(0)
const thinkingElapsedMs = ref(0)
const lastTurnMetrics = ref<TurnMetrics | null>(null)
const turnPreviousAssistantId = ref('')
const liveTools = ref<LiveTool[]>([])
const historyRoot = ref<HTMLElement | null>(null)
let eventSource: EventSource | null = null
let phaseTimer: number | null = null
let thinkingAccumulatedMs = 0
const dismissedApprovalKeys = new Set<string>()
let selectionGeneration = 0
const activeRunsStorageKey = 'ai-console-agent-active-runs'
const selectedSessionStorageKey = 'ai-console-agent-selected-session'
const sessionStatusPriority: Record<AgentLifecycleStatus, number> = {
  active: 0,
  starting: 1,
  waiting: 2,
  idle: 3,
  unknown: 4,
  failed: 5,
  lost: 6,
  completed: 7,
}

const statusOptions = computed(() => [
  { label: t('agentUi.allStatuses'), value: 'all' },
  ...(['starting', 'active', 'idle', 'waiting', 'completed', 'failed', 'lost', 'unknown'] as AgentLifecycleStatus[])
    .map((value) => ({ label: statusText(value), value })),
])
const runtimeOptions = computed(() => [
  { label: t('agentUi.allRuntimes'), value: 'all' },
  ...Array.from(new Set((sessions.value?.sessions ?? []).map((item) => item.agent.runtime))).sort().map((value) => ({ label: value, value })),
])
const taskTypeOptions = computed(() => [
  { label: t('agentUi.messageType.task'), value: 'task' },
  { label: t('agentUi.messageType.note'), value: 'note' },
  { label: t('agentUi.messageType.status'), value: 'status' },
])
const actionOptions = computed(() => {
  if (!selectedSession.value) return []
  const items = selectedSession.value.archived_at
    ? [{ label: t('agentUi.unarchive'), key: 'unarchive' }]
    : [{ label: t('agentUi.archive'), key: 'archive' }]
  items.push({ label: t('agentUi.copyResume'), key: 'resume' })
  items.push({ label: t('agentUi.renameSession'), key: 'rename' })
  items.push({ label: t('agentUi.deleteSource'), key: 'delete' })
  return items
})
function compareSessions(left: AgentSession, right: AgentSession) {
  const statusDifference = sessionStatusPriority[left.status] - sessionStatusPriority[right.status]
  const leftActivity = typeof left.metadata.runtime_updated_at === 'string' ? left.metadata.runtime_updated_at : left.last_seen_at
  const rightActivity = typeof right.metadata.runtime_updated_at === 'string' ? right.metadata.runtime_updated_at : right.last_seen_at
  return statusDifference || rightActivity.localeCompare(leftActivity)
}
const filteredSessions = computed(() => (sessions.value?.sessions ?? []).filter((session) => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return (runtimeFilter.value === 'all' || session.agent.runtime === runtimeFilter.value)
    && (statusFilter.value === 'all' || session.status === statusFilter.value)
    && (!query || `${session.agent.display_name} ${session.purpose} ${session.external_session_id ?? ''}`.toLocaleLowerCase().includes(query))
}).sort(compareSessions))
const selectedAdapterState = computed(() => selectedSession.value ? runtimeStatus.value?.adapters[selectedSession.value.agent.runtime] : undefined)
const canChat = computed(() => Boolean(selectedSession.value?.external_session_id && !selectedSession.value.source_deleted_at && runtimeStatus.value?.available && selectedAdapterState.value !== 'unavailable'))
const modelOptions = computed(() => models.value.map((model) => ({
  label: model.label,
  value: model.id,
})))
const selectedModelOption = computed(() => models.value.find((model) => model.id === selectedModel.value) ?? null)
const reasoningOptions = computed(() => [
  {
    label: selectedModelOption.value?.default_reasoning_effort
      ? t('agentUi.reasoningAutoWithDefault', { effort: t(`agentUi.reasoningEffort.${selectedModelOption.value.default_reasoning_effort}`) })
      : t('agentUi.reasoningAuto'),
    value: 'auto',
  },
  ...(selectedModelOption.value?.reasoning_efforts ?? []).map((effort) => ({
    label: t(`agentUi.reasoningEffort.${effort}`),
    value: effort,
  })),
])
const workspaceStyle = computed(() => ({ '--session-pane-width': `${sessionPaneCollapsed.value ? 0 : sessionPaneWidth.value}px` }))
const totalAttachmentBytes = computed(() => attachments.value.reduce((total, item) => total + item.size, 0))
const mobileDrawerWidth = computed(() => typeof window === 'undefined' ? 320 : Math.min(360, Math.max(280, window.innerWidth - 40)))
const turnPhaseLabel = computed(() => {
  if (!turnPhase.value) return ''
  const key = { thinking: 'thinking', tool_running: 'toolRunning', waiting_approval: 'waitingApproval', responding: 'responding' }[turnPhase.value]
  return t(`agentUi.${key}`)
})
const turnStartingForSelected = computed(() => Boolean(selectedSession.value && startingSessionId.value === selectedSession.value.session_id))
const turnBusy = computed(() => Boolean(currentRunId.value || turnStartingForSelected.value))
const latestAssistantMessageId = computed(() => [...history.value].reverse().find((message) => message.role === 'assistant')?.message_id ?? '')
const activeApproval = computed(() => pendingApprovals.value[0] ?? null)
const remainingApprovalCount = computed(() => Math.max(0, pendingApprovals.value.length - 1))

function statusText(status: AgentLifecycleStatus) { return t(`agentUi.status.${status}`) }
function statusType(status: AgentLifecycleStatus) {
  if (status === 'active' || status === 'completed') return 'success'
  if (status === 'failed' || status === 'lost') return 'error'
  if (status === 'waiting' || status === 'starting') return 'warning'
  return 'default'
}
function sessionSource(session: AgentSession) {
  return typeof session.metadata.source === 'string' ? session.metadata.source : session.registration_source
}
function closeEventStream() {
  eventSource?.close()
  eventSource = null
  stopPhaseTimer()
}
function readActiveRuns(): Record<string, string> {
  try {
    const value = JSON.parse(sessionStorage.getItem(activeRunsStorageKey) ?? '{}')
    return value && typeof value === 'object' ? value as Record<string, string> : {}
  } catch {
    return {}
  }
}
function activeRunFor(sessionId: string) {
  return readActiveRuns()[sessionId] ?? ''
}
function rememberActiveRun(sessionId: string, runId: string) {
  sessionStorage.setItem(activeRunsStorageKey, JSON.stringify({ ...readActiveRuns(), [sessionId]: runId }))
}
function forgetActiveRun(sessionId: string, runId: string) {
  const runs = readActiveRuns()
  if (runs[sessionId] !== runId) return
  delete runs[sessionId]
  sessionStorage.setItem(activeRunsStorageKey, JSON.stringify(runs))
}
function apiErrorCode(value: unknown) {
  if (!(value instanceof ApiError) || !value.body || typeof value.body !== 'object') return ''
  const detail = 'detail' in value.body ? value.body.detail : null
  return detail && typeof detail === 'object' && 'code' in detail ? String(detail.code ?? '') : ''
}

function approvalKey(runId: string, approvalId: string) {
  return `${runId}:${approvalId}`
}

function notifyError(content: string, title = t('common.loadFailed')) {
  notification.error({ title, content, duration: 6000, closable: true })
}

function setError(value: unknown) {
  const code = apiErrorCode(value) || 'runtime_error'
  notifyError(t('agentUi.operationFailed', { code }))
}
function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function loadAgents(preserveSelection = true) {
  loading.value = true
  try {
    const [nextSessions, nextRuntime] = await Promise.all([
      getAgentSessions(showArchived.value),
      getAgentRuntimeStatus(),
    ])
    sessions.value = nextSessions
    runtimeStatus.value = nextRuntime
    if (preserveSelection && selectedSession.value) {
      selectedSession.value = nextSessions.sessions.find((item) => item.session_id === selectedSession.value?.session_id) ?? null
    }
    if (!selectedSession.value && nextSessions.sessions.length) {
      const requestedSessionId = sessionStorage.getItem('ai-console-agent-open-session')
      if (requestedSessionId) sessionStorage.removeItem('ai-console-agent-open-session')
      const savedSessionId = sessionStorage.getItem(selectedSessionStorageKey)
      const orderedSessions = [...nextSessions.sessions].sort(compareSessions)
      await selectSession(
        orderedSessions.find((item) => item.session_id === requestedSessionId)
        ?? orderedSessions.find((item) => item.session_id === savedSessionId)
        ?? orderedSessions[0],
      )
    }
  } catch (err) {
    setError(err)
  } finally {
    loading.value = false
  }
}

async function selectSession(session: AgentSession) {
  const generation = ++selectionGeneration
  closeEventStream()
  selectedSession.value = session
  sessionStorage.setItem(selectedSessionStorageKey, session.session_id)
  mobileDrawerOpen.value = false
  history.value = []
  inbox.value = []
  nextCursor.value = null
  pendingApprovals.value = []
  currentRunId.value = activeRunFor(session.session_id)
  streamingText.value = ''
  resumeCommand.value = ''
  attachments.value = []
  liveTools.value = []
  resetTurnTiming()
  models.value = []
  selectedModel.value = null
  selectedReasoningEffort.value = null
  historyQuery.value = ''
  historyLoading.value = true
  if (currentRunId.value) void connectRunStream(session.session_id, currentRunId.value, true)
  try {
    modelLoading.value = true
    const [historyResponse, inboxResponse, modelResponse] = await Promise.all([
      getAgentHistory(session.session_id),
      session.entry.capabilities.message_inbox ? getAgentMessages(session.session_id) : Promise.resolve(null),
      getAgentModels(session.session_id).catch(() => null),
    ])
    if (generation !== selectionGeneration || selectedSession.value?.session_id !== session.session_id) return
    history.value = historyResponse.messages
    nextCursor.value = historyResponse.next_cursor
    inbox.value = inboxResponse?.messages ?? []
    models.value = modelResponse?.models ?? []
    selectedModel.value = modelResponse?.models.find((item) => item.is_current)?.id
      ?? modelResponse?.models.find((item) => item.is_default)?.id
      ?? modelResponse?.models[0]?.id
      ?? null
    selectedReasoningEffort.value = 'auto'
    await scrollHistoryToEnd()
  } catch (err) {
    if (generation === selectionGeneration && selectedSession.value?.session_id === session.session_id) {
      setError(err)
    }
  } finally {
    if (generation === selectionGeneration && selectedSession.value?.session_id === session.session_id) {
      historyLoading.value = false
      modelLoading.value = false
    }
  }
}

async function scrollHistoryToEnd() {
  await nextTick()
  if (historyRoot.value) historyRoot.value.scrollTop = historyRoot.value.scrollHeight
}

function stopPhaseTimer() {
  if (phaseTimer !== null) window.clearInterval(phaseTimer)
  phaseTimer = null
}

function formatRunDuration(milliseconds: number) {
  const seconds = Math.max(0, milliseconds) / 1000
  if (seconds < 60) return `${seconds.toFixed(1)} ${t('agentUi.secondsShort')}`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}

function updateRunTimers(now = Date.now()) {
  turnElapsedMs.value = turnStartedAt.value ? Math.max(0, now - turnStartedAt.value) : 0
  phaseElapsedMs.value = phaseStartedAt.value ? Math.max(0, now - phaseStartedAt.value) : 0
  thinkingElapsedMs.value = thinkingAccumulatedMs
    + (turnPhase.value === 'thinking' && phaseStartedAt.value ? Math.max(0, now - phaseStartedAt.value) : 0)
}

function resetTurnTiming(clearCompleted = true) {
  stopPhaseTimer()
  turnPhase.value = null
  turnPhaseDetail.value = ''
  turnStartedAt.value = 0
  phaseStartedAt.value = 0
  turnElapsedMs.value = 0
  phaseElapsedMs.value = 0
  thinkingElapsedMs.value = 0
  thinkingAccumulatedMs = 0
  turnPreviousAssistantId.value = ''
  if (clearCompleted) lastTurnMetrics.value = null
}

function setTurnPhase(phase: TurnPhase | null, detail = '') {
  const now = Date.now()
  const previousPhase = turnPhase.value
  if (previousPhase === 'thinking' && phase !== 'thinking' && phaseStartedAt.value) {
    thinkingAccumulatedMs += Math.max(0, now - phaseStartedAt.value)
  }
  turnPhase.value = phase
  turnPhaseDetail.value = detail.slice(0, 120)
  if (!phase) {
    stopPhaseTimer()
    phaseStartedAt.value = 0
    return
  }
  if (!turnStartedAt.value) turnStartedAt.value = now
  if (previousPhase !== phase || !phaseStartedAt.value) phaseStartedAt.value = now
  updateRunTimers(now)
  if (phaseTimer === null) {
    phaseTimer = window.setInterval(() => {
      updateRunTimers()
    }, 100)
  }
}

function finishTurnTiming(sessionId: string) {
  updateRunTimers()
  lastTurnMetrics.value = {
    sessionId,
    previousAssistantId: turnPreviousAssistantId.value,
    thinkingMs: thinkingElapsedMs.value,
    totalMs: turnElapsedMs.value,
  }
}

async function loadOlderHistory() {
  if (!selectedSession.value || !nextCursor.value) return
  const sessionId = selectedSession.value.session_id
  const generation = selectionGeneration
  const cursor = nextCursor.value
  historyLoading.value = true
  try {
    const response = await getAgentHistory(sessionId, cursor)
    if (generation !== selectionGeneration || selectedSession.value?.session_id !== sessionId) return
    history.value = [...response.messages, ...history.value]
    nextCursor.value = response.next_cursor
  } catch (err) {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) setError(err)
  } finally {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) historyLoading.value = false
  }
}

async function runHistorySearch() {
  if (!selectedSession.value || !historyQuery.value.trim()) return
  const sessionId = selectedSession.value.session_id
  const generation = selectionGeneration
  const query = historyQuery.value.trim()
  historyLoading.value = true
  try {
    const response = await searchAgentHistory(sessionId, query)
    if (generation !== selectionGeneration || selectedSession.value?.session_id !== sessionId) return
    history.value = response.messages
    nextCursor.value = null
  } catch (err) {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) setError(err)
  } finally {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) historyLoading.value = false
  }
}

async function reloadHistoryAfterTurn(sessionId: string, generation: number) {
  try {
    const response = await getAgentHistory(sessionId)
    if (generation !== selectionGeneration || selectedSession.value?.session_id !== sessionId) return
    history.value = response.messages
    nextCursor.value = response.next_cursor
    await scrollHistoryToEnd()
  } catch (err) {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) setError(err)
  }
}

function handleTurnEvent(sessionId: string, runId: string, event: MessageEvent<string>) {
  const payload = JSON.parse(event.data) as AgentTurnEvent
  const isSelectedRun = selectedSession.value?.session_id === sessionId && currentRunId.value === runId
  if (payload.type === 'approval_resolved' && payload.approval_id) {
    dismissedApprovalKeys.add(approvalKey(runId, payload.approval_id))
    pendingApprovals.value = pendingApprovals.value.filter((item) => item.runId !== runId || item.approvalId !== payload.approval_id)
    return
  }
  if (payload.type === 'completed' || payload.type === 'failed' || payload.type === 'interrupted') {
    forgetActiveRun(sessionId, runId)
    pendingApprovals.value = pendingApprovals.value.filter((item) => item.runId !== runId)
    if (!isSelectedRun) return
    streamingText.value = ''
    currentRunId.value = ''
    finishTurnTiming(sessionId)
    setTurnPhase(null)
    closeEventStream()
    if (payload.type === 'failed') {
      notifyError(t('agentUi.turnFailed', { code: payload.code ?? 'runtime_error' }), t('agentUi.runtimeUnavailable'))
    } else {
      void reloadHistoryAfterTurn(sessionId, selectionGeneration)
    }
    return
  }
  if (!isSelectedRun) return
  if (payload.type === 'phase' && payload.phase) setTurnPhase(payload.phase, payload.detail ?? '')
  if (payload.type === 'started') setTurnPhase('thinking')
  if (payload.type === 'text_delta') {
    setTurnPhase('responding')
    streamingText.value += payload.text ?? ''
    void scrollHistoryToEnd()
  }
  if (payload.type === 'tool') {
    const name = (payload.name ?? 'tool').slice(0, 120)
    liveTools.value = [...liveTools.value.filter((item) => item.name !== name), { name, status: payload.status ?? 'in_progress' }].slice(-8)
    setTurnPhase('tool_running', name)
  }
  if (payload.type === 'approval' && payload.approval_id) {
    setTurnPhase('waiting_approval')
    if (!dismissedApprovalKeys.has(approvalKey(runId, payload.approval_id))
      && !pendingApprovals.value.some((item) => item.runId === runId && item.approvalId === payload.approval_id)) {
      pendingApprovals.value.push({ runId, approvalId: payload.approval_id, kind: payload.kind ?? 'approval', summary: payload.summary ?? t('agentUi.approvalRequired'), resolving: false })
    }
  }
}

async function clearStaleRun(sessionId: string, runId: string, reloadHistory = true) {
  forgetActiveRun(sessionId, runId)
  pendingApprovals.value = pendingApprovals.value.filter((item) => item.runId !== runId)
  if (selectedSession.value?.session_id !== sessionId || currentRunId.value !== runId) return
  currentRunId.value = ''
  streamingText.value = ''
  setTurnPhase(null)
  closeEventStream()
  if (reloadHistory) await reloadHistoryAfterTurn(sessionId, selectionGeneration)
}

async function reconcileRunState(sessionId: string, runId: string, reloadHistory = true) {
  try {
    const operation = await getAgentTurnStatus(runId)
    if (operation.status === 'running') return true
    await clearStaleRun(sessionId, runId, reloadHistory)
    return false
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      await clearStaleRun(sessionId, runId, reloadHistory)
      return false
    }
    setError(err)
    return false
  }
}

async function recoverDisconnectedRun(sessionId: string, runId: string) {
  const stillRunning = await reconcileRunState(sessionId, runId)
  if (stillRunning && selectedSession.value?.session_id === sessionId && currentRunId.value === runId) {
    notifyError(t('agentUi.streamDisconnected'), t('agentUi.runtimeUnavailable'))
  }
}

async function connectRunStream(sessionId: string, runId: string, verifyStoredRun = false) {
  if (selectedSession.value?.session_id !== sessionId) return
  closeEventStream()
  currentRunId.value = runId
  if (!turnStartedAt.value) turnStartedAt.value = Date.now()
  setTurnPhase('thinking')
  const source = new EventSource(`/api/v1/agent-turns/${encodeURIComponent(runId)}/events`)
  eventSource = source
  const handler = (event: Event) => handleTurnEvent(sessionId, runId, event as MessageEvent<string>)
  for (const type of ['started', 'phase', 'text_delta', 'tool', 'approval', 'approval_resolved', 'completed', 'failed', 'interrupted']) source.addEventListener(type, handler)
  source.onerror = () => {
    if (eventSource !== source) return
    source.close()
    eventSource = null
    stopPhaseTimer()
    void recoverDisconnectedRun(sessionId, runId)
  }
}

async function submitTurn() {
  if (!selectedSession.value || (!composerText.value.trim() && !attachments.value.length) || turnBusy.value) return
  const sessionId = selectedSession.value.session_id
  const generation = selectionGeneration
  const text = composerText.value.trim()
  composerText.value = ''
  const pendingAttachments = attachments.value.map(({ name, media_type, data_base64 }) => ({ name, media_type, data_base64 }))
  const attachmentNames = attachments.value.map((item) => item.name)
  attachments.value = []
  liveTools.value = []
  startingSessionId.value = sessionId
  resetTurnTiming()
  turnPreviousAssistantId.value = latestAssistantMessageId.value
  turnStartedAt.value = Date.now()
  setTurnPhase('thinking')
  history.value.push({ message_id: `local-${Date.now()}`, role: 'user', text: [text, attachmentNames.length ? t('agentUi.attachmentsSent', { count: attachmentNames.length }) : ''].filter(Boolean).join('\n'), created_at: new Date().toISOString(), tool_summaries: [], source: selectedSession.value.agent.runtime === 'hermes' ? 'hermes' : 'codex' })
  void scrollHistoryToEnd()
  try {
    const reasoningEffort = selectedReasoningEffort.value === 'auto' ? null : selectedReasoningEffort.value
    const response = await startAgentTurn(sessionId, text, selectedModel.value, reasoningEffort, pendingAttachments)
    rememberActiveRun(sessionId, response.run_id)
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) {
      streamingText.value = ''
      connectRunStream(sessionId, response.run_id)
    }
  } catch (err) {
    if (generation === selectionGeneration && selectedSession.value?.session_id === sessionId) {
      setTurnPhase(null)
      attachments.value = pendingAttachments.map((item, index) => ({ ...item, id: `retry-${index}-${item.name}`, size: Math.floor(item.data_base64.length * 0.75) }))
      setError(err)
    }
  } finally {
    if (startingSessionId.value === sessionId) startingSessionId.value = ''
  }
}

async function fileToAttachment(file: File): Promise<PendingAttachment> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error ?? new Error('Unable to read attachment'))
    reader.readAsDataURL(file)
  })
  return {
    id: `${file.name}-${file.lastModified}-${file.size}`,
    name: file.name,
    media_type: file.type || 'application/octet-stream',
    data_base64: dataUrl.split(',', 2)[1] ?? '',
    size: file.size,
  }
}

async function addAttachments(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return
  if (attachments.value.length + files.length > 5) {
    error.value = t('agentUi.tooManyAttachments')
    return
  }
  if (files.some((file) => file.size > 10 * 1024 * 1024) || totalAttachmentBytes.value + files.reduce((sum, file) => sum + file.size, 0) > 20 * 1024 * 1024) {
    error.value = t('agentUi.attachmentTooLarge')
    return
  }
  try {
    attachments.value.push(...await Promise.all(files.map(fileToAttachment)))
  } catch (err) {
    setError(err)
  }
}

function removeAttachment(id: string) {
  attachments.value = attachments.value.filter((item) => item.id !== id)
}

function beginResize(event: PointerEvent) {
  if (window.innerWidth <= 760 || sessionPaneCollapsed.value) return
  resizing.value = true
  const startX = event.clientX
  const startWidth = sessionPaneWidth.value
  const move = (nextEvent: PointerEvent) => {
    sessionPaneWidth.value = Math.min(520, Math.max(260, startWidth + nextEvent.clientX - startX))
  }
  const stop = () => {
    resizing.value = false
    localStorage.setItem('ai-console-agent-pane-width', String(sessionPaneWidth.value))
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

function toggleSessionPane() {
  sessionPaneCollapsed.value = !sessionPaneCollapsed.value
  localStorage.setItem('ai-console-agent-pane-collapsed', String(sessionPaneCollapsed.value))
}

async function stopTurn() {
  if (!currentRunId.value) return
  const sessionId = selectedSession.value?.session_id
  const runId = currentRunId.value
  try {
    await interruptAgentTurn(runId)
  } catch (err) {
    if (sessionId && err instanceof ApiError && err.status === 404) {
      await clearStaleRun(sessionId, runId)
    } else {
      setError(err)
    }
  }
}

async function resolveApproval(approval: PendingApproval, decision: 'approve' | 'deny') {
  approval.resolving = true
  try {
    await resolveAgentApproval(approval.runId, approval.approvalId, decision)
    dismissedApprovalKeys.add(approvalKey(approval.runId, approval.approvalId))
    pendingApprovals.value = pendingApprovals.value.filter((item) => item.runId !== approval.runId || item.approvalId !== approval.approvalId)
  } catch (err) {
    const code = apiErrorCode(err)
    if (code === 'approval_not_found' || code === 'run_not_found') {
      dismissedApprovalKeys.add(approvalKey(approval.runId, approval.approvalId))
      pendingApprovals.value = pendingApprovals.value.filter((item) => item.runId !== approval.runId || item.approvalId !== approval.approvalId)
      notifyError(t('agentUi.approvalExpired'), t('agentUi.approvalRequired'))
    } else {
      setError(err)
    }
  } finally {
    approval.resolving = false
  }
}

async function dispatchTaskToRuntime() {
  if (!selectedSession.value || !taskBody.value.trim() || !canChat.value || turnBusy.value) return
  composerText.value = taskBody.value.trim()
  taskBody.value = ''
  workspaceTab.value = 'conversation'
  await submitTurn()
}

async function saveTaskToInbox() {
  if (!selectedSession.value || !taskBody.value.trim()) return
  sendingTask.value = true
  try {
    await sendAgentMessage(selectedSession.value.session_id, taskBody.value.trim(), taskType.value)
    taskBody.value = ''
    inbox.value = (await getAgentMessages(selectedSession.value.session_id)).messages
    await loadAgents()
  } catch (err) {
    setError(err)
  } finally {
    sendingTask.value = false
  }
}

async function copyText(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    copyState.value = 'copied'
  } catch {
    copyState.value = 'failed'
  }
  window.setTimeout(() => { copyState.value = 'idle' }, 1800)
}

async function handleAction(key: string) {
  if (!selectedSession.value) return
  try {
    if (key === 'archive') {
      await archiveAgentSession(selectedSession.value.session_id)
      sessionStorage.removeItem(selectedSessionStorageKey)
      selectedSession.value = null
      await loadAgents(false)
    } else if (key === 'unarchive') {
      await unarchiveAgentSession(selectedSession.value.session_id)
      await loadAgents()
    } else if (key === 'resume') {
      const response = await getAgentResumeHint(selectedSession.value.session_id)
      resumeCommand.value = response.command
      await copyText(response.command)
    } else if (key === 'rename') {
      renameValue.value = selectedSession.value.purpose || selectedSession.value.agent.display_name
      renameVisible.value = true
    } else if (key === 'delete') {
      deleteConfirmation.value = ''
      deleteVisible.value = true
    }
  } catch (err) {
    setError(err)
  }
}

async function confirmDelete() {
  if (!selectedSession.value?.external_session_id || deleteConfirmation.value !== selectedSession.value.external_session_id) return
  deleting.value = true
  try {
    const deletingSessionId = selectedSession.value.session_id
    await deleteAgentSourceSession(selectedSession.value.session_id, deleteConfirmation.value)
    deleteVisible.value = false
    selectedSession.value = null
    sessionStorage.removeItem(selectedSessionStorageKey)
    if (sessions.value) {
      sessions.value = {
        ...sessions.value,
        total: Math.max(0, sessions.value.total - 1),
        sessions: sessions.value.sessions.filter((item) => item.session_id !== deletingSessionId),
      }
    }
    await loadAgents(false)
  } catch (err) {
    setError(err)
  } finally {
    deleting.value = false
  }
}

async function confirmRename() {
  if (!selectedSession.value || !renameValue.value.trim()) return
  renaming.value = true
  try {
    const updated = await renameAgentSession(selectedSession.value.session_id, renameValue.value.trim())
    selectedSession.value = updated
    if (sessions.value) {
      sessions.value = {
        ...sessions.value,
        sessions: sessions.value.sessions.map((item) => item.session_id === updated.session_id ? updated : item),
      }
    }
    renameVisible.value = false
  } catch (err) {
    setError(err)
  } finally {
    renaming.value = false
  }
}

watch(showArchived, () => void loadAgents(false))
watch(selectedModel, () => {
  if (selectedReasoningEffort.value !== 'auto'
    && !selectedModelOption.value?.reasoning_efforts.includes(selectedReasoningEffort.value ?? '')) {
    selectedReasoningEffort.value = 'auto'
  }
})
onMounted(() => {
  const savedWidth = Number(localStorage.getItem('ai-console-agent-pane-width'))
  if (Number.isFinite(savedWidth)) sessionPaneWidth.value = Math.min(520, Math.max(260, savedWidth))
  sessionPaneCollapsed.value = localStorage.getItem('ai-console-agent-pane-collapsed') === 'true'
  void loadAgents()
})
onBeforeUnmount(closeEventStream)
</script>

<template>
  <section class="ops-page agent-workspace-page">
    <PageHeader :title="t('pages.agents.title')" :description="t('pages.agents.description')" />
    <AgentModuleNav />
    <div class="agent-workspace" :class="{ 'is-resizing': resizing, 'is-session-pane-collapsed': sessionPaneCollapsed }" :style="workspaceStyle">
      <aside v-if="!sessionPaneCollapsed" class="agent-session-sidebar">
        <div class="agent-session-sidebar__header">
          <strong>{{ t('agentUi.sessions') }}</strong>
          <span>{{ filteredSessions.length }}</span>
          <NButton quaternary circle size="small" :aria-label="t('agentUi.collapseSessions')" @click="toggleSessionPane">
            <template #icon><NIcon><ChevronBackOutline /></NIcon></template>
          </NButton>
        </div>
        <div class="agent-session-filters">
          <NInput v-model:value="searchText" clearable :placeholder="t('agentUi.searchSessions')" />
          <div>
            <NSelect v-model:value="runtimeFilter" :options="runtimeOptions" size="small" />
            <NSelect v-model:value="statusFilter" :options="statusOptions" size="small" />
          </div>
          <NCheckbox v-model:checked="showArchived">{{ t('agentUi.showArchived') }}</NCheckbox>
        </div>
        <div v-if="filteredSessions.length" class="agent-session-list">
          <button
            v-for="session in filteredSessions"
            :key="session.session_id"
            type="button"
            class="agent-session-item"
            :class="{ 'is-selected': selectedSession?.session_id === session.session_id }"
            @click="selectSession(session)"
          >
            <div>
              <strong>{{ session.purpose || session.agent.display_name }}</strong>
              <NTag size="tiny" :type="statusType(session.status)" :bordered="false">{{ statusText(session.status) }}</NTag>
            </div>
            <span>{{ session.agent.runtime }} · {{ sessionSource(session) }}</span>
            <span>{{ dateTime(session.last_seen_at) }}</span>
            <span v-if="session.archived_at">{{ t('agentUi.archived') }}</span>
          </button>
        </div>
        <NEmpty v-else class="agent-session-empty" :description="sessions?.total ? t('agentUi.noFilteredSessions') : t('agentUi.noSessions')" />
      </aside>

      <div v-if="!sessionPaneCollapsed" class="agent-workspace-resizer" role="separator" aria-orientation="vertical" :aria-label="t('agentUi.resizePanels')" @pointerdown.prevent="beginResize">
        <span />
      </div>

      <main v-if="selectedSession" class="agent-conversation">
        <header class="agent-conversation-header">
          <NButton class="agent-session-pane-trigger" quaternary circle size="small" :aria-label="sessionPaneCollapsed ? t('agentUi.expandSessions') : t('agentUi.collapseSessions')" @click="sessionPaneCollapsed ? toggleSessionPane() : mobileDrawerOpen = true">
            <template #icon><NIcon><component :is="sessionPaneCollapsed ? ChevronForwardOutline : MenuOutline" /></NIcon></template>
          </NButton>
          <div class="agent-conversation-identity">
            <div class="agent-conversation-title">
              <strong>{{ selectedSession.purpose || selectedSession.agent.display_name }}</strong>
              <NButton text size="tiny" @click="handleAction('rename')">{{ t('agentUi.rename') }}</NButton>
              <NTag size="small" :bordered="false">{{ selectedSession.agent.runtime }}</NTag>
              <NTag v-if="selectedSession.archived_at" size="small" type="warning" :bordered="false">{{ t('agentUi.archived') }}</NTag>
            </div>
            <span>{{ selectedSession.external_session_id }} · {{ sessionSource(selectedSession) }}</span>
          </div>
          <div class="agent-conversation-actions">
            <NTag :type="runtimeStatus?.available ? 'success' : 'warning'" :bordered="false">{{ runtimeStatus?.available ? t('agentUi.bridgeOnline') : t('agentUi.bridgeOffline') }}</NTag>
            <NDropdown trigger="click" :options="actionOptions" @select="handleAction"><NButton size="small" secondary>{{ t('agentUi.moreActions') }}</NButton></NDropdown>
          </div>
        </header>

        <NTabs v-model:value="workspaceTab" type="line" animated class="agent-workspace-tabs">
          <NTabPane name="conversation" :tab="t('agentUi.conversation')" class="agent-conversation-pane">
            <div class="agent-history-tools">
              <NButton v-if="nextCursor" size="tiny" secondary :loading="historyLoading" @click="loadOlderHistory">{{ t('agentUi.loadOlder') }}</NButton>
              <div>
                <NInput v-model:value="historyQuery" size="small" clearable :placeholder="t('agentUi.searchHistory')" @keyup.enter="runHistorySearch" />
                <NButton size="small" :disabled="!historyQuery.trim()" @click="runHistorySearch">{{ t('agentUi.search') }}</NButton>
              </div>
            </div>

            <div ref="historyRoot" class="agent-history">
              <NSpin v-if="historyLoading && !history.length" size="small" />
              <template v-else-if="history.length || streamingText">
                <article v-for="message in history" :key="message.message_id" class="agent-history-message" :class="`is-${message.role}`">
                  <div class="agent-message-avatar">{{ message.role === 'user' ? t('agentUi.role.user').slice(0, 1) : message.role === 'tool' ? 'T' : 'AI' }}</div>
                  <div class="agent-message-body">
                    <div class="agent-message-meta"><strong>{{ t(`agentUi.role.${message.role}`) }}</strong><span>{{ message.created_at ? dateTime(message.created_at) : '' }}</span></div>
                    <AgentMarkdown v-if="message.text" :content="message.text" />
                    <div v-if="message.tool_summaries.length" class="agent-tool-list">
                      <NTag v-for="tool in message.tool_summaries" :key="`${message.message_id}-${tool.name}`" size="small" :bordered="false">{{ tool.name }} · {{ tool.status }}</NTag>
                    </div>
                    <div
                      v-if="message.message_id === latestAssistantMessageId && lastTurnMetrics?.sessionId === selectedSession.session_id && latestAssistantMessageId !== lastTurnMetrics.previousAssistantId"
                      class="agent-response-metrics"
                    >
                      {{ t('agentUi.turnMetrics', { thinking: formatRunDuration(lastTurnMetrics.thinkingMs), total: formatRunDuration(lastTurnMetrics.totalMs) }) }}
                    </div>
                  </div>
                </article>
                <div v-if="turnPhase" class="agent-run-state">
                  <span class="agent-run-pulse" aria-hidden="true"><i /><i /><i /></span>
                  <div class="agent-run-state__body">
                    <div><strong>{{ turnPhaseLabel }}</strong><span>{{ t('agentUi.currentPhaseElapsed', { duration: formatRunDuration(phaseElapsedMs) }) }}</span></div>
                    <span v-if="turnPhaseDetail">{{ turnPhaseDetail }}</span>
                    <span v-else-if="turnPhase !== 'thinking' && thinkingElapsedMs">{{ t('agentUi.thoughtFor', { duration: formatRunDuration(thinkingElapsedMs) }) }}</span>
                  </div>
                  <time>{{ t('agentUi.totalElapsed', { duration: formatRunDuration(turnElapsedMs) }) }}</time>
                </div>
                <div v-if="liveTools.length" class="agent-live-tools">
                  <NTag v-for="tool in liveTools" :key="tool.name" size="small" :bordered="false">{{ tool.name }} · {{ tool.status }}</NTag>
                </div>
                <article v-if="streamingText" class="agent-history-message is-assistant is-streaming">
                  <div class="agent-message-avatar">AI</div>
                  <div class="agent-message-body"><div class="agent-message-meta"><strong>{{ t('agentUi.role.assistant') }}</strong><span>{{ t('agentUi.generating') }}</span></div><AgentMarkdown :content="streamingText" /></div>
                </article>
              </template>
              <NEmpty v-else :description="t('agentUi.noHistory')" />
            </div>

            <div v-if="activeApproval" class="agent-approval-list">
              <article :key="`${activeApproval.runId}-${activeApproval.approvalId}`" class="agent-approval-card">
                <div>
                  <div><strong>{{ t('agentUi.approvalRequired') }}</strong><span>{{ activeApproval.kind }}</span></div>
                  <NTag v-if="remainingApprovalCount" size="small" :bordered="false">{{ t('agentUi.approvalRemaining', { count: remainingApprovalCount }) }}</NTag>
                </div>
                <p>{{ activeApproval.summary }}</p>
                <div>
                  <NButton class="agent-approval-deny" size="small" secondary :loading="activeApproval.resolving" @click="resolveApproval(activeApproval, 'deny')">{{ t('agentUi.deny') }}</NButton>
                  <NButton class="agent-approval-approve" size="small" type="primary" :loading="activeApproval.resolving" @click="resolveApproval(activeApproval, 'approve')">{{ t('agentUi.approve') }}</NButton>
                </div>
              </article>
            </div>

            <div class="agent-chat-composer">
              <div v-if="attachments.length" class="agent-attachment-list">
                <div v-for="attachment in attachments" :key="attachment.id" class="agent-attachment-chip">
                  <div><strong>{{ attachment.name }}</strong><span>{{ formatFileSize(attachment.size) }}</span></div>
                  <NButton text size="tiny" :aria-label="t('agentUi.removeAttachment')" @click="removeAttachment(attachment.id)">×</NButton>
                </div>
              </div>
              <NInput class="agent-chat-input" v-model:value="composerText" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :maxlength="20000" :disabled="!canChat || turnBusy" :placeholder="canChat ? t('agentUi.continuePlaceholder') : t('agentUi.bridgeRequired')" @keydown.ctrl.enter.prevent="submitTurn" />
              <div class="agent-composer-toolbar">
                <div>
                  <NButton quaternary circle size="small" :aria-label="t('agentUi.attachFile')" :disabled="attachments.length >= 5 || turnBusy" @click="attachmentInput?.click()"><template #icon><NIcon><AttachOutline /></NIcon></template></NButton>
                  <input ref="attachmentInput" class="agent-file-input" type="file" multiple @change="addAttachments">
                  <NSelect v-model:value="selectedModel" class="agent-model-select" size="small" filterable :loading="modelLoading" :options="modelOptions" :placeholder="t('agentUi.selectModel')" />
                  <NSelect v-if="reasoningOptions.length > 1" v-model:value="selectedReasoningEffort" class="agent-reasoning-select" size="small" :disabled="turnBusy" :options="reasoningOptions" :placeholder="t('agentUi.reasoning')" />
                </div>
                <div>
                  <span>{{ t('agentUi.inputHint') }}</span>
                  <NButton v-if="currentRunId" circle type="warning" :aria-label="t('agentUi.stopGenerating')" @click="stopTurn"><template #icon><NIcon><StopCircleOutline /></NIcon></template></NButton>
                  <NButton v-else class="agent-send-button" circle type="primary" :loading="turnStartingForSelected" :aria-label="t('agentUi.send')" :disabled="!canChat || turnBusy || (!composerText.trim() && !attachments.length)" @click="submitTurn"><template #icon><NIcon><SendOutline /></NIcon></template></NButton>
                </div>
              </div>
            </div>
          </NTabPane>

          <NTabPane name="tasks" :tab="`${t('agentUi.taskInbox')} (${inbox.length})`" class="agent-task-pane">
            <p class="agent-task-hint">{{ t('agentUi.taskDeliveryHint') }}</p>
            <div class="agent-task-compose">
              <NSelect v-model:value="taskType" :options="taskTypeOptions" size="small" />
              <NInput v-model:value="taskBody" type="textarea" :maxlength="2000" show-count :placeholder="t('agentUi.messagePlaceholder')" />
              <div class="agent-task-actions">
                <NButton secondary :loading="sendingTask" :disabled="!taskBody.trim()" @click="saveTaskToInbox">{{ t('agentUi.saveToInbox') }}</NButton>
                <NButton type="primary" :disabled="!canChat || turnBusy || !taskBody.trim()" @click="dispatchTaskToRuntime">{{ t('agentUi.sendAndRun') }}</NButton>
              </div>
            </div>
            <div v-if="inbox.length" class="agent-message-list">
              <article v-for="message in inbox" :key="message.message_id" class="agent-message-item">
                <div><NTag size="small" :bordered="false">{{ t(`agentUi.messageType.${message.message_type}`) }}</NTag><span>{{ dateTime(message.created_at) }}</span></div>
                <p>{{ message.body }}</p>
                <NTag size="small" :bordered="false">{{ t(`agentUi.messageStatus.${message.status}`) }}</NTag>
              </article>
            </div>
            <NEmpty v-else :description="t('agentUi.noMessages')" />
          </NTabPane>
        </NTabs>
      </main>

      <main v-else class="agent-conversation agent-conversation-empty">
        <NButton v-if="sessionPaneCollapsed" class="agent-empty-pane-trigger" secondary @click="toggleSessionPane">{{ t('agentUi.expandSessions') }}</NButton>
        <NEmpty :description="t('agentUi.selectSession')" />
      </main>
    </div>

    <NDrawer v-model:show="mobileDrawerOpen" class="agent-session-drawer" placement="left" :width="mobileDrawerWidth">
      <NDrawerContent :title="t('agentUi.sessions')" closable>
        <div class="agent-session-filters">
          <NInput v-model:value="searchText" clearable :placeholder="t('agentUi.searchSessions')" />
          <div><NSelect v-model:value="runtimeFilter" :options="runtimeOptions" size="small" /><NSelect v-model:value="statusFilter" :options="statusOptions" size="small" /></div>
          <NCheckbox v-model:checked="showArchived">{{ t('agentUi.showArchived') }}</NCheckbox>
        </div>
        <div class="agent-session-list">
          <button v-for="session in filteredSessions" :key="session.session_id" type="button" class="agent-session-item" :class="{ 'is-selected': selectedSession?.session_id === session.session_id }" @click="selectSession(session)">
            <div><strong>{{ session.purpose || session.agent.display_name }}</strong><NTag size="tiny" :type="statusType(session.status)" :bordered="false">{{ statusText(session.status) }}</NTag></div>
            <span>{{ session.agent.runtime }} · {{ sessionSource(session) }}</span><span>{{ dateTime(session.last_seen_at) }}</span>
          </button>
        </div>
      </NDrawerContent>
    </NDrawer>

    <NAlert v-if="copyState !== 'idle'" :type="copyState === 'copied' ? 'success' : 'error'" class="agent-copy-feedback">
      {{ copyState === 'copied' ? t('agentUi.resumeCopied') : t('agentUi.copyFailed') }}<code v-if="resumeCommand">{{ resumeCommand }}</code>
    </NAlert>

    <NModal v-model:show="deleteVisible" preset="dialog" type="error" :title="t('agentUi.deleteSource')">
      <p>{{ t('agentUi.deleteWarning') }}</p>
      <code>{{ selectedSession?.external_session_id }}</code>
      <NInput v-model:value="deleteConfirmation" :placeholder="t('agentUi.typeSessionId')" />
      <template #action>
        <NButton @click="deleteVisible = false">{{ t('agentUi.cancel') }}</NButton>
        <NButton type="error" :loading="deleting" :disabled="deleteConfirmation !== selectedSession?.external_session_id" @click="confirmDelete">{{ t('agentUi.confirmDelete') }}</NButton>
      </template>
    </NModal>

    <NModal v-model:show="renameVisible" preset="dialog" :title="t('agentUi.renameSession')">
      <NInput v-model:value="renameValue" :maxlength="120" show-count :placeholder="t('agentUi.sessionNamePlaceholder')" @keyup.enter="confirmRename" />
      <template #action>
        <NButton @click="renameVisible = false">{{ t('agentUi.cancel') }}</NButton>
        <NButton type="primary" :loading="renaming" :disabled="!renameValue.trim()" @click="confirmRename">{{ t('agentUi.saveName') }}</NButton>
      </template>
    </NModal>
  </section>
</template>
