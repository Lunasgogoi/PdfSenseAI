import { useState } from 'react'
import { CircleAlert, Copy, FileText, LoaderCircle, Sparkles } from 'lucide-react'
import { summarizeDocument } from '../api'

function SummaryContent({ content }) {
  const lines = content.split('\n')
  return (
    <div className="space-y-3 text-sm leading-7 text-slate-700">
      {lines.map((line, index) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={index} className="h-1" />
        if (trimmed.startsWith('### ')) {
          return <h4 key={index} className="pt-2 text-base font-black text-slate-900">{trimmed.slice(4)}</h4>
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={index} className="pt-3 text-lg font-black text-slate-950">{trimmed.slice(3)}</h3>
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={index} className="pt-3 text-xl font-black text-slate-950">{trimmed.slice(2)}</h2>
        }
        if (/^[-*] /.test(trimmed)) {
          return <p key={index} className="flex gap-3 pl-1"><span className="mt-3 size-1.5 shrink-0 rounded-full bg-violet-500" />{trimmed.slice(2)}</p>
        }
        return <p key={index}>{line}</p>
      })}
    </div>
  )
}

function SummaryPanel({ document, onQuotaChange }) {
  const [detail, setDetail] = useState('brief')
  const [summary, setSummary] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const generate = async () => {
    setLoading(true)
    setError('')
    setCopied(false)
    try {
      const response = await summarizeDocument(document.document_id, detail)
      setSummary(response.summary)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
      onQuotaChange?.()
    }
  }

  const copySummary = async () => {
    await navigator.clipboard.writeText(summary)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="h-fit rounded-3xl border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-28">
          <div className="grid size-11 place-items-center rounded-2xl bg-amber-100 text-amber-700">
            <Sparkles size={21} />
          </div>
          <h2 className="mt-4 text-xl font-black tracking-tight text-slate-950">Create a summary</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            PdfSense reads every stored chunk and reduces long documents in safe batches.
          </p>

          <fieldset className="mt-6">
            <legend className="mb-2 text-xs font-black uppercase tracking-[0.16em] text-slate-400">Detail level</legend>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
              {[
                ['brief', 'Brief', 'A quick one-to-two paragraph overview'],
                ['detailed', 'Detailed', 'Structured findings, facts, and conclusions'],
              ].map(([value, label, description]) => (
                <label key={value} className={`cursor-pointer rounded-2xl border p-3 transition ${detail === value ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-100' : 'border-slate-200 hover:border-slate-300'}`}>
                  <input type="radio" name="detail" value={value} checked={detail === value} className="sr-only" onChange={() => setDetail(value)} />
                  <span className="block text-sm font-black text-slate-800">{label}</span>
                  <span className="mt-1 hidden text-xs leading-5 text-slate-500 lg:block">{description}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <button
            type="button"
            disabled={loading}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-slate-900/15 transition hover:bg-violet-700 disabled:cursor-wait disabled:bg-slate-300"
            onClick={generate}
          >
            {loading ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={17} />}
            {loading ? 'Summarizing…' : summary ? 'Regenerate summary' : 'Generate summary'}
          </button>
        </aside>

        <section className="min-w-0 rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex min-h-16 items-center justify-between border-b border-slate-100 px-5 sm:px-6">
            <div className="flex min-w-0 items-center gap-2.5">
              <FileText className="shrink-0 text-violet-600" size={18} />
              <p className="truncate text-sm font-bold text-slate-800">{document.filename}</p>
            </div>
            {summary && (
              <button type="button" className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-bold text-slate-500 hover:bg-slate-100 hover:text-slate-900" onClick={copySummary}>
                <Copy size={14} />
                {copied ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>

          <div className="min-h-[430px] p-5 sm:p-7">
            {error && (
              <div className="flex gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-700">
                <CircleAlert className="shrink-0" size={18} />
                {error}
              </div>
            )}
            {loading ? (
              <div className="flex min-h-[370px] flex-col items-center justify-center text-center">
                <div className="relative grid size-16 place-items-center rounded-2xl bg-violet-50 text-violet-600">
                  <LoaderCircle className="animate-spin" size={27} />
                  <span className="absolute -right-1 -top-1 size-3 animate-pulse rounded-full bg-amber-400" />
                </div>
                <p className="mt-5 text-sm font-black text-slate-800">Reading every section</p>
                <p className="mt-1 text-xs text-slate-500">Long PDFs may take a little longer.</p>
              </div>
            ) : summary ? (
              <SummaryContent content={summary} />
            ) : !error ? (
              <div className="flex min-h-[370px] flex-col items-center justify-center text-center">
                <div className="grid size-16 place-items-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 text-slate-400">
                  <Sparkles size={25} />
                </div>
                <p className="mt-5 text-sm font-black text-slate-700">Your summary will appear here</p>
                <p className="mt-1 max-w-xs text-xs leading-5 text-slate-500">Choose a detail level, then generate a grounded overview of all {document.page_count} pages.</p>
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  )
}

export default SummaryPanel
