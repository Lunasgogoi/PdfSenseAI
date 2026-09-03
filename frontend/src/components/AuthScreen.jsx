import { useState } from 'react'
import { BrainCircuit, LoaderCircle, LockKeyhole, Mail, ShieldCheck } from 'lucide-react'
import { loginAccount, registerAccount } from '../api'

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const authenticate = mode === 'login' ? loginAccount : registerAccount
      const user = await authenticate(email, password)
      await onAuthenticated(user)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[#172033] px-4 py-10 sm:place-items-center">
      <div className="absolute left-[-8rem] top-[-8rem] size-96 rounded-full bg-indigo-500/15 blur-3xl" />
      <div className="absolute bottom-[-8rem] right-[-8rem] size-96 rounded-full bg-sky-400/10 blur-3xl" />
      <section className="relative mx-auto grid w-full max-w-5xl overflow-hidden rounded-[2rem] border border-white/10 bg-[#fbfcfd] shadow-2xl shadow-slate-950/20 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="hidden bg-gradient-to-br from-indigo-600 via-indigo-700 to-[#172033] p-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-white/15 backdrop-blur">
              <BrainCircuit size={24} />
            </div>
            <span className="text-xl font-semibold">PdfSense</span>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-indigo-100/80">Private document AI</p>
            <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-[-0.025em]">Your PDFs. Your workspace. Grounded answers.</h1>
            <p className="mt-5 max-w-md text-base leading-7 text-indigo-100/80">Documents, indexes, and chat history stay isolated to your account, with page-aware evidence for every answer.</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-indigo-100/75">
            <ShieldCheck size={16} /> Secure password hashing and signed sessions
          </div>
        </div>

        <div className="p-6 sm:p-10 lg:p-12">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="grid size-10 place-items-center rounded-xl bg-indigo-500 text-white"><BrainCircuit size={21} /></div>
            <span className="text-lg font-semibold">PdfSense</span>
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-indigo-500">{mode === 'login' ? 'Welcome back' : 'Create your workspace'}</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-[-0.025em] text-slate-800">{mode === 'login' ? 'Sign in to continue' : 'Start exploring PDFs'}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">{mode === 'login' ? 'Open your private documents and saved conversations.' : 'Create an account with an email and a secure password.'}</p>

          <form className="mt-8 space-y-4" onSubmit={submit}>
            <label className="block">
              <span className="text-sm font-medium text-slate-600">Email address</span>
              <span className="mt-2 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-100/70">
                <Mail className="text-slate-400" size={17} />
                <input aria-label="Email address" required type="email" autoComplete="email" value={email} className="h-12 min-w-0 flex-1 outline-none" onChange={(event) => setEmail(event.target.value)} />
              </span>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-600">Password</span>
              <span className="mt-2 flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-100/70">
                <LockKeyhole className="text-slate-400" size={17} />
                <input aria-label="Password" required minLength={8} maxLength={128} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} className="h-12 min-w-0 flex-1 outline-none" onChange={(event) => setPassword(event.target.value)} />
              </span>
            </label>
            {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{error}</p>}
            <button type="submit" disabled={loading} className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#26344d] text-sm font-medium text-white shadow-md shadow-slate-900/10 transition hover:bg-indigo-700 disabled:cursor-wait disabled:bg-slate-300">
              {loading && <LoaderCircle className="animate-spin" size={17} />}
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {mode === 'login' ? 'New to PdfSense?' : 'Already have an account?'}{' '}
            <button type="button" className="font-medium text-indigo-600 hover:text-indigo-800" onClick={() => { setMode((current) => current === 'login' ? 'register' : 'login'); setError('') }}>
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </div>
      </section>
    </main>
  )
}

export default AuthScreen
