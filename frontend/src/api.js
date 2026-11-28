// 所有后端请求集中在这里，组件里只调函数、不写 fetch 细节
const JSON_HEADERS = { 'Content-Type': 'application/json' }

export function getToken() {
  return localStorage.getItem('access_token') || ''
}

export function setToken(token) {
  localStorage.setItem('access_token', token || '')
}

function tokenHeader() {
  const token = getToken()
  return token ? { 'X-Access-Token': token } : {}
}

function authHeaders() {
  const headers = { ...JSON_HEADERS }
  const token = getToken()
  if (token) headers['X-Access-Token'] = token
  return headers
}

async function toJson(res) {
  if (res.status === 401) throw new Error('需要访问口令，请点右上角“设置口令”')
  if (res.status === 429) throw new Error('请求太频繁，请稍后再试')
  if (!res.ok) throw new Error('HTTP ' + res.status)
  return res.json()
}

// 通用 SSE 读取：按行解析 data: 帧
async function readSSE(res, onEvent) {
  if (res.status === 401) throw new Error('需要访问口令，请点右上角“设置口令”')
  if (res.status === 429) throw new Error('请求太频繁，请稍后再试')
  if (!res.ok) throw new Error('HTTP ' + res.status)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') continue
      try {
        onEvent(JSON.parse(data))
      } catch {
        /* 忽略心跳或非 JSON 帧 */
      }
    }
  }
}

// ---------- 会话 ----------
export async function listSessions() {
  const data = await toJson(await fetch('/api/sessions'))
  return data.sessions || []
}

export async function createSession(title = '新会话') {
  return toJson(
    await fetch('/api/sessions', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ title }),
    }),
  )
}

export async function getSession(sessionId) {
  return toJson(await fetch(`/api/sessions/${sessionId}`))
}

export async function deleteSession(sessionId) {
  return toJson(await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' }))
}

// ---------- 问答（SSE 流式） ----------
export async function askStream(question, sessionId, onEvent, mode = 'quality', kb = 'fastapi', web = false) {
  const res = await fetch('/api/ask/stream', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ question, session_id: sessionId, mode, kb, web }),
  })
  await readSSE(res, onEvent)
}

// ---------- Agent ----------
export async function runAgent(task) {
  return toJson(
    await fetch('/api/agent/run', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ task }),
    }),
  )
}

export async function agentStream(task, sessionId, onEvent) {
  const res = await fetch('/api/agent/stream', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ task, session_id: sessionId }),
  })
  await readSSE(res, onEvent)
}

export async function approveAgent(runId, approved) {
  return toJson(
    await fetch('/api/agent/approve', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ run_id: runId, approved }),
    }),
  )
}

// ---------- 统计 ----------
export async function getStats() {
  return toJson(await fetch('/api/stats'))
}

export async function getDailyStats(days = 7) {
  return toJson(await fetch(`/api/stats/daily?days=${days}`))
}


// ---------- 知识库 ----------
export async function listKbs() {
  const data = await toJson(await fetch('/api/kbs', { headers: tokenHeader() }))
  return data.items || []
}

export async function createKb(name) {
  return toJson(
    await fetch('/api/kbs', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ name }),
    }),
  )
}

export async function deleteKb(kbId) {
  return toJson(
    await fetch(`/api/kbs/${kbId}`, { method: 'DELETE', headers: tokenHeader() }),
  )
}

export async function uploadDocument(kbId, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`/api/kbs/${kbId}/documents`, {
    method: 'POST',
    headers: tokenHeader(),
    body: form,
  })
  if (res.status === 401) throw new Error('需要访问口令')
  if (!res.ok) throw new Error('HTTP ' + res.status)
  return res.json()
}

export async function renameKb(kbId, name) {
  return toJson(
    await fetch(`/api/kbs/${kbId}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ name }),
    }),
  )
}


// ---------- 监控 ----------
export async function listWatch() {
  const data = await toJson(await fetch('/api/watchlist', { headers: authHeaders() }))
  return data.items || []
}

export async function addWatch(symbol) {
  return toJson(await fetch('/api/watchlist', {
    method: 'POST', headers: authHeaders(), body: JSON.stringify({ symbol }),
  }))
}

export async function removeWatch(symbol) {
  return toJson(await fetch(`/api/watchlist/${symbol}`, { method: 'DELETE', headers: authHeaders() }))
}

export async function listAlerts(limit = 50) {
  const data = await toJson(await fetch(`/api/alerts?limit=${limit}`, { headers: authHeaders() }))
  return data.items || []
}

export async function ackAlert(id) {
  return toJson(await fetch(`/api/alerts/${id}/ack`, { method: 'POST', headers: authHeaders() }))
}

export async function scanMonitor() {
  return toJson(await fetch('/api/monitor/scan', { method: 'POST', headers: authHeaders() }))
}

export async function getMonitorStatus() {
  return toJson(await fetch('/api/monitor/status', { headers: authHeaders() }))
}


// ---------- 行情图表 ----------
export async function getKline(symbol, period = 'day', count = 120) {
  const data = await toJson(
    await fetch(`/api/kline?symbol=${symbol}&period=${period}&count=${count}`, {
      headers: authHeaders(),
    }),
  )
  return data.bars || []
}

export async function getSectors(limit = 16) {
  const data = await toJson(await fetch(`/api/sectors?limit=${limit}`, { headers: authHeaders() }))
  return data.items || []
}

export async function getSectorStocks(code, limit = 10) {
  const data = await toJson(
    await fetch(`/api/sectors/${code}/stocks?limit=${limit}`, { headers: authHeaders() }),
  )
  return data.items || []
}


// ---------- 今日综述 ----------
export async function getBrief(force = false) {
  return toJson(await fetch(`/api/brief${force ? '?force=1' : ''}`, { headers: authHeaders() }))
}
