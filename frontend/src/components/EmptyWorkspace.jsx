import { BrainCircuit, FileSearch, GraduationCap, LoaderCircle, Sparkles } from 'lucide-react'
import UploadDropzone from './UploadDropzone'

const features = [
  { icon: FileSearch, label: 'Ask with page citations' },
  { icon: Sparkles, label: 'Create grounded summaries' },
  { icon: GraduationCap, label: 'Generate study material' },
]

function EmptyWorkspace({ loading, uploading, progress, onUpload }) {
  if (loading) {
    return (
      <div className="grid flex-1 place-items-center p-8 text-slate-500">
        <div className="text-center">
          <LoaderCircle className="mx-auto animate-spin text-violet-600" size={28} />
          <p className="mt-3 text-sm font-semibold">Opening your workspace…</p>
        </div>
      </div>
    )
  }

  return (
    <section className="relative flex flex-1 items-center justify-center overflow-hidden px-5 py-12 sm:px-8">
      <div className="workspace-orb workspace-orb-one" />
      <div className="workspace-orb workspace-orb-two" />
      <div className="relative z-10 w-full max-w-3xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl bg-slate-900 text-white shadow-2xl shadow-violet-300">
            <BrainCircuit size={30} />
          </div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-violet-600">
            Read less. Understand more.
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl text-3xl font-black tracking-[-0.04em] text-slate-950 sm:text-5xl">
            Turn any PDF into a conversation.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-slate-500 sm:text-base">
            Upload a text-based PDF and PdfSense will build a private, page-aware workspace for questions, summaries, and revision.
          </p>
        </div>

        <UploadDropzone
          onUpload={onUpload}
          uploading={uploading}
          progress={progress}
        />

        <div className="mt-7 grid gap-3 sm:grid-cols-3">
          {features.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center justify-center gap-2 rounded-xl border border-slate-200/80 bg-white/60 px-3 py-3 text-xs font-bold text-slate-600 backdrop-blur">
              <Icon size={15} className="text-violet-600" />
              {label}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default EmptyWorkspace
