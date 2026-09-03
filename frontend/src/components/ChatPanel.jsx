import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp,
  Bot,
  ChevronDown,
  CircleAlert,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Quote,
  Trash2,
  UserRound,
} from 'lucide-react'
import { askDocument, clearChatHistory, getChatHistory } from '../api'

const suggestions = [
  'What is the main idea of this document?',
  'What are the most important findings?',
  'Explain the key concepts in simple terms.',
]

function CitationCard({ citation, index }) {
  return (
    <details className="group rounded-xl border border-indigo-100 bg-indigo-50/60">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-sm font-medium text-indigo-700">
        <Quote size={13} />
        Source {index + 1} · Page {citation.page_number}
        <span className="ml-auto text-xs text-indigo-400">
          {(citation.similarity_score * 100).toFixed(0)}% match
        </span>
        <ChevronDown className="transition group-open:rotate-180" size={14} />
      </summary>
      <div className="border-t border-indigo-100 px-3 py-3 text-sm leading-6 text-slate-600">
        {citation.excerpt}
      </div>
    </details>
  )
}

function ChatPanel({ document, onQuotaChange }) {
  const [messages, setMessages] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    let active = true
    getChatHistory(document.document_id)
      .then((history) => {
        if (!active) return
        setMessages(
          history.turns.flatMap((turn) => [
            { id: `${turn.turn_id}-question`, role: 'user', text: turn.query },
            {
              id: `${turn.turn_id}-answer`,
              role: 'assistant',
              text: turn.answer,
              citations: turn.citations,
            },
          ]),
        )
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [document.document_id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, loading])

  const submitQuestion = async (event) => {
    event?.preventDefault()
    const question = query.trim()
    if (!question || loading) return

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', text: question },
    ])
    setQuery('')
    setError('')
    setLoading(true)
    try {
      const response = await askDocument(document.document_id, question)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: response.answer,
          citations: response.citations,
        },
      ])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
      onQuotaChange?.()
    }
  }

  const clearConversation = async () => {
    setError('')
    try {
      await clearChatHistory(document.document_id)
      setMessages([])
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-141px)] w-full max-w-5xl flex-col px-4 sm:px-7 lg:px-10">
      <div className="flex min-h-12 shrink-0 items-center justify-between border-b border-slate-200/70">
        <p className="text-sm font-medium text-slate-500">Conversation</p>
        <button type="button" disabled={messages.length === 0 || loading} className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40" onClick={clearConversation}>
          <Trash2 size={14} /> Clear
        </button>
      </div>
      <div className="scrollbar-light min-h-0 flex-1 overflow-y-auto py-6 sm:py-8">
        {historyLoading ? (
          <div className="flex min-h-full items-center justify-center gap-2 text-sm text-slate-400">
            <LoaderCircle className="animate-spin text-indigo-500" size={17} /> Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <div className="mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center pb-8 text-center">
            <div className="grid size-14 place-items-center rounded-2xl bg-indigo-100/80 text-indigo-600">
              <MessageSquareText size={25} />
            </div>
            <h2 className="mt-5 text-2xl font-semibold tracking-tight text-slate-800 sm:text-[1.75rem]">
              Ask your document anything
            </h2>
            <p className="mt-3 max-w-xl text-base leading-7 text-slate-500">
              Answers are grounded in {document.filename} and include the exact page excerpts used as evidence.
            </p>
            <div className="mt-7 grid w-full gap-2 sm:grid-cols-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 text-left text-sm leading-6 text-slate-600 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-200 hover:bg-white hover:text-indigo-700"
                  onClick={() => setQuery(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message) => (
              <article
                key={message.id}
                className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {message.role === 'assistant' && (
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-white">
                    <Bot size={17} />
                  </div>
                )}
                <div className={`max-w-[88%] sm:max-w-[78%] ${message.role === 'user' ? 'order-first' : ''}`}>
                  <div
                    className={`rounded-2xl px-4 py-3.5 text-sm leading-6 shadow-sm ${
                      message.role === 'user'
                        ? 'rounded-br-md bg-indigo-500 text-white'
                        : 'rounded-bl-md border border-slate-200/70 bg-[#f7f8fa] text-slate-700'
                    }`}
                  >
                    {message.text}
                  </div>
                  {message.citations?.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {message.citations.map((citation, index) => (
                        <CitationCard key={citation.chunk_id} citation={citation} index={index} />
                      ))}
                    </div>
                  )}
                </div>
                {message.role === 'user' && (
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-indigo-100 text-indigo-600">
                    <UserRound size={17} />
                  </div>
                )}
              </article>
            ))}

            {loading && (
              <div className="flex items-center gap-3">
                <div className="grid size-9 place-items-center rounded-xl bg-slate-900 text-white">
                  <Bot size={17} />
                </div>
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-slate-200/70 bg-[#f7f8fa] px-4 py-3 text-sm text-slate-500 shadow-sm">
                  <LoaderCircle className="animate-spin text-indigo-500" size={16} />
                  Reading the relevant pages…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="shrink-0 pb-4 sm:pb-6">
        {error && (
          <div className="mb-3 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">
            <CircleAlert className="mt-0.5 shrink-0" size={15} />
            <span>{error}</span>
          </div>
        )}
        <form
          className="rounded-2xl border border-slate-200/70 bg-[#f7f8fa] p-2 shadow-[0_12px_32px_rgba(51,65,85,0.06)] focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-indigo-100/70"
          onSubmit={submitQuestion}
        >
          <label htmlFor="document-question" className="sr-only">
            Ask a question about this document
          </label>
          <textarea
            id="document-question"
            value={query}
            rows={1}
            maxLength={4000}
            placeholder="Ask a question about this PDF…"
            className="max-h-36 min-h-12 w-full resize-none bg-transparent px-3 py-3 text-base text-slate-700 outline-none placeholder:text-slate-400"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void submitQuestion()
              }
            }}
          />
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-2 pt-2">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <FileText size={13} />
              {document.page_count} pages · {document.number_of_chunks} indexed chunks
            </div>
            <button
              type="submit"
              disabled={!query.trim() || loading}
              aria-label="Send question"
              className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#26344d] text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
            >
              {loading ? <LoaderCircle className="animate-spin" size={16} /> : <ArrowUp size={17} />}
            </button>
          </div>
        </form>
        <p className="mt-2 text-center text-xs text-slate-400">
          PdfSense answers only from retrieved document evidence.
        </p>
      </div>
    </div>
  )
}

export default ChatPanel
