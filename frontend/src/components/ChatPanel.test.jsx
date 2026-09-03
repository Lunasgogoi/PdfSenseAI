import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { askDocument, clearChatHistory, getChatHistory } from '../api'
import ChatPanel from './ChatPanel'


vi.mock('../api', () => ({
  askDocument: vi.fn(),
  clearChatHistory: vi.fn(),
  getChatHistory: vi.fn(),
}))

const document = {
  document_id: 'document-123',
  filename: 'research.pdf',
  page_count: 8,
  number_of_chunks: 19,
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getChatHistory.mockResolvedValue({ turns: [] })
    clearChatHistory.mockResolvedValue(undefined)
  })

  it('submits a question and renders server-owned page citations', async () => {
    askDocument.mockResolvedValue({
      answer: 'The launch is planned for October.',
      citations: [
        {
          chunk_id: 'chunk-1',
          page_number: 4,
          excerpt: 'The launch is planned for October.',
          similarity_score: 0.91,
        },
      ],
    })
    render(<ChatPanel document={document} />)

    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: 'When is the launch?' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send question/i }))

    await waitFor(() => {
      expect(askDocument).toHaveBeenCalledWith('document-123', 'When is the launch?')
    })
    expect(
      await screen.findAllByText('The launch is planned for October.'),
    ).toHaveLength(2)
    expect(screen.getByText(/source 1 .* page 4/i)).toBeInTheDocument()
  })
})
