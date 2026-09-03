import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { generateStudyMaterials } from '../api'
import StudyPanel from './StudyPanel'


vi.mock('../api', () => ({ generateStudyMaterials: vi.fn() }))

const document = {
  document_id: 'document-123',
  filename: 'research.pdf',
}

describe('StudyPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders validated MCQs and interactive flashcards', async () => {
    generateStudyMaterials.mockResolvedValue({
      mcqs: [
        {
          question: 'What is the launch month?',
          choices: ['August', 'September', 'October', 'November'],
          answer: 'October',
        },
      ],
      flashcards: [{ front: 'Launch month', back: 'October' }],
    })
    render(<StudyPanel document={document} />)

    fireEvent.click(screen.getByRole('button', { name: /^generate$/i }))

    await waitFor(() => {
      expect(generateStudyMaterials).toHaveBeenCalledWith('document-123', 5, 5)
    })
    expect(await screen.findByText('What is the launch month?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /flashcards \(1\)/i }))
    fireEvent.click(screen.getByRole('button', { name: /launch month/i }))
    expect(screen.getByText('October')).toBeInTheDocument()
  })
})
