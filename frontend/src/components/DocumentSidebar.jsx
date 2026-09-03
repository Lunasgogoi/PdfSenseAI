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
      className={`fixed inset-y-0 left-0 z-40 flex w-[min(88vw,340px)] shrink-0 flex-col bg-[#172033] text-slate-100 shadow-2xl transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:w-[320px] lg:translate-x-0 lg:shadow-none ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex h-20 items-center justify-between border-b border-slate-700/50 px-5">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-indigo-500 shadow-lg shadow-indigo-950/20">
            <BrainCircuit size={22} />
          </div>
          <div>
            <p className="text-lg font-semibold tracking-tight">PdfSense</p>
            <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
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

      <div className="border-b border-slate-700/50 p-4">
        <UploadDropzone
          compact
          onUpload={onUpload}
          uploading={uploadState.active}
          progress={uploadState.progress}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col px-3 pb-3 pt-4">
        <div className="mb-3 flex items-center justify-between px-2">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
            Your documents
          </p>
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
            {documents.length}
          </span>
        </div>

        <div className="scrollbar-dark min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
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
                  className={`group relative overflow-hidden rounded-xl border transition ${
                    active
                      ? 'border-white/10 bg-white/[0.075] shadow-sm shadow-black/10'
                      : 'border-transparent hover:border-white/[0.06] hover:bg-white/[0.045]'
                  }`}
                >
                  {active && <span className="absolute inset-y-3 left-0 w-0.5 rounded-r-full bg-indigo-400" />}
                  <button
                    type="button"
                    className="w-full p-3 text-left"
                    onClick={() => onSelect(document.document_id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`grid size-9 shrink-0 place-items-center rounded-lg ${active ? 'bg-indigo-500/90 text-white' : 'bg-white/[0.06] text-slate-400'}`}>
                        <FileText size={17} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p
                          title={document.filename}
                          className={`line-clamp-2 break-words pr-1 text-sm font-medium leading-5 ${active ? 'text-slate-50' : 'text-slate-200'}`}
                        >
                          {document.filename}
                        </p>
                        <div className="mt-1.5 flex items-center gap-2 pr-8 text-xs text-slate-400">
                          <span>{document.page_count} {document.page_count === 1 ? 'page' : 'pages'}</span>
                          <span aria-hidden="true" className="size-0.5 rounded-full bg-slate-600" />
                          <span>{formatDate(document.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${document.filename}`}
                    disabled={deleting}
                    className="absolute bottom-1.5 right-1.5 grid size-8 place-items-center rounded-lg text-slate-500 opacity-100 transition hover:bg-rose-500/10 hover:text-rose-300 disabled:cursor-wait sm:opacity-0 sm:focus:opacity-100 sm:group-hover:opacity-100"
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

      <div className="flex items-center gap-3 border-t border-slate-700/50 px-5 py-4 text-sm text-slate-400">
        <Layers3 size={15} />
        <span>{quota.documents_remaining} of {quota.document_limit} document slots left</span>
        <PanelLeftClose className="ml-auto hidden text-slate-700 lg:block" size={15} />
      </div>
    </aside>
  )
}

export default DocumentSidebar
