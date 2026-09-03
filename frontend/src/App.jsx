import { useCallback, useEffect, useMemo, useState } from 'react'
import { GraduationCap, Menu, MessageSquareText, Sparkles } from 'lucide-react'
import { deleteDocument, listDocuments, uploadPdf } from './api'
import ChatPanel from './components/ChatPanel'
import DocumentSidebar from './components/DocumentSidebar'
import EmptyWorkspace from './components/EmptyWorkspace'
import StudyPanel from './components/StudyPanel'
import SummaryPanel from './components/SummaryPanel'
import Toast from './components/Toast'

const tabs = [
  { id: 'chat', label: 'Ask', icon: MessageSquareText },
  { id: 'summary', label: 'Summarize', icon: Sparkles },
  { id: 'study', label: 'Study', icon: GraduationCap },
]

function App() {
  const [documents, setDocuments] = useState([])
  const [selectedDocumentId, setSelectedDocumentId] = useState(null)
  const [activeTab, setActiveTab] = useState('chat')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [loadingDocuments, setLoadingDocuments] = useState(true)
  const [uploadState, setUploadState] = useState({ active: false, progress: 0 })
  const [deletingId, setDeletingId] = useState(null)
  const [toast, setToast] = useState(null)

  const selectedDocument = useMemo(
    () => documents.find((document) => document.document_id === selectedDocumentId),
    [documents, selectedDocumentId],
  )

  const refreshDocuments = useCallback(async (preferredDocumentId = null) => {
    try {
      const nextDocuments = await listDocuments()
      setDocuments(nextDocuments)
      setSelectedDocumentId((currentId) => {
        if (
          preferredDocumentId &&
          nextDocuments.some((document) => document.document_id === preferredDocumentId)
        ) {
          return preferredDocumentId
        }
        return nextDocuments.some((document) => document.document_id === currentId)
          ? currentId
          : (nextDocuments[0]?.document_id ?? null)
      })
    } catch (error) {
      setToast({ type: 'error', message: error.message })
    } finally {
      setLoadingDocuments(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    listDocuments()
      .then((nextDocuments) => {
        if (!active) return
        setDocuments(nextDocuments)
        setSelectedDocumentId(nextDocuments[0]?.document_id ?? null)
      })
      .catch((error) => {
        if (active) setToast({ type: 'error', message: error.message })
      })
      .finally(() => {
        if (active) setLoadingDocuments(false)
      })
    return () => {
      active = false
    }
  }, [])

  const handleUpload = async (file) => {
    if (!file) return
    const looksLikePdf =
      file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!looksLikePdf) {
      setToast({ type: 'error', message: 'Choose a PDF file to continue.' })
      return
    }

    setUploadState({ active: true, progress: 0 })
    try {
      const uploaded = await uploadPdf(file, (progress) => {
        setUploadState({ active: true, progress })
      })
      await refreshDocuments(uploaded.document_id)
      setSelectedDocumentId(uploaded.document_id)
      setActiveTab('chat')
      setSidebarOpen(false)
      setToast({ type: 'success', message: `${uploaded.filename} is ready to explore.` })
    } catch (error) {
      setToast({ type: 'error', message: error.message })
    } finally {
      setUploadState({ active: false, progress: 0 })
    }
  }

  const handleDeleteDocument = async (document) => {
    const confirmed = window.confirm(
      `Delete “${document.filename}”? This removes the PDF and its local index.`,
    )
    if (!confirmed) return

    setDeletingId(document.document_id)
    try {
      await deleteDocument(document.document_id)
      await refreshDocuments()
      setToast({ type: 'success', message: `${document.filename} was deleted.` })
    } catch (error) {
      setToast({ type: 'error', message: error.message })
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f6f8] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1800px]">
        <DocumentSidebar
          documents={documents}
          selectedDocumentId={selectedDocumentId}
          loading={loadingDocuments}
          uploadState={uploadState}
          deletingId={deletingId}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onUpload={handleUpload}
          onSelect={(documentId) => {
            setSelectedDocumentId(documentId)
            setSidebarOpen(false)
          }}
          onDelete={handleDeleteDocument}
        />

        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close document menu"
            className="fixed inset-0 z-30 bg-slate-950/35 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <main className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between border-b border-slate-200/80 bg-[#f5f6f8]/90 px-4 backdrop-blur-xl sm:px-7 lg:px-10">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                aria-label="Open document menu"
                className="grid size-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm lg:hidden"
                onClick={() => setSidebarOpen(true)}
              >
                <Menu size={19} />
              </button>
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-violet-600">
                  Workspace
                </p>
                <h1 className="truncate text-base font-bold text-slate-900 sm:text-lg">
                  {selectedDocument?.filename ?? 'Document intelligence'}
                </h1>
              </div>
            </div>

            <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-sm sm:flex">
              <span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" />
              Local workspace
            </div>
          </header>

          {!selectedDocument ? (
            <EmptyWorkspace
              loading={loadingDocuments}
              uploading={uploadState.active}
              progress={uploadState.progress}
              onUpload={handleUpload}
            />
          ) : (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="border-b border-slate-200/80 px-4 sm:px-7 lg:px-10">
                <div className="flex items-center gap-1 overflow-x-auto py-3">
                  {tabs.map((tab) => {
                    const Icon = tab.icon
                    const active = activeTab === tab.id
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        className={`flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition ${
                          active
                            ? 'bg-slate-900 text-white shadow-lg shadow-slate-900/15'
                            : 'text-slate-500 hover:bg-white hover:text-slate-900'
                        }`}
                        onClick={() => setActiveTab(tab.id)}
                      >
                        <Icon size={17} />
                        {tab.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="min-h-0 flex-1">
                {activeTab === 'chat' && (
                  <ChatPanel key={`chat-${selectedDocument.document_id}`} document={selectedDocument} />
                )}
                {activeTab === 'summary' && (
                  <SummaryPanel
                    key={`summary-${selectedDocument.document_id}`}
                    document={selectedDocument}
                  />
                )}
                {activeTab === 'study' && (
                  <StudyPanel key={`study-${selectedDocument.document_id}`} document={selectedDocument} />
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}

export default App
