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
  UserRound,
} from 'lucide-react'
import { askDocument } from '../api'

const suggestions = [
  'What is the main idea of this document?',
  'What are the most important findings?',
  'Explain the key concepts in simple terms.',
]

function CitationCard({ citation, index }) {
  return (
    <details className="group rounded-xl border border-violet-100 bg-violet-50/70">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-xs font-bold text-violet-800">
        <Quote size={13} />
        Source {index + 1} · Page {citation.page_number}
        <span className="ml-auto text-[10px] font-semibold text-violet-500">
          {(citation.similarity_score * 100).toFixed(0)}% match
        </span>
        <ChevronDown className="transition group-open:rotate-180" size={14} />
      </summary>
      <div className="border-t border-violet-100 px-3 py-3 text-xs leading-5 text-slate-600">
        {citation.excerpt}
      </div>
    </details>
  )
}

function ChatPanel({ document }) {
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

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
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-141px)] w-full max-w-5xl flex-col px-4 sm:px-7 lg:px-10">
      <div className="scrollbar-light min-h-0 flex-1 overflow-y-auto py-6 sm:py-8">
        {messages.length === 0 ? (
          <div className="mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center pb-8 text-center">
            <div className="grid size-14 place-items-center rounded-2xl bg-violet-100 text-violet-700">
              <MessageSquareText size={25} />
            </div>
            <h2 className="mt-5 text-2xl font-black tracking-tight text-slate-950 sm:text-3xl">
              Ask your document anything
            </h2>
            <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">
              Answers are grounded in {document.filename} and include the exact page excerpts used as evidence.
            </p>
            <div className="mt-7 grid w-full gap-2 sm:grid-cols-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-2xl border border-slate-200 bg-white p-4 text-left text-xs font-semibold leading-5 text-slate-600 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-300 hover:text-violet-700 hover:shadow-md"
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
                        ? 'rounded-br-md bg-violet-600 text-white'
                        : 'rounded-bl-md border border-slate-200 bg-white text-slate-700'
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
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-violet-100 text-violet-700">
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
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-500 shadow-sm">
                  <LoaderCircle className="animate-spin text-violet-600" size={16} />
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
          <div className="mb-3 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs font-semibold text-rose-700">
            <CircleAlert className="mt-0.5 shrink-0" size={15} />
            <span>{error}</span>
          </div>
        )}
        <form
          className="rounded-2xl border border-slate-200 bg-white p-2 shadow-[0_12px_35px_rgba(15,23,42,0.1)] focus-within:border-violet-300 focus-within:ring-4 focus-within:ring-violet-100"
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
            className="max-h-36 min-h-12 w-full resize-none bg-transparent px-3 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void submitQuestion()
              }
            }}
          />
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-2 pt-2">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-400">
              <FileText size={13} />
              {document.page_count} pages · {document.number_of_chunks} indexed chunks
            </div>
            <button
              type="submit"
              disabled={!query.trim() || loading}
              aria-label="Send question"
              className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-white shadow-md transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
            >
              {loading ? <LoaderCircle className="animate-spin" size={16} /> : <ArrowUp size={17} />}
            </button>
          </div>
        </form>
        <p className="mt-2 text-center text-[10px] font-medium text-slate-400">
          PdfSense answers only from retrieved document evidence.
        </p>
      </div>
    </div>
  )
}

export default ChatPanel
