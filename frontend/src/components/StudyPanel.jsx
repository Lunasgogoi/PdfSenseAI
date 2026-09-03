import { useState } from 'react'
import {
  BookOpenCheck,
  Check,
  CircleAlert,
  GraduationCap,
  Layers3,
  LoaderCircle,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react'
import { generateStudyMaterials } from '../api'

function NumberControl({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">{label}</span>
      <div className="mt-2 flex items-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        <button type="button" aria-label={`Decrease ${label}`} className="grid size-10 place-items-center text-lg font-medium text-slate-500 hover:bg-white hover:text-indigo-600" onClick={() => onChange(Math.max(0, value - 1))}>−</button>
        <input
          type="number"
          min="0"
          max="20"
          value={value}
          className="min-w-0 flex-1 bg-transparent text-center text-sm font-medium text-slate-700 outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          onChange={(event) => onChange(Math.min(20, Math.max(0, Number(event.target.value) || 0)))}
        />
        <button type="button" aria-label={`Increase ${label}`} className="grid size-10 place-items-center text-lg font-medium text-slate-500 hover:bg-white hover:text-indigo-600" onClick={() => onChange(Math.min(20, value + 1))}>+</button>
      </div>
    </label>
  )
}

function MCQCard({ mcq, index }) {
  const [selected, setSelected] = useState('')
  const [checked, setChecked] = useState(false)
  const correct = selected === mcq.answer

  return (
    <article className="rounded-2xl border border-slate-200/70 bg-[#f7f8fa] p-5 shadow-sm shadow-slate-300/20 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-indigo-50 text-xs font-medium text-indigo-600">{index + 1}</span>
        <h3 className="pt-1 text-sm font-medium leading-6 text-slate-800 sm:text-base">{mcq.question}</h3>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {mcq.choices.map((choice, choiceIndex) => {
          const isAnswer = choice === mcq.answer
          const isSelected = choice === selected
          let choiceStyle = 'border-slate-200 bg-slate-50/70 hover:border-indigo-300 hover:bg-indigo-50/60'
          if (checked && isAnswer) choiceStyle = 'border-emerald-400 bg-emerald-50 text-emerald-800'
          else if (checked && isSelected) choiceStyle = 'border-rose-400 bg-rose-50 text-rose-800'
          else if (isSelected) choiceStyle = 'border-indigo-400 bg-indigo-50 text-indigo-800 ring-2 ring-indigo-100'
          return (
            <button
              key={choice}
              type="button"
              disabled={checked}
              className={`flex min-h-12 items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm leading-5 transition ${choiceStyle}`}
              onClick={() => setSelected(choice)}
            >
              <span className="grid size-6 shrink-0 place-items-center rounded-full border border-current/20 bg-white/60 text-xs font-medium">
                {String.fromCharCode(65 + choiceIndex)}
              </span>
              <span className="flex-1">{choice}</span>
              {checked && isAnswer && <Check size={15} />}
              {checked && isSelected && !isAnswer && <X size={15} />}
            </button>
          )
        })}
      </div>
      <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
        {checked ? (
          <p className={`text-sm font-medium ${correct ? 'text-emerald-700' : 'text-rose-700'}`}>
            {correct ? 'Correct — nicely done.' : `Answer: ${mcq.answer}`}
          </p>
        ) : (
          <p className="text-sm text-slate-400">Choose one answer.</p>
        )}
        <button
          type="button"
          disabled={!selected}
          className="rounded-lg bg-[#26344d] px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          onClick={() => {
            if (checked) {
              setSelected('')
              setChecked(false)
            } else {
              setChecked(true)
            }
          }}
        >
          {checked ? 'Try again' : 'Check answer'}
        </button>
      </div>
    </article>
  )
}

function Flashcard({ card, index }) {
  const [flipped, setFlipped] = useState(false)
  return (
    <button
      type="button"
      className="group min-h-52 rounded-2xl border border-slate-200/70 bg-[#f7f8fa] p-6 text-left shadow-sm shadow-slate-300/20 transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
      onClick={() => setFlipped((current) => !current)}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-[0.16em] text-indigo-500">
          {flipped ? 'Answer' : `Card ${index + 1}`}
        </span>
        <RotateCcw className="text-slate-300 transition group-hover:rotate-45 group-hover:text-indigo-500" size={16} />
      </div>
      <p className={`mt-8 font-medium leading-7 ${flipped ? 'text-base text-slate-700' : 'text-lg text-slate-800'}`}>
        {flipped ? card.back : card.front}
      </p>
      <p className="mt-6 text-xs text-slate-400">Tap to {flipped ? 'see the prompt' : 'reveal the answer'}</p>
    </button>
  )
}

