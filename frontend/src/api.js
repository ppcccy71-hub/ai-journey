// 所有后端请求集中在这里，组件里只调函数、不写 fetch 细节
const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function toJson(res) {
  if (!res.ok) throw new Error('HTTP ' + res.status)
  return res.json()
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
export async function askStream(question, sessionId, onEvent) {
  const res = await fetch('/api/ask/stream', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ question, session_id: sessionId }),
  })
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
        /* 忽略解析失败的心跳帧 */
      }
    }
  }
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

// ---------- 统计 ----------
export async function getStats() {
  return toJson(await fetch('/api/stats'))
}

export async function getDailyStats(days = 7) {
  return toJson(await fetch(`/api/stats/daily?days=${days}`))
}
