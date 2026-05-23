import { useEffect, useRef, useState } from 'react'
import api from '../api/client'

interface Message {
  role: 'user' | 'agent'
  text: string
  sources?: string[]
  hasContext?: boolean
}

interface HistoryItem {
  id: number
  question: string
  answer: string
  sources: string[]
  created_at: string
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'agent',
      text: 'Hello! Ask me anything about Formula 1. You can also upload documents to expand my knowledge base.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(true)
  const [hasDocuments, setHasDocuments] = useState<boolean | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [clearingAll, setClearingAll] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadHistory = async () => {
    try {
      const res = await api.get('/agent/history')
      setHistory(res.data)
    } catch {
      // silently fail
    }
  }

  const checkDocuments = async () => {
    try {
      const res = await api.get('/documents/')
      setHasDocuments(res.data.length > 0)
    } catch {
      setHasDocuments(null)
    }
  }

  useEffect(() => {
    loadHistory()
    checkDocuments()
  }, [])

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return

    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setInput('')
    setLoading(true)

    try {
      const res = await api.post('/agent/ask', { question })
      const { answer, sources, has_context } = res.data
      setMessages((prev) => [
        ...prev,
        { role: 'agent', text: answer, sources, hasContext: has_context },
      ])
      loadHistory()
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'An error occurred. Please try again.'
      setMessages((prev) => [
        ...prev,
        { role: 'agent', text: detail, hasContext: false },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const loadHistoryMessage = (item: HistoryItem) => {
    setMessages([
      { role: 'user', text: item.question },
      { role: 'agent', text: item.answer, sources: item.sources },
    ])
    setShowHistory(false)
  }

  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeletingId(id)
    try {
      await api.delete(`/agent/history/${id}`)
      setHistory((prev) => prev.filter((item) => item.id !== id))
    } catch {
      // silently fail
    } finally {
      setDeletingId(null)
    }
  }

  const clearAllHistory = async () => {
    if (!window.confirm('Delete all conversation history?')) return
    setClearingAll(true)
    try {
      await Promise.all(history.map((item) => api.delete(`/agent/history/${item.id}`)))
      setHistory([])
    } catch {
      // silently fail
    } finally {
      setClearingAll(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-64px)] bg-gray-950">
      {/* History sidebar */}
      {showHistory && (
        <aside className="w-72 bg-gray-900 border-r border-gray-700 flex flex-col">
          <div className="p-4 border-b border-gray-700 flex items-center justify-between">
            <h2 className="text-white font-semibold">History</h2>
            <div className="flex items-center gap-2">
              {history.length > 0 && (
                <button
                  onClick={clearAllHistory}
                  disabled={clearingAll}
                  title="Clear all history"
                  className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50 px-2 py-0.5 rounded hover:bg-gray-700 transition-colors"
                >
                  {clearingAll ? 'Clearing…' : 'Clear all'}
                </button>
              )}
              <button
                onClick={() => setShowHistory(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="overflow-y-auto flex-1">
            {history.length === 0 ? (
              <p className="text-gray-500 text-sm p-4">No conversations yet.</p>
            ) : (
              history.map((item) => (
                <div
                  key={item.id}
                  className="group relative border-b border-gray-700/50 hover:bg-gray-800 transition-colors"
                >
                  <button
                    onClick={() => loadHistoryMessage(item)}
                    className="w-full text-left p-3 pr-10"
                  >
                    <p className="text-gray-200 text-sm truncate">{item.question}</p>
                    <p className="text-gray-500 text-xs mt-1">
                      {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </button>

                  {/* Delete button — visible on hover */}
                  <button
                    onClick={(e) => deleteConversation(item.id, e)}
                    disabled={deletingId === item.id}
                    title="Delete conversation"
                    className="
                      absolute right-2 top-1/2 -translate-y-1/2
                      opacity-0 group-hover:opacity-100
                      text-gray-500 hover:text-red-400
                      disabled:opacity-30
                      p-1 rounded transition-all
                    "
                  >
                    {deletingId === item.id ? (
                      <span className="text-xs">…</span>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    )}
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>
      )}

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-900 border-b border-gray-700">
          <button
            onClick={() => {
              setShowHistory((v) => !v)
              if (!showHistory) loadHistory()
            }}
            className="text-sm text-gray-400 hover:text-white px-3 py-1 rounded-md hover:bg-gray-700 transition-colors"
          >
            {showHistory ? 'Hide History' : 'Show History'}
          </button>
          <button
            onClick={() =>
              setMessages([
                {
                  role: 'agent',
                  text: 'Hello! Ask me anything about Formula 1.',
                },
              ])
            }
            className="text-sm text-gray-400 hover:text-white px-3 py-1 rounded-md hover:bg-gray-700 transition-colors"
          >
            New Chat
          </button>
        </div>

        {/* No documents banner */}
        {hasDocuments === false && (
          <div className="mx-4 mt-3 bg-yellow-900/30 border border-yellow-700 rounded-lg px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <p className="text-yellow-300 text-sm">
                No documents in the knowledge base. The agent won't be able to answer questions.
              </p>
            </div>
            <a
              href="/documents"
              className="text-yellow-400 hover:text-yellow-200 text-sm font-medium underline ml-4 shrink-0"
            >
              Upload docs →
            </a>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-2xl rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-red-600 text-white'
                    : msg.hasContext === false
                    ? 'bg-yellow-900/40 border border-yellow-700 text-yellow-200'
                    : 'bg-gray-800 text-gray-100'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-600">
                    <p className="text-xs text-gray-400">Sources:</p>
                    <ul className="mt-1 space-y-0.5">
                      {msg.sources.map((s, j) => (
                        <li key={j} className="text-xs text-gray-400 truncate">
                          📄 {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl px-4 py-3">
                <div className="flex gap-1 items-center h-5">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 py-4 bg-gray-900 border-t border-gray-700">
          <div className="flex gap-3 max-w-4xl mx-auto">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              rows={1}
              disabled={hasDocuments === false}
              placeholder={
                hasDocuments === false
                  ? 'Upload documents first to enable the chat...'
                  : 'Ask about Formula 1... (Enter to send)'
              }
              className="flex-1 resize-none bg-gray-800 text-gray-100 placeholder-gray-500 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}