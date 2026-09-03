import { useRef, useState } from 'react'
import { FileUp, LoaderCircle, UploadCloud } from 'lucide-react'

function UploadDropzone({ onUpload, uploading, progress, compact = false }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const selectFile = (file) => {
    if (file) onUpload(file)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div
      className={`group relative overflow-hidden rounded-2xl border border-dashed transition ${
        dragging
          ? 'border-indigo-400 bg-indigo-50'
          : compact
            ? 'border-slate-600/70 bg-white/[0.045] hover:border-indigo-400/80 hover:bg-white/[0.07]'
            : 'border-slate-300/80 bg-white/75 hover:border-indigo-400 hover:bg-white'
      } ${compact ? 'p-4' : 'p-7 sm:p-9'}`}
      onDragEnter={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false)
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        selectFile(event.dataTransfer.files[0])
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        disabled={uploading}
        onChange={(event) => selectFile(event.target.files[0])}
      />

      <div className={`flex ${compact ? 'items-center gap-3' : 'flex-col items-center text-center'}`}>
        <div
          className={`grid shrink-0 place-items-center rounded-2xl ${
            compact
              ? 'size-10 bg-indigo-400/15 text-indigo-300'
              : 'mb-4 size-14 bg-indigo-50 text-indigo-500 shadow-[0_10px_30px_rgba(99,102,241,0.12)]'
          }`}
        >
          {uploading ? (
            <LoaderCircle className="animate-spin" size={compact ? 19 : 24} />
          ) : compact ? (
            <FileUp size={19} />
          ) : (
            <UploadCloud size={25} />
          )}
        </div>

        <div className={compact ? 'min-w-0 flex-1' : ''}>
          <p className={`font-medium ${compact ? 'text-sm text-slate-100' : 'text-base text-slate-800'}`}>
            {uploading ? 'Processing your PDF' : compact ? 'Add a PDF' : 'Drop a PDF here'}
          </p>
          <p className={`mt-1 text-sm ${compact ? 'text-slate-400' : 'text-slate-500'}`}>
            {uploading
              ? 'Extracting text and building the index'
              : compact
                ? 'or browse from your device'
                : 'or choose a file from your device · up to 25 MB'}
          </p>
        </div>

        {!compact && !uploading && (
          <button
            type="button"
            className="mt-5 rounded-xl bg-[#26344d] px-5 py-2.5 text-sm font-medium text-white shadow-md shadow-slate-900/10 transition hover:-translate-y-0.5 hover:bg-indigo-700"
            onClick={() => inputRef.current?.click()}
          >
            Choose PDF
          </button>
        )}

        {compact && !uploading && (
          <button
            type="button"
            aria-label="Choose PDF"
            className="absolute inset-0 cursor-pointer"
            onClick={() => inputRef.current?.click()}
          />
        )}
      </div>

      {uploading && (
        <div className={`${compact ? 'mt-3' : 'mx-auto mt-5 max-w-sm'}`}>
          <div className={`h-1.5 overflow-hidden rounded-full ${compact ? 'bg-slate-700' : 'bg-slate-200'}`}>
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-sky-400 transition-[width] duration-300"
              style={{ width: `${Math.max(progress, 6)}%` }}
            />
          </div>
          <p className={`mt-2 text-right text-xs ${compact ? 'text-slate-400' : 'text-slate-500'}`}>
            {progress < 100 ? `${progress}% uploaded` : 'Creating embeddings…'}
          </p>
        </div>
      )}
    </div>
  )
}

export default UploadDropzone
