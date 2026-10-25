import { useState, type FormEvent } from "react"

export interface Session {
  name: string
  phone: string
}

const storageKey = "alfa-biz-session"

export function readSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Session
    if (!parsed.name) return null
    return parsed
  } catch {
    return null
  }
}

export function storeSession(session: Session | null) {
  if (!session) sessionStorage.removeItem(storageKey)
  else sessionStorage.setItem(storageKey, JSON.stringify(session))
}

interface AuthProps {
  view: "login" | "register"
  onClose: () => void
  onSwitch: (view: "login" | "register") => void
  onSuccess: (session: Session) => void
}

export function AuthWindow({ view, onClose, onSwitch, onSuccess }: AuthProps) {
  return (
    <div
      className="ab-shade"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="ab-window" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="ab-x" type="button" onClick={onClose} aria-label="Закрыть">
          ×
        </button>
        <h2 id="auth-title">{view === "login" ? "Вход" : "Регистрация"}</h2>
        <p className="ab-note">Макет окна. Запрос на сервер не уходит, доступ остаётся в этом браузере до закрытия вкладки.</p>
        {view === "login" ? (
          <LoginForm onSuccess={onSuccess} onSwitch={() => onSwitch("register")} />
        ) : (
          <RegisterForm onSuccess={onSuccess} onSwitch={() => onSwitch("login")} />
        )}
      </div>
    </div>
  )
}

function LoginForm({ onSuccess, onSwitch }: { onSuccess: (session: Session) => void; onSwitch: () => void }) {
  const [mode, setMode] = useState<"phone" | "login">("phone")
  const [phone, setPhone] = useState("")
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  function submit(event: FormEvent) {
    event.preventDefault()
    const identity = mode === "phone" ? phone : login
    if (mode === "phone" && digits(phone).length < 10) {
      setError("Введите номер телефона полностью.")
      return
    }
    if (mode === "login" && login.trim().length < 3) {
      setError("Введите логин.")
      return
    }
    if (password.length < 4) {
      setError("Введите пароль.")
      return
    }
    onSuccess({ name: identity.trim(), phone: mode === "phone" ? phone.trim() : "" })
  }

  return (
    <form className="ab-form" onSubmit={submit}>
      <div className="ab-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "phone"} onClick={() => setMode("phone")}>
          Телефон
        </button>
        <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => setMode("login")}>
          Логин
        </button>
      </div>
      {mode === "phone" ? (
        <label>
          Номер телефона
          <input autoFocus value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" placeholder="+7 900 000-00-00" />
        </label>
      ) : (
        <label>
          Логин
          <input autoFocus value={login} onChange={(event) => setLogin(event.target.value)} autoComplete="username" placeholder="company.login" />
        </label>
      )}
      <label>
        Пароль
        <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" />
      </label>
      {error ? <p className="ab-error">{error}</p> : null}
      <button className="ab-primary" type="submit">Войти</button>
      <button className="ab-text" type="button" onClick={onSwitch}>Нет доступа? Зарегистрироваться</button>
    </form>
  )
}

function RegisterForm({ onSuccess, onSwitch }: { onSuccess: (session: Session) => void; onSwitch: () => void }) {
  const [company, setCompany] = useState("")
  const [inn, setInn] = useState("")
  const [phone, setPhone] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  function submit(event: FormEvent) {
    event.preventDefault()
    const innDigits = digits(inn)
    if (company.trim().length < 2) {
      setError("Укажите название компании.")
      return
    }
    if (innDigits.length !== 10 && innDigits.length !== 12) {
      setError("ИНН: 10 или 12 цифр.")
      return
    }
    if (digits(phone).length < 10) {
      setError("Введите телефон полностью.")
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Проверьте адрес почты.")
      return
    }
    if (password.length < 6) {
      setError("Пароль не короче 6 символов.")
      return
    }
    onSuccess({ name: company.trim(), phone: phone.trim() })
  }

  return (
    <form className="ab-form" onSubmit={submit}>
      <label>
        Компания
        <input autoFocus value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Северная нефть" />
      </label>
      <label>
        ИНН
        <input value={inn} onChange={(event) => setInn(event.target.value)} inputMode="numeric" placeholder="10 или 12 цифр" />
      </label>
      <label>
        Телефон
        <input value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" placeholder="+7 900 000-00-00" />
      </label>
      <label>
        Эл. почта
        <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="name@company.ru" />
      </label>
      <label>
        Пароль
        <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="new-password" />
      </label>
      {error ? <p className="ab-error">{error}</p> : null}
      <button className="ab-primary" type="submit">Открыть доступ</button>
      <button className="ab-text" type="button" onClick={onSwitch}>Уже есть доступ? Войти</button>
    </form>
  )
}

function digits(value: string) {
  return value.replace(/\D/g, "")
}
