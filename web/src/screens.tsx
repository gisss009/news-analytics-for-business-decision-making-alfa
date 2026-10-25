import { useState, type FormEvent, type ReactNode } from "react"
import { Scenario, type Card, type Client, type Story } from "../../maket/scenario.js"
import { ago, cleanTitle, ru, sourceLabel } from "./format"

const QUESTIONS = [
  "Что произошло и откуда это известно",
  "Почему это касается кредитов, выручки или поставок этой компании",
  "Какие риски и возможности из этого следуют",
  "Какой шаг уместен, если он следует из материалов",
  "Как событие оценивает банк",
  "На каких источниках держится вывод",
]

export function Home({
  onEnter,
  onNews,
  onPick,
}: {
  onEnter: () => void
  onNews: () => void
  onPick: (id: string) => void
}) {
  return (
    <>
      <section className="land-hero">
        <div className="land-wrap land-hero-top">
          <div>
            <h1>Сводка для решений</h1>
            <p className="ab-lead">
              Сводка показывает, как ставка, курс, спрос и цены поставщиков сказываются
              на кредитах, выручке и поставках выбранной компании.
            </p>
            <div className="ab-actions">
              <button className="ab-primary" type="button" onClick={onEnter}>Разобрать событие</button>
              <button className="ab-secondary" type="button" onClick={onNews}>Новости</button>
            </div>
          </div>
          <aside className="ab-hero-card">
            <p className="ab-kicker">Пример</p>
            <strong>Дом торговли</strong>
            <p>Сеть финансирует товарные запасы за счёт кредитных средств. При текущей ставке ЦБ около 14% следующая партия обойдётся примерно в ту же сумму, что и сейчас.</p>
          </aside>
        </div>
      </section>
      <section className="ab-home-more">
        <div className="land-wrap">
          <h2>Компании</h2>
          <p className="ab-lead">У каждой компании свой список: он зависит от долга, выручки и поставок. Компании вымышленные, это не клиенты банка.</p>
          <div className="ab-home-companies">
            {Scenario.clients.map((client) => (
              <button key={client.id} className="ab-home-company" type="button" onClick={() => onPick(client.id)}>
                <p className="ab-kicker">{client.sector}</p>
                <h3>{client.name}</h3>
                <p>{client.finance}</p>
              </button>
            ))}
          </div>
          <h2>Что видно по событию</h2>
          <ol className="ab-questions">
            {QUESTIONS.map((item) => <li key={item}>{item}</li>)}
          </ol>
        </div>
      </section>
    </>
  )
}

export function Companies({ onPick }: { onPick: (id: string) => void }) {
  return (
    <section>
      <h1>Для кого сводка</h1>
      <p className="ab-lead">Выберите компанию. У другой компании список событий будет другой.</p>
      <p className="ab-note">Компании синтетические: в этой сборке нет карточек реальных клиентов.</p>
      <div className="ab-grid">
        {Scenario.clients.map((client) => (
          <button key={client.id} className="ab-card" type="button" onClick={() => onPick(client.id)}>
            <p className="ab-kicker">{client.sector} · {client.region}</p>
            <h2>{client.name}</h2>
            <p>{client.finance}</p>
            <ul className="ab-tags">
              {client.features.map((feature) => <li key={feature.id}>{feature.text}</li>)}
            </ul>
          </button>
        ))}
      </div>
    </section>
  )
}

export function Events({
  client,
  pool,
  onOpen,
  onBack,
}: {
  client: Client
  pool: Card[]
  onOpen: (id: string) => void
  onBack: () => void
}) {
  const items = Scenario.storiesFor(client.id, pool)
  return (
    <section>
      <button className="ab-back" type="button" onClick={onBack}>К компаниям</button>
      <p className="ab-kicker">{client.name}</p>
      <h1>Что важно компании «{client.name}»</h1>
      <p className="ab-lead">
        {items.length} {ru(items.length, "событие", "события", "событий")} · {client.sector}.
        События отбираются по признакам этой компании.
      </p>
      {items.length ? (
        <div className="ab-stack">
          {items.map((item) => (
            <button key={item.id} className="ab-card ab-story" type="button" onClick={() => onOpen(item.id)}>
              <p className="ab-kicker">{item.action ? "Есть следующий шаг" : "Шаг не следует"}</p>
              <h2>{item.title}</h2>
              <p>{item.why}</p>
              <ul className="ab-tags">
                {item.factors.map((factor) => <li key={factor.label}>{factor.label}</li>)}
              </ul>
            </button>
          ))}
        </div>
      ) : (
        <p className="ab-card">Для этой компании в текущей выгрузке нет события из двух независимых материалов.</p>
      )}
    </section>
  )
}

