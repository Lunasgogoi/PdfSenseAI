import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loginAccount, registerAccount } from '../api'
import AuthScreen from './AuthScreen'


vi.mock('../api', () => ({
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
}))

describe('AuthScreen', () => {
  beforeEach(() => vi.clearAllMocks())

  it('signs in and hands the authenticated user to the application', async () => {
    const user = { email: 'reader@example.com' }
    const onAuthenticated = vi.fn()
    loginAccount.mockResolvedValue(user)
    render(<AuthScreen onAuthenticated={onAuthenticated} />)

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'reader@example.com' },
    })
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'good-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

    await waitFor(() => {
      expect(loginAccount).toHaveBeenCalledWith('reader@example.com', 'good-password')
      expect(onAuthenticated).toHaveBeenCalledWith(user)
    })
  })

  it('switches to account creation', async () => {
    registerAccount.mockResolvedValue({ email: 'new@example.com' })
    render(<AuthScreen onAuthenticated={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /create an account/i }))
    expect(screen.getByRole('button', { name: /^create account$/i })).toBeInTheDocument()
  })
})
