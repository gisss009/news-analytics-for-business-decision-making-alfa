import { useEffect, useState } from "react"
import { Scenario, type Card, type Story } from "../../maket/scenario.js"
import { AuthWindow, readSession, storeSession, type Session } from "./auth"
import { isBusinessNews } from "./format"
import { Companies, Events, Home, News, Reading } from "./screens"

type Screen = "home" | "news" | "entry" | "events" | "reading"

export default function App() {
  const [screen, setScreen] = useState<Screen>("home")
  const [auth, setAuth] = useState<"login" | "register" | null>(null)
  const [session, setSession] = useState<Session | null>(() => readSession())
  const [pool, setPool] = useState<Card[]>([])
  const [news, setNews] = useState<Card[]>([])
  const [ready, setReady] = useState(false)
  const [clientId, setClientId] = useState<string | null>(null)
  const [storyId, setStoryId] = useState<string | null>(null)
  const [extra, setExtra] = useState<Story | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const [business, materials] = await Promise.all([
        fetchJson("/data/out/business_news.json"),
        fetchJson("/data/out/materials.json"),
      ])
      if (cancelled) return
      const cards = materials ?? []
      const businessNews = (business?.length ? business : cards).filter(isBusinessNews)
      businessNews.sort((left, right) => String(right.published_at || "").localeCompare(String(left.published_at || "")))
      const bank = cards.filter((card) => card.source_type === "alfa_research")
      setNews(businessNews)
      setPool([...bank, ...businessNews])
      setReady(Boolean(materials || business))
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [screen, storyId])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && auth) setAuth(null)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [auth])

  const client = Scenario.clients.find((item) => item.id === clientId) ?? null
  const summaryTab = screen === "entry" || screen === "events" || screen === "reading"

  function openSummary() {
    setScreen(clientId ? "events" : "entry")
  }

  function signIn(next: Session) {
    storeSession(next)
    setSession(next)
    setAuth(null)
  }

  function signOut() {
    storeSession(null)
    setSession(null)
  }

  return (
    <>
      <header className="ab-top">
        <button className="ab-brand" type="button" aria-label="На главную" onClick={() => setScreen("home")}>
          <Mark />
        </button>
        <nav aria-label="Разделы">
          <button type="button" aria-current={screen === "home" ? "page" : undefined} onClick={() => setScreen("home")}>Главная</button>
          <button type="button" aria-current={summaryTab ? "page" : undefined} onClick={openSummary}>Сводка</button>
          <button type="button" aria-current={screen === "news" ? "page" : undefined} onClick={() => setScreen("news")}>Новости</button>
        </nav>
        <div className="ab-user">
          {session ? (
            <>
              <span className="ab-avatar" aria-hidden="true">{session.name.slice(0, 1).toUpperCase()}</span>
              <span className="ab-user-name">{session.name}</span>
              <button className="ab-secondary" type="button" onClick={signOut}>Выйти</button>
            </>
          ) : (
            <>
              <button className="ab-secondary" type="button" onClick={() => setAuth("register")}>Регистрация</button>
              <button className="ab-primary" type="button" onClick={() => setAuth("login")}>Войти</button>
            </>
          )}
        </div>
      </header>
      <main className={screen === "home" ? "ab-home" : undefined}>
        {screen === "home" ? (
          <Home
            onEnter={() => setScreen("entry")}
            onNews={() => setScreen("news")}
            onPick={(id) => {
              if (!ready) return
              setClientId(id)
              setStoryId(null)
              setExtra(null)
              setScreen("events")
            }}
          />
        ) : null}
        {screen === "entry" ? (
          <Companies onPick={(id) => {
            if (!ready) return
            setClientId(id)
            setStoryId(null)
            setExtra(null)
            setScreen("events")
          }} />
        ) : null}
        {screen === "events" && client ? (
          <Events
            client={client}
            pool={pool}
            onBack={() => setScreen("entry")}
            onOpen={(id) => { setStoryId(id); setScreen("reading") }}
          />
        ) : null}
        {screen === "reading" && client && storyId ? (
          <>
            <div className="ab-backs">
              <button className="ab-back" type="button" onClick={() => setScreen("events")}>К событиям</button>
              <button className="ab-back" type="button" onClick={() => setScreen("entry")}>К компаниям</button>
            </div>
            <Reading
              client={client}
              pool={pool}
              storyId={storyId}
              extra={extra}
              onCut={(story) => { setExtra(story); setStoryId(story.id) }}
            />
          </>
        ) : null}
        {screen === "news" ? <News cards={news} /> : null}
        {!ready && screen !== "home" ? <p className="ab-note">Нет файла выгрузки. Запустите сервис из папки web, чтобы страница увидела data/out.</p> : null}
      </main>
      {auth ? (
        <AuthWindow
          view={auth}
          onClose={() => setAuth(null)}
          onSwitch={setAuth}
          onSuccess={signIn}
        />
      ) : null}
    </>
  )
}

function Mark() {
  return (
    <svg className="ab-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="6" fill="#ef3124" />
      <ellipse cx="16" cy="14.5" rx="7.2" ry="9" fill="#f5d90a" />
      <path d="M9.5 12.5h13" stroke="#1c1c1c" strokeWidth="1.3" />
      <circle cx="16" cy="12.6" r="3.5" fill="#f7f7f7" stroke="#1c1c1c" strokeWidth="1.1" />
      <circle cx="16.5" cy="13.1" r="1.35" fill="#5a3318" />
      <path d="M13.2 17.2q2.8 2.2 5.6 0" fill="none" stroke="#1c1c1c" strokeWidth="0.9" strokeLinecap="round" />
      <rect x="10.2" y="18.2" width="11.6" height="6.4" rx="1.6" fill="#3d5a99" />
      <rect x="10.2" y="18.2" width="11.6" height="1.7" fill="#1c1c1c" />
    </svg>
  )
}

async function fetchJson(url: string): Promise<Card[] | null> {
  try {
    const response = await fetch(url)
    if (!response.ok) return null
    return await response.json() as Card[]
  } catch {
    return null
  }
}
