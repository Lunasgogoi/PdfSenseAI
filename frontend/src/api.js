import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120_000,
})

function errorMessage(error) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
    if (error.code === 'ECONNABORTED') {
      return 'The request took too long. Please try again.'
    }
    if (!error.response) {
      return 'Cannot reach the PdfSense backend. Make sure it is running.'
    }
    return `Request failed with status ${error.response.status}.`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

async function request(operation) {
  try {
    return await operation()
  } catch (error) {
    throw new Error(errorMessage(error), { cause: error })
  }
}

export async function listDocuments() {
  const response = await request(() => api.get('/documents'))
  return response.data.documents
}

export async function uploadPdf(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const response = await request(() =>
    api.post('/upload', form, {
      onUploadProgress: (event) => {
        if (!event.total) return
        onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)))
      },
    }),
  )
  return response.data
}

export async function deleteDocument(documentId) {
  await request(() => api.delete(`/documents/${documentId}`))
}

export async function askDocument(documentId, query) {
  const response = await request(() =>
    api.post('/chat', { document_id: documentId, query }),
  )
  return response.data
}

export async function summarizeDocument(documentId, detail) {
  const response = await request(() =>
    api.post('/summary', { document_id: documentId, detail }),
  )
  return response.data
}

export async function generateStudyMaterials(
  documentId,
  mcqCount,
  flashcardCount,
) {
  const response = await request(() =>
    api.post('/study', {
      document_id: documentId,
      mcq_count: mcqCount,
      flashcard_count: flashcardCount,
    }),
  )
  return response.data
}
