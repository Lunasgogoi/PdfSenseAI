import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { summarizeDocument } from '../api'
import SummaryPanel from './SummaryPanel'


vi.mock('../api', () => ({ summarizeDocument: vi.fn() }))

const document = {
  document_id: 'document-123',
  filename: 'research.pdf',
  page_count: 8,
}

describe('SummaryPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('requests the selected detail level and displays the summary', async () => {
    summarizeDocument.mockResolvedValue({ summary: 'A grounded detailed summary.' })
    render(<SummaryPanel document={document} />)

    fireEvent.click(screen.getByLabelText(/detailed/i))
    fireEvent.click(screen.getByRole('button', { name: /generate summary/i }))

    await waitFor(() => {
      expect(summarizeDocument).toHaveBeenCalledWith('document-123', 'detailed')
    })
    expect(await screen.findByText('A grounded detailed summary.')).toBeInTheDocument()
  })
})