function StudyPanel({ document, onQuotaChange }) {
  const [mcqCount, setMcqCount] = useState(5)
  const [flashcardCount, setFlashcardCount] = useState(5)
  const [materials, setMaterials] = useState(null)
  const [activeSection, setActiveSection] = useState('mcqs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generate = async () => {
    if (mcqCount === 0 && flashcardCount === 0) {
      setError('Request at least one MCQ or flashcard.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const response = await generateStudyMaterials(
        document.document_id,
        mcqCount,
        flashcardCount,
      )
      setMaterials(response)
      setActiveSection(response.mcqs.length > 0 ? 'mcqs' : 'flashcards')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
      onQuotaChange?.()
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
      <div className="rounded-3xl border border-slate-200/70 bg-[#f7f8fa] p-5 shadow-sm shadow-slate-300/20 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-cyan-100 text-cyan-700">
              <GraduationCap size={22} />
            </div>
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-slate-800">Build a study set</h2>
              <p className="mt-1 max-w-xl text-sm leading-6 text-slate-500">Generate validated questions and recall cards grounded in {document.filename}.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-[150px_150px_auto] sm:items-end">
            <NumberControl label="MCQs" value={mcqCount} onChange={setMcqCount} />
            <NumberControl label="Flashcards" value={flashcardCount} onChange={setFlashcardCount} />
            <button type="button" disabled={loading || (mcqCount === 0 && flashcardCount === 0)} className="flex h-11 items-center justify-center gap-2 rounded-xl bg-[#26344d] px-5 text-sm font-medium text-white shadow-md shadow-slate-900/10 transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300" onClick={generate}>
              {loading ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={17} />}
              {loading ? 'Generating…' : materials ? 'Regenerate' : 'Generate'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-5 flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <CircleAlert className="mt-0.5 shrink-0" size={18} />
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-6 flex min-h-80 flex-col items-center justify-center rounded-3xl border border-slate-200/70 bg-[#f7f8fa] text-center shadow-sm">
          <div className="grid size-16 place-items-center rounded-2xl bg-cyan-50 text-cyan-600">
            <LoaderCircle className="animate-spin" size={27} />
          </div>
          <p className="mt-5 text-sm font-medium text-slate-700">Designing your study set</p>
          <p className="mt-1 text-sm text-slate-500">Validating every choice and answer before it appears.</p>
        </div>
      ) : materials ? (
        <div className="mt-6">
          <div className="mb-5 flex w-fit items-center gap-1 rounded-xl border border-slate-200/70 bg-[#f7f8fa] p-1 shadow-sm">
            {[
              ['mcqs', `MCQs (${materials.mcqs.length})`, BookOpenCheck],
              ['flashcards', `Flashcards (${materials.flashcards.length})`, Layers3],
            ].map(([id, label, Icon]) => (
              <button key={id} type="button" disabled={materials[id].length === 0} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${activeSection === id ? 'bg-[#26344d] text-white' : 'text-slate-500 hover:bg-slate-100'} disabled:cursor-not-allowed disabled:opacity-40`} onClick={() => setActiveSection(id)}>
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          {activeSection === 'mcqs' ? (
            <div className="space-y-4">
              {materials.mcqs.map((mcq, index) => (
                <MCQCard key={`${mcq.question}-${index}`} mcq={mcq} index={index} />
              ))}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {materials.flashcards.map((card, index) => (
                <Flashcard key={`${card.front}-${index}`} card={card} index={index} />
              ))}
            </div>
          )}
        </div>
      ) : !error ? (
        <div className="mt-6 flex min-h-80 flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-[#f7f8fa]/75 px-5 text-center">
          <div className="grid size-16 place-items-center rounded-2xl bg-slate-100 text-slate-400 shadow-sm">
            <GraduationCap size={27} />
          </div>
          <p className="mt-5 text-sm font-medium text-slate-700">Practice material, made from your PDF</p>
          <p className="mt-1 max-w-md text-sm leading-6 text-slate-500">Choose how many questions and cards you want. Every generated answer is checked against a strict response schema.</p>
        </div>
      ) : null}
    </div>
  )
}

export default StudyPanel
