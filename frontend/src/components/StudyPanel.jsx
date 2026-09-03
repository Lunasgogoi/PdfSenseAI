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
      <span className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">{label}</span>
      <div className="mt-2 flex items-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        <button type="button" aria-label={`Decrease ${label}`} className="grid size-10 place-items-center text-lg font-semibold text-slate-500 hover:bg-white hover:text-violet-700" onClick={() => onChange(Math.max(0, value - 1))}>−</button>
        <input
          type="number"
          min="0"
          max="20"
          value={value}
          className="min-w-0 flex-1 bg-transparent text-center text-sm font-black text-slate-800 outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          onChange={(event) => onChange(Math.min(20, Math.max(0, Number(event.target.value) || 0)))}
        />
        <button type="button" aria-label={`Increase ${label}`} className="grid size-10 place-items-center text-lg font-semibold text-slate-500 hover:bg-white hover:text-violet-700" onClick={() => onChange(Math.min(20, value + 1))}>+</button>
      </div>
    </label>
  )
}

function MCQCard({ mcq, index }) {
  const [selected, setSelected] = useState('')
  const [checked, setChecked] = useState(false)
  const correct = selected === mcq.answer

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-violet-100 text-xs font-black text-violet-700">{index + 1}</span>
        <h3 className="pt-1 text-sm font-black leading-6 text-slate-900 sm:text-base">{mcq.question}</h3>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {mcq.choices.map((choice, choiceIndex) => {
          const isAnswer = choice === mcq.answer
          const isSelected = choice === selected
          let choiceStyle = 'border-slate-200 bg-slate-50 hover:border-violet-300 hover:bg-violet-50'
          if (checked && isAnswer) choiceStyle = 'border-emerald-400 bg-emerald-50 text-emerald-800'
          else if (checked && isSelected) choiceStyle = 'border-rose-400 bg-rose-50 text-rose-800'
          else if (isSelected) choiceStyle = 'border-violet-400 bg-violet-50 text-violet-800 ring-2 ring-violet-100'
          return (
            <button
              key={choice}
              type="button"
              disabled={checked}
              className={`flex min-h-12 items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-xs font-semibold leading-5 transition ${choiceStyle}`}
              onClick={() => setSelected(choice)}
            >
              <span className="grid size-6 shrink-0 place-items-center rounded-full border border-current/20 bg-white/60 text-[10px] font-black">
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
          <p className={`text-xs font-bold ${correct ? 'text-emerald-700' : 'text-rose-700'}`}>
            {correct ? 'Correct — nicely done.' : `Answer: ${mcq.answer}`}
          </p>
        ) : (
          <p className="text-xs text-slate-400">Choose one answer.</p>
        )}
        <button
          type="button"
          disabled={!selected}
          className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
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
      className="group min-h-52 rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-lg"
      onClick={() => setFlipped((current) => !current)}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-[0.18em] text-violet-600">
          {flipped ? 'Answer' : `Card ${index + 1}`}
        </span>
        <RotateCcw className="text-slate-300 transition group-hover:rotate-45 group-hover:text-violet-500" size={16} />
      </div>
      <p className={`mt-8 font-black leading-7 ${flipped ? 'text-base text-slate-700' : 'text-lg text-slate-950'}`}>
        {flipped ? card.back : card.front}
      </p>
      <p className="mt-6 text-[11px] font-semibold text-slate-400">Tap to {flipped ? 'see the prompt' : 'reveal the answer'}</p>
    </button>
  )
}

function StudyPanel({ document }) {
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
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-cyan-100 text-cyan-700">
              <GraduationCap size={22} />
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight text-slate-950">Build a study set</h2>
              <p className="mt-1 max-w-xl text-sm leading-6 text-slate-500">Generate validated questions and recall cards grounded in {document.filename}.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-[150px_150px_auto] sm:items-end">
            <NumberControl label="MCQs" value={mcqCount} onChange={setMcqCount} />
            <NumberControl label="Flashcards" value={flashcardCount} onChange={setFlashcardCount} />
            <button type="button" disabled={loading || (mcqCount === 0 && flashcardCount === 0)} className="flex h-11 items-center justify-center gap-2 rounded-xl bg-slate-900 px-5 text-sm font-bold text-white shadow-lg shadow-slate-900/15 transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-slate-300" onClick={generate}>
              {loading ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={17} />}
              {loading ? 'Generating…' : materials ? 'Regenerate' : 'Generate'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-5 flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-700">
          <CircleAlert className="mt-0.5 shrink-0" size={18} />
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-6 flex min-h-80 flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white text-center shadow-sm">
          <div className="grid size-16 place-items-center rounded-2xl bg-cyan-50 text-cyan-600">
            <LoaderCircle className="animate-spin" size={27} />
          </div>
          <p className="mt-5 text-sm font-black text-slate-800">Designing your study set</p>
          <p className="mt-1 text-xs text-slate-500">Validating every choice and answer before it appears.</p>
        </div>
      ) : materials ? (
        <div className="mt-6">
          <div className="mb-5 flex w-fit items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            {[
              ['mcqs', `MCQs (${materials.mcqs.length})`, BookOpenCheck],
              ['flashcards', `Flashcards (${materials.flashcards.length})`, Layers3],
            ].map(([id, label, Icon]) => (
              <button key={id} type="button" disabled={materials[id].length === 0} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold transition ${activeSection === id ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'} disabled:cursor-not-allowed disabled:opacity-40`} onClick={() => setActiveSection(id)}>
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
        <div className="mt-6 flex min-h-80 flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white/55 px-5 text-center">
          <div className="grid size-16 place-items-center rounded-2xl bg-white text-slate-400 shadow-sm">
            <GraduationCap size={27} />
          </div>
          <p className="mt-5 text-sm font-black text-slate-700">Practice material, made from your PDF</p>
          <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">Choose how many questions and cards you want. Every generated answer is checked against a strict response schema.</p>
        </div>
      ) : null}
    </div>
  )
}

export default StudyPanel
