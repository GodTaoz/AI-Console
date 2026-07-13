export const uiMessages = {
  'zh-CN': {
    status: { ok: '正常', warning: '警告', critical: '严重', unsupported: '不支持', permission_denied: '无权限', unknown: '未知' },
    common: { refresh: '刷新', collectNow: '立即采集', collectedAt: '采集时间', notCollected: '尚未采集', noData: '暂无数据', items: '项', status: '状态', loadFailed: '数据加载失败', last24Hours: '最近 24 小时' },
    header: { title: '运行监控', hint: '查看主机、容器和额度的最新状态', menu: '显示或隐藏导航', theme: '切换主题', language: '选择语言' },
    footer: { product: 'AI-Console', description: '单机自托管 AI 工作站健康与额度预警中心', mode: '只读模式' },
    overviewUi: {
      allOk: '所有核心监控项运行正常', hasIssues: '存在需要处理的监控事件', coreContainers: '核心容器', quotaAccounts: '额度账号', activeIssues: '活动问题', dataState: '数据状态', fresh: '最新', stale: '已过期',
      host: '主机', storage: '存储', quota: '额度', containers: '容器', events: '事件', memory: '内存占用', cpu: 'CPU 使用率', resourceTrend: '资源使用趋势', temperature: '最高温度', battery: '电池电量', root: '根分区', nas: 'NAS', used: '已用', resetsIn: '{duration}后重置', resetUnknown: '重置时间未知', running: '运行中', stopped: '已停止', healthPassed: '健康检查通过', healthFailed: '健康检查失败', healthStarting: '检查中', healthNone: '未配置健康检查', noIssues: '当前没有需要处理的问题。', noQuota: '暂无额度数据', uptime: '运行时间'
    },
    hostUi: {
      cpu: 'CPU 使用率', memory: '内存占用', uptime: '运行时间', temperature: '最高温度', throughput: '实时吞吐', liveThroughput: '当前吞吐', resourceTrend: 'CPU 与内存趋势', networkTrend: '网络吞吐趋势', diskTrend: '磁盘读写趋势', cores: '逻辑核心', diskRead: '磁盘读取', diskWrite: '磁盘写入', networkReceive: '网络接收', networkSend: '网络发送', systemInfo: '系统信息', hostname: '主机名', hardware: '硬件型号', os: '操作系统', kernel: '内核', cpuModel: '处理器', ip: '主 IP 地址', cpuProcesses: 'CPU 占用排行', memoryProcesses: '内存占用排行', pid: 'PID', process: '进程', cpuPercent: 'CPU', memoryPercent: '内存', rss: '常驻内存', power: '电源', rootDisk: '根分区', swap: 'Swap', issues: '资源事件', acOnline: '交流电在线', batteryOrUnknown: '电池供电或状态未知'
    },
    containerUi: { total: '容器总数', running: '正在运行', stopped: '已停止', coreHealthy: '核心容器健康', list: '容器列表', portMappings: '{count} 个端口映射', container: '容器', runtime: '运行状态', health: '健康检查', ports: '端口映射', uptime: '运行时间', passed: '通过', failed: '失败', checking: '检查中', notConfigured: '未配置', events: '事件', noContainers: '暂无容器数据' },
    quotaUi: { accounts: '额度账号', available: '可用账号', averageRemaining: '平均剩余', averageUsed: '平均已用', source: '数据源', accountStatusOk: '账号状态正常', accountStatusBad: '{count} 个账号异常', pool: '额度使用', used: '已用 {value}', reset: '{duration}后重置', noQuota: '暂无额度数据', events: '额度事件', noEvents: '暂无额度事件', readOnly: '只读管理接口' },
    networkUi: { riskVolumes: '异常存储卷', nasUsage: 'NAS 占用', interface: '主网卡', mounts: '挂载点', mount: '挂载点', usedCapacity: '已用 / 总容量', usage: '使用率', volumes: '存储卷', network: '网络吞吐', receive: '接收速率', send: '发送速率', cumulativeReceive: '累计接收', cumulativeSend: '累计发送', totalShort: '累计 {value}', allVolumesOk: '所有存储卷状态正常', volumeIssue: '存在容量或挂载异常' },
    securityUi: { firewall: '防火墙状态', provider: '防火墙', firewallState: '运行状态', enabled: '已启用', disabled: '未启用', allowRules: '允许规则', listeningCount: '非本机监听 / 总数', allowedPorts: '防火墙允许规则', listeningPorts: '主机监听端口', port: '端口', protocol: '协议', source: '来源范围', addressFamily: '地址族', listenAddress: '监听地址', exposure: '监听范围', anywhere: '任意来源', noRules: '未读取到允许规则', noListeningPorts: '未发现监听端口', explanation: '防火墙允许规则表示流量策略；监听端口表示主机服务正在接收连接。两者含义不同，应结合查看。', scope: { loopback: '仅本机', all_interfaces: '所有网卡', specific_address: '指定地址' } },
    alertUi: { active: '活动告警', resolved: '最近恢复', event: '事件', severity: '级别', firstSeenLabel: '首次出现', lastSeenLabel: '最近出现', resolvedAt: '恢复时间', occurrencesLabel: '次数', noActive: '暂无活动告警', noResolved: '暂无已恢复事件', activeCount: '{count} 个活动告警', none: '当前无活动告警', firstSeen: '首次 {time}', lastSeen: '最近 {time} · {count} 次', occurrences: '累计 {count} 次', resolvedStatus: '已恢复' }
    ,issues: { filesystem_missing: '文件系统未挂载', filesystem_capacity_high: '文件系统容量不足', memory_capacity_high: '内存使用率较高', memory_capacity_critical: '内存使用率严重过高', temperature_high: '系统温度较高', temperature_critical: '系统温度严重过高', docker_unavailable: '无法连接容器服务', core_container_missing: '核心容器缺失', cpa_management_key_missing: '未配置 CPA 管理密钥', cpa_auth_files_failed: '无法读取 CPA 账号', cpa_quota_fetch_failed: '额度请求失败', cpa_quota_missing: '额度数据不可用', cpa_account_disabled: '额度账号已禁用', resources_collection_failed: '主机数据采集失败', docker_collection_failed: '容器数据采集失败', quota_collection_failed: '额度数据采集失败' }
  },
  'en-US': {
    status: { ok: 'Healthy', warning: 'Warning', critical: 'Critical', unsupported: 'Unsupported', permission_denied: 'Permission denied', unknown: 'Unknown' },
    common: { refresh: 'Refresh', collectNow: 'Collect now', collectedAt: 'Collected', notCollected: 'Not collected', noData: 'No data', items: 'items', status: 'Status', loadFailed: 'Failed to load data', last24Hours: 'Last 24 hours' },
    header: { title: 'Operations', hint: 'Monitor host, container, and quota status', menu: 'Show or hide navigation', theme: 'Toggle theme', language: 'Choose language' },
    footer: { product: 'AI-Console', description: 'Health and quota alerts for a self-hosted AI workstation', mode: 'Read-only' },
    overviewUi: {
      allOk: 'All core monitors are healthy', hasIssues: 'Monitoring events require attention', coreContainers: 'Core containers', quotaAccounts: 'Quota accounts', activeIssues: 'Active issues', dataState: 'Data status', fresh: 'Fresh', stale: 'Stale',
      host: 'Host', storage: 'Storage', quota: 'Quota', containers: 'Containers', events: 'Events', memory: 'Memory usage', cpu: 'CPU usage', resourceTrend: 'Resource usage trend', temperature: 'Peak temperature', battery: 'Battery', root: 'Root volume', nas: 'NAS', used: 'Used', resetsIn: 'Resets in {duration}', resetUnknown: 'Reset time unknown', running: 'Running', stopped: 'Stopped', healthPassed: 'Health check passed', healthFailed: 'Health check failed', healthStarting: 'Checking', healthNone: 'No health check', noIssues: 'No issues require action.', noQuota: 'No quota data', uptime: 'Uptime'
    },
    hostUi: {
      cpu: 'CPU usage', memory: 'Memory usage', uptime: 'Uptime', temperature: 'Peak temperature', throughput: 'Live throughput', liveThroughput: 'Current throughput', resourceTrend: 'CPU and memory trend', networkTrend: 'Network throughput trend', diskTrend: 'Disk I/O trend', cores: 'logical cores', diskRead: 'Disk read', diskWrite: 'Disk write', networkReceive: 'Network receive', networkSend: 'Network send', systemInfo: 'System information', hostname: 'Hostname', hardware: 'Hardware', os: 'Operating system', kernel: 'Kernel', cpuModel: 'Processor', ip: 'Primary IP', cpuProcesses: 'Top CPU processes', memoryProcesses: 'Top memory processes', pid: 'PID', process: 'Process', cpuPercent: 'CPU', memoryPercent: 'Memory', rss: 'Resident memory', power: 'Power', rootDisk: 'Root volume', swap: 'Swap', issues: 'Resource events', acOnline: 'AC connected', batteryOrUnknown: 'Battery power or unknown state'
    },
    containerUi: { total: 'Total containers', running: 'Running', stopped: 'Stopped', coreHealthy: 'Healthy core containers', list: 'Containers', portMappings: '{count} port mappings', container: 'Container', runtime: 'Runtime', health: 'Health check', ports: 'Ports', uptime: 'Uptime', passed: 'Passed', failed: 'Failed', checking: 'Checking', notConfigured: 'Not configured', events: 'Events', noContainers: 'No container data' },
    quotaUi: { accounts: 'Quota accounts', available: 'Available accounts', averageRemaining: 'Average remaining', averageUsed: 'Average used', source: 'Source', accountStatusOk: 'All accounts available', accountStatusBad: '{count} accounts unavailable', pool: 'Quota usage', used: 'Used {value}', reset: 'Resets in {duration}', noQuota: 'No quota data', events: 'Quota events', noEvents: 'No quota events', readOnly: 'Read-only management API' },
    networkUi: { riskVolumes: 'Volumes with issues', nasUsage: 'NAS usage', interface: 'Primary interface', mounts: 'Mounts', mount: 'Mount', usedCapacity: 'Used / total', usage: 'Usage', volumes: 'Volumes', network: 'Network throughput', receive: 'Receive rate', send: 'Send rate', cumulativeReceive: 'Total received', cumulativeSend: 'Total sent', totalShort: 'Total {value}', allVolumesOk: 'All volumes are healthy', volumeIssue: 'Capacity or mount issue detected' },
    securityUi: { firewall: 'Firewall status', provider: 'Firewall', firewallState: 'State', enabled: 'Enabled', disabled: 'Disabled', allowRules: 'Allow rules', listeningCount: 'Non-loopback / total', allowedPorts: 'Firewall allow rules', listeningPorts: 'Host listening ports', port: 'Port', protocol: 'Protocol', source: 'Source range', addressFamily: 'Address family', listenAddress: 'Listen address', exposure: 'Listen scope', anywhere: 'Anywhere', noRules: 'No allow rules were found', noListeningPorts: 'No listening ports were found', explanation: 'Firewall allow rules describe traffic policy. Listening ports describe services accepting connections. Review both together.', scope: { loopback: 'Loopback only', all_interfaces: 'All interfaces', specific_address: 'Specific address' } },
    alertUi: { active: 'Active alerts', resolved: 'Recently resolved', event: 'Event', severity: 'Severity', firstSeenLabel: 'First seen', lastSeenLabel: 'Last seen', resolvedAt: 'Resolved at', occurrencesLabel: 'Count', noActive: 'No active alerts', noResolved: 'No resolved events', activeCount: '{count} active alerts', none: 'No active alerts', firstSeen: 'First seen {time}', lastSeen: 'Last seen {time} · {count} times', occurrences: '{count} occurrences', resolvedStatus: 'Resolved' }
    ,issues: { filesystem_missing: 'Filesystem is not mounted', filesystem_capacity_high: 'Filesystem capacity is low', memory_capacity_high: 'Memory usage is high', memory_capacity_critical: 'Memory usage is critically high', temperature_high: 'System temperature is high', temperature_critical: 'System temperature is critically high', docker_unavailable: 'Container service is unavailable', core_container_missing: 'Core container is missing', cpa_management_key_missing: 'CPA management key is not configured', cpa_auth_files_failed: 'CPA accounts could not be loaded', cpa_quota_fetch_failed: 'Quota request failed', cpa_quota_missing: 'Quota data is unavailable', cpa_account_disabled: 'Quota account is disabled', resources_collection_failed: 'Host collection failed', docker_collection_failed: 'Container collection failed', quota_collection_failed: 'Quota collection failed' }
  }
} as const

function messageKeys(value: object, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return item && typeof item === 'object' ? messageKeys(item, path) : [path]
  })
}

export function assertUiMessageParity() {
  const zhKeys = messageKeys(uiMessages['zh-CN'])
  const enKeys = messageKeys(uiMessages['en-US'])
  if (zhKeys.join('\n') !== enKeys.join('\n')) {
    throw new Error('UI locale message keys do not match')
  }
}
