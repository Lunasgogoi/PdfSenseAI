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
          <LoaderCircle className="mx-auto animate-spin text-indigo-500" size={28} />
          <p className="mt-3 text-sm font-medium">Opening your workspace…</p>
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
          <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl bg-[#26344d] text-white shadow-lg shadow-slate-400/25">
            <BrainCircuit size={30} />
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-indigo-500">
            Read less. Understand more.
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl text-3xl font-semibold tracking-[-0.025em] text-slate-700 sm:text-4xl">
            Turn any PDF into a conversation.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-slate-500">
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
            <div key={label} className="flex items-center justify-center gap-2 rounded-xl border border-slate-200/70 bg-white/70 px-3 py-3 text-sm font-medium text-slate-600 shadow-sm shadow-slate-200/30 backdrop-blur">
              <Icon size={15} className="text-indigo-500" />
              {label}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default EmptyWorkspace
