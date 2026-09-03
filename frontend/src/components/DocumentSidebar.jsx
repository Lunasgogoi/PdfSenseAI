import {
  BrainCircuit,
  FileText,
  Layers3,
  LoaderCircle,
  PanelLeftClose,
  Trash2,
  X,
} from 'lucide-react'
import UploadDropzone from './UploadDropzone'

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function SidebarSkeleton() {
  return Array.from({ length: 3 }, (_, index) => (
    <div key={index} className="animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50 p-3.5">
      <div className="h-3 w-3/4 rounded bg-slate-700" />
      <div className="mt-3 h-2 w-1/2 rounded bg-slate-800" />
    </div>
  ))
}

function DocumentSidebar({
  documents,
  selectedDocumentId,
  loading,
  uploadState,
  deletingId,
  open,
  onClose,
  onUpload,
  onSelect,
  onDelete,
  quota,
}) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex w-[min(88vw,340px)] shrink-0 flex-col bg-slate-950 text-white shadow-2xl transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:w-[330px] lg:translate-x-0 lg:shadow-none ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex h-20 items-center justify-between border-b border-slate-800/90 px-5">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-950/40">
            <BrainCircuit size={22} />
          </div>
          <div>
            <p className="text-lg font-black tracking-tight">PdfSense</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Document AI
            </p>
          </div>
        </div>
        <button
          type="button"
          aria-label="Close document menu"
          className="grid size-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </div>

      <div className="border-b border-slate-800/90 p-4">
        <UploadDropzone
          compact
          onUpload={onUpload}
          uploading={uploadState.active}
          progress={uploadState.progress}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col px-3 pb-3 pt-4">
        <div className="mb-3 flex items-center justify-between px-2">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Your documents
          </p>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-bold text-slate-400">
            {documents.length}
          </span>
        </div>

        <div className="scrollbar-dark min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          {loading ? (
            <SidebarSkeleton />
          ) : documents.length === 0 ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 px-4 py-8 text-center">
              <FileText className="mx-auto text-slate-600" size={25} />
              <p className="mt-3 text-sm font-semibold text-slate-400">No PDFs yet</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">Upload one to begin your workspace.</p>
            </div>
          ) : (
            documents.map((document) => {
              const active = document.document_id === selectedDocumentId
              const deleting = deletingId === document.document_id
              return (
                <div
                  key={document.document_id}
                  className={`group relative rounded-2xl border transition ${
                    active
                      ? 'border-violet-500/60 bg-violet-500/10 shadow-[inset_3px_0_0_#8b5cf6]'
                      : 'border-transparent bg-slate-900/50 hover:border-slate-700 hover:bg-slate-900'
                  }`}
                >
                  <button
                    type="button"
                    className="w-full p-3.5 pr-11 text-left"
                    onClick={() => onSelect(document.document_id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`grid size-9 shrink-0 place-items-center rounded-xl ${active ? 'bg-violet-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
                        <FileText size={17} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className={`truncate text-sm font-bold ${active ? 'text-white' : 'text-slate-300'}`}>
                          {document.filename}
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-[10px] font-semibold text-slate-500">
                          <span>{document.page_count} pages</span>
                          <span className="size-0.5 rounded-full bg-slate-600" />
                          <span>{formatDate(document.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${document.filename}`}
                    disabled={deleting}
                    className="absolute right-2.5 top-3 grid size-8 place-items-center rounded-lg text-slate-600 opacity-100 transition hover:bg-rose-500/10 hover:text-rose-400 disabled:cursor-wait sm:opacity-0 sm:group-hover:opacity-100"
                    onClick={() => onDelete(document)}
                  >
                    {deleting ? <LoaderCircle className="animate-spin" size={15} /> : <Trash2 size={15} />}
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 border-t border-slate-800/90 px-5 py-4 text-xs text-slate-500">
        <Layers3 size={15} />
        <span>{quota.documents_remaining} of {quota.document_limit} document slots left</span>
        <PanelLeftClose className="ml-auto hidden text-slate-700 lg:block" size={15} />
      </div>
    </aside>
  )
}

export default DocumentSidebar
