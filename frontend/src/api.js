// 所有后端请求集中在这里，组件里只调函数、不写 fetch 细节
const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function toJson(res) {
  if (!res.ok) throw new Error('HTTP ' + res.status)
  return res.json()
}

// 通用 SSE 读取：按行解析 data: 帧
async function readSSE(res, onEvent) {
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
      headers: JSON_HEADERS,
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
export async function askStream(question, sessionId, onEvent, mode = 'quality') {
  const res = await fetch('/api/ask/stream', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ question, session_id: sessionId, mode }),
  })
  await readSSE(res, onEvent)
}

// ---------- Agent ----------
export async function runAgent(task) {
  return toJson(
    await fetch('/api/agent/run', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ task }),
    }),
  )
}

export async function agentStream(task, sessionId, onEvent) {
  const res = await fetch('/api/agent/stream', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ task, session_id: sessionId }),
  })
  await readSSE(res, onEvent)
}

export async function approveAgent(runId, approved) {
  return toJson(
    await fetch('/api/agent/approve', {
      method: 'POST',
      headers: JSON_HEADERS,
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