export function Reading({
  client,
  pool,
  storyId,
  extra,
  onCut,
}: {
  client: Client
  pool: Card[]
  storyId: string
  extra: Story | null
  onCut: (story: Story) => void
}) {
  const listed = Scenario.storiesFor(client.id, pool).find((story) => story.id === storyId)
  const item = listed || (extra && extra.id === storyId ? extra : null)
  if (!item) return <p className="ab-card">Событие не найдено.</p>
  return (
    <article className="ab-reading">
      <header className="ab-block">
        <p className="ab-kicker">{client.name} · {client.sector}</p>
        <h1>{item.title}</h1>
        <p className="ab-lead">{item.why}</p>
      </header>
      <Section title="Что произошло">
        {item.happened.map((factor) => {
          const bank = /банк/i.test(`${factor.kind || ""} ${factor.label || ""}`)
          return (
            <div key={`${factor.source}-${factor.title}`} className={bank ? "ab-factor is-bank" : "ab-factor"}>
              <p className="ab-kicker">{factor.kind || factor.label}</p>
              <p>{factor.gloss}</p>
              <p className="ab-muted">{factor.source}. {factor.title}</p>
              {factor.href ? <a href={factor.href} target="_blank" rel="noreferrer">Открыть материал</a> : null}
            </div>
          )
        })}
      </Section>
      <Section title="Почему это важно для этой компании">
        {item.whyCompany.map((line) => <p key={line}>{line}</p>)}
      </Section>
      <Section title="Какие последствия возможны">
        {item.risks.length || item.opportunities.length ? (
          <div className="ab-split">
            {item.risks.length ? (
              <div className="ab-pane is-risk">
                <p className="ab-kicker">Риски</p>
                <ul>{item.risks.map((line) => <li key={line}>{line}</li>)}</ul>
              </div>
            ) : null}
            {item.opportunities.length ? (
              <div className="ab-pane is-chance">
                <p className="ab-kicker">Возможности</p>
                <ul>{item.opportunities.map((line) => <li key={line}>{line}</li>)}</ul>
              </div>
            ) : null}
          </div>
        ) : <p>По этой теме отдельных последствий для компании нет.</p>}
      </Section>
      <Section title="Какое действие уместно">
        <div className={item.action ? "ab-action" : "ab-quiet"}>
          <p>{item.action || "Отдельное действие не предлагаем."}</p>
          <p>{item.actionWhy}</p>
        </div>
      </Section>
      <Section title="Как это оценивает банк">
        {item.bank.length ? item.bank.map((line) => (
          <div key={line.text}>
            <p className="ab-bank">{line.role}. {line.text}</p>
            <p className="ab-muted">{line.source}</p>
            {line.href ? <a href={line.href} target="_blank" rel="noreferrer">Открыть обзор</a> : null}
          </div>
        )) : <p>В обзорах банка по этому сочетанию факторов прямой формулировки нет. Ниже вывод сервиса на неё не опирается.</p>}
      </Section>
      <Section title="На чём основан вывод">
        <div className="ab-service">
          <p>{item.conclusion}</p>
          <p>Собрано правилами из нескольких материалов. Это не позиция банка и не ответ модели.</p>
        </div>
        {item.featuresUsed.length ? (
          <>
            <p className="ab-kicker">Признаки компании</p>
            <ul>{item.featuresUsed.map((line) => <li key={line}>{line}</li>)}</ul>
          </>
        ) : null}
        <p className="ab-kicker">Источники</p>
        <ul>
          {item.sources.map((source) => (
            <li key={`${source.kind}-${source.title}`}>
              {source.kind}: {source.name}. {source.title}
              {source.href ? <> <a href={source.href} target="_blank" rel="noreferrer">открыть</a></> : null}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Как это собрано">
        <ol className="ab-trace">
          {item.trace.map((step) => <li key={step.name}><b>{step.name}.</b> {step.text}</li>)}
        </ol>
      </Section>
      <Section title="Уточнить или взять другой срез">
        <CutForm clientId={client.id} pool={pool} onCut={onCut} />
      </Section>
    </article>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="ab-block">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function CutForm({ clientId, pool, onCut }: { clientId: string; pool: Card[]; onCut: (story: Story) => void }) {
  const [value, setValue] = useState("")
  const [error, setError] = useState("")

  function submit(event: FormEvent) {
    event.preventDefault()
    const result = Scenario.answerQuestion(clientId, pool, value)
    if (result.error || !result.event) {
      setError(result.error || "Событие не найдено.")
      return
    }
    setError("")
    onCut(result.event)
  }

  return (
    <form className="ab-cut" onSubmit={submit}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label="Другой срез"
        placeholder="Ставка, курс, нефть, спрос, сталь, зерно"
      />
      <button className="ab-primary" type="submit">Показать срез</button>
      {error ? <p className="ab-error">{error}</p> : null}
    </form>
  )
}

export function News({ cards }: { cards: Card[] }) {
  return (
    <section>
      <h1>Новости</h1>
      <p className="ab-lead">
        {cards.length
          ? `${cards.length} ${ru(cards.length, "новость", "новости", "новостей")}. У каждой заметки сайт и сколько времени назад она вышла.`
          : "В выгрузке нет деловых новостей."}
      </p>
      <div className="ab-news">
        {cards.map((card) => (
          <a key={card.id} href={card.anchor?.url || "#"} target="_blank" rel="noreferrer">
            <p><span>{sourceLabel(card.source_name)}</span> · {ago(card.published_at)}</p>
            <h2>{cleanTitle(card.title, card.source_name)}</h2>
          </a>
        ))}
      </div>
    </section>
  )
}
