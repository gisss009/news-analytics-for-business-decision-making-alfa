import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useInsightStream } from "../api/useInsightStream";
import { ClaimList, LabelChip, REF_KIND_TITLES, RefChip, refKind } from "../components/Claims";
import { useRole } from "../components/RolePicker";
import { SourcePanel } from "../components/SourcePanel";
import { ErrorBox, Loading } from "../components/Status";
import { date, pct } from "../format";

const ALL_STEPS = ["planner", "retriever", "ranker", "bank_view", "interpreter", "verifier"];
const STEP_TITLES: Record<string, string> = {
  planner: "Планирую, какие данные нужны",
  retriever: "Собираю новости, аналитику и данные компании",
  ranker: "Оцениваю значимость для компании",
  bank_view: "Ищу позицию аналитиков банка",
  interpreter: "Формирую интерпретацию",
  verifier: "Проверяю источники и числа",
};

/** Страница события: шесть блоков интерпретации, метки происхождения, переход к первоисточнику. */
export function InsightPage() {
  const { clientId = "", eventId = "" } = useParams();
  const [role] = useRole();
  const { steps, result, error } = useInsightStream(eventId, clientId, role);
  const [activeRef, setActiveRef] = useState<string | null>(null);
  const ins = result?.insight;
  const b = ins?.blocks;
  const done = new Set(steps.map((s) => s.step));
  const basisGroups = (b?.basis.refs ?? []).reduce<Record<string, string[]>>((acc, r) => {
    const k = refKind(r) === "news_fact" ? "news" : refKind(r);
    (acc[k] ??= []).push(r);
    return acc;
  }, {});

  return (
    <section>
      <p className="crumb">
        <Link to="/">Главная</Link> / <Link to={`/clients?role=${role}`}>Сводка</Link> /{" "}
        <Link to={`/clients/${clientId}?role=${role}`}>Лента компании</Link> / Событие
      </p>
      <h1>{ins?.event.title ?? "Разбор события"}</h1>
      {ins && (
        <p className="lead">
          {date(ins.event.published_at)} · источники: {ins.event.sources.map((s) => s.name).join(", ")} · значимость для
          компании {pct(ins.relevance.score)} из 100
        </p>
      )}

      <div className="insight-layout">
        <div className="blocks">
          {error && <ErrorBox error={error} />}
          {!ins && !error && (
            <div className="card">
              <h2>Агент разбирает событие</h2>
              <ol className="steps">
                {ALL_STEPS.map((s) => {
                  const st = steps.find((x) => x.step === s);
                  return (
                    <li key={s} className={st ? (st.status === "ok" ? "done" : st.status) : ""}>
                      <span className="dot" aria-hidden="true" />
                      {STEP_TITLES[s]}
                      {st && <span className="muted small">· {st.duration_ms} мс</span>}
                    </li>
                  );
                })}
              </ol>
            </div>
          )}

          {ins && b && (
            <>
              <div className="card legend" aria-label="Обозначения">
                <span>Метки утверждений:</span>
                <LabelChip label="fact" /> <span className="muted small">подтверждено источником</span>
                <LabelChip label="bank_analytics" /> <span className="muted small">позиция банка из его материалов</span>
                <LabelChip label="model_inference" /> <span className="muted small">вывод ИИ по данным компании</span>
              </div>

              {ins.warnings.length > 0 && (
                <div className="warnings" role="note">
                  <strong>Обратите внимание</strong>
                  <ul>
                    {ins.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              <article className="card block">
                <h2><span className="num">1</span>Что произошло</h2>
                <ClaimList claims={b.what_happened.claims} activeRef={activeRef} onOpen={setActiveRef} />
              </article>

              <article className="card block">
                <h2><span className="num">2</span>Почему это важно вашей компании</h2>
                <ClaimList claims={b.why_it_matters.claims} activeRef={activeRef} onOpen={setActiveRef} />
              </article>

              <article className="card block">
                <h2><span className="num">3</span>Возможные последствия</h2>
                <div className="two-col">
                  <div>
                    <p className="sub-title">Риски</p>
                    {b.consequences.risks.length ? (
                      <ClaimList claims={b.consequences.risks} activeRef={activeRef} onOpen={setActiveRef} />
                    ) : (
                      <p className="muted">Существенных рисков не выявлено.</p>
                    )}
                  </div>
                  <div>
                    <p className="sub-title">Возможности</p>
                    {b.consequences.opportunities.length ? (
                      <ClaimList claims={b.consequences.opportunities} activeRef={activeRef} onOpen={setActiveRef} />
                    ) : (
                      <p className="muted">Явных возможностей не выявлено.</p>
                    )}
                  </div>
                </div>
              </article>

              <article className="card block">
                <h2><span className="num">4</span>Что можно сделать</h2>
                <ClaimList claims={b.actions.claims} activeRef={activeRef} onOpen={setActiveRef} />
              </article>

              <article className="card block">
                <h2><span className="num">5</span>Как это оценивает Альфа-Банк</h2>
                {b.bank_view.absent ? (
                  <p className="bank-absent">{b.bank_view.note}</p>
                ) : (
                  <>
                    <ClaimList claims={b.bank_view.claims} activeRef={activeRef} onOpen={setActiveRef} />
                    {b.bank_view.note && <p className="muted small">{b.bank_view.note}</p>}
                  </>
                )}
              </article>

              <article className="card block">
                <h2><span className="num">6</span>На чём основан вывод</h2>
                {Object.entries(basisGroups).map(([kind, refs]) => (
                  <div key={kind}>
                    <p className="sub-title">{kind === "news" ? "Новости" : REF_KIND_TITLES[kind] ?? kind}</p>
                    <div className="chips">
                      {refs.map((r) => (
                        <RefChip key={r} refId={r} active={activeRef === r} onOpen={setActiveRef} />
                      ))}
                    </div>
                  </div>
                ))}
                <p className="sub-title">Почему событие в вашей ленте</p>
                <ul className="why">
                  {ins.relevance.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </article>
            </>
          )}
        </div>

        <aside className="panel">
          {activeRef && <SourcePanel refId={activeRef} client={clientId} onClose={() => setActiveRef(null)} />}
          {ins && (
            <div className="card">
              <h3>Самопроверка</h3>
              <p className={ins.verification.passed ? "verified" : "muted"} style={{ margin: "6px 0 0" }}>
                {ins.verification.passed
                  ? "Все ссылки открываются, числа совпадают с источниками"
                  : "Часть утверждений не прошла проверку и скрыта"}
              </p>
              <p className="muted small">
                Итераций проверки: {ins.verification.iterations} · статус: {ins.status}
                {result?.cached ? " · из кэша" : ""}
              </p>
              {steps.length > 0 && (
                <ol className="steps">
                  {steps.map((s, i) => (
                    <li key={`${s.step}-${i}`} className={s.status === "ok" ? "done" : s.status}>
                      <span className="dot" aria-hidden="true" />
                      {s.title} <span className="muted small">· {s.duration_ms} мс</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
          {!activeRef && ins && <p className="top-note">Нажмите на ссылку у утверждения, чтобы открыть первоисточник.</p>}
          {!ins && !error && done.size === 0 && <Loading text="Подключаемся к агенту" />}
        </aside>
      </div>
    </section>
  );
}
