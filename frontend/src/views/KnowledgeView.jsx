// 知识库管理页：列表、新建、上传、删除
import { useEffect, useRef, useState } from 'react'
import { listKbs, createKb, deleteKb, uploadDocument, renameKb } from '../api'

export default function KnowledgeView({ kb, onSelect, onChanged }) {
  const [items, setItems] = useState([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState('')
  const fileRef = useRef(null)

  async function refresh() {
    try {
      const data = await listKbs()
      setItems(data)
      const indexing = data.some((k) => k.status === 'indexing')
      onChanged?.(data)
      return indexing
    } catch {
      return false
    }
  }

  useEffect(() => {
    let alive = true
    let timer = null
    const tick = async () => {
      const indexing = await refresh()
      if (alive && indexing) timer = setTimeout(tick, 2000)
    }
    tick()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [])

  async function create() {
    const value = name.trim()
    if (!value) return
    setBusy('创建中……')
    try {
      const created = await createKb(value)
      setName('')
      onSelect?.(created.id)
      await refresh()
    } finally {
      setBusy('')
    }
  }

  async function upload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(`上传 ${file.name}……`)
    try {
      await uploadDocument(kb, file)
      const indexing = await refresh()
      if (indexing) setTimeout(refresh, 2000)
    } catch (err) {
      setBusy('上传失败：' + err.message)
    } finally {
      e.target.value = ''
      setBusy('')
    }
  }

  async function rename(id, current) {
    const name = window.prompt('新的知识库名称', current)
    if (!name || !name.trim()) return
    await renameKb(id, name.trim())
    await refresh()
  }

  async function remove(id) {
    if (!window.confirm('删除这个知识库？')) return
    await deleteKb(id)
    if (id === kb) onSelect?.('fastapi')
    await refresh()
  }

  return (
    <div className="page">
      <div className="card chart-card">
        <div className="chart-title">知识库</div>
        <div className="kb-list">
          {items.map((k) => (
            <div key={k.id} className={`kb-item ${k.id === kb ? 'active' : ''}`} onClick={() => onSelect?.(k.id)}>
              <div>
                <div className="kb-name">{k.name}</div>
                <div className="kb-meta">
                  {k.chunk_count} 块 · {k.doc_count} 篇
                  {k.status === 'indexing' && ' · 索引中……'}
                  {k.status === 'error' && ' · 失败'}
                </div>
                {k.message && <div className="kb-msg">{k.message}</div>}
              </div>
              {k.id !== 'fastapi' && (
                <div className="kb-actions">
                  <button
                    className="del"
                    title="重命名"
                    onClick={(e) => {
                      e.stopPropagation()
                      rename(k.id, k.name)
                    }}
                  >
                    ✎
                  </button>
                  <button
                    className="del"
                    title="删除"
                    onClick={(e) => {
                      e.stopPropagation()
                      remove(k.id)
                    }}
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="kb-create">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="新知识库名称"
            onKeyDown={(e) => e.key === 'Enter' && create()}
          />
          <button onClick={create}>新建</button>
        </div>

        <div className="kb-upload">
          <input ref={fileRef} type="file" accept=".md,.txt,.pdf" onChange={upload} hidden />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={kb === 'fastapi' || kb === 'all'}
            title={kb === 'fastapi' || kb === 'all' ? '请先在列表里选中一个具体知识库' : ''}
          >
            {kb === 'all' ? '先选择一个知识库' : kb === 'fastapi' ? '内置库只读' : `上传文档到「${kb}」`}
          </button>
          <span className="meta">{busy}</span>
        </div>
        <div className="hint-card">
          支持 .md / .txt / .pdf。上传后后台切块并向量化，几秒后自动刷新；同一文件名会覆盖旧内容。
          内置的 FastAPI 库是只读的，练习上传请先新建知识库。
        </div>
      </div>
    </div>
  )
}
