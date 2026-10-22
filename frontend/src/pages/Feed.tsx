import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useApi } from "../api/useApi";
import { RolePicker, useRole } from "../components/RolePicker";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { EXPOSURE_TITLES, date, pct, rub } from "../format";

/** Персонализированная лента: события по значимости для компании и «почему в вашей ленте». */
export function Feed() {
  const { clientId = "" } = useParams();
  const [role] = useRole();
  const [topic, setTopic] = useState<string | null>(null);
  const profile = useApi(
    async () => unwrap(await api.GET("/clients/{client_id}/profile", { params: { path: { client_id: clientId } } })),
    [clientId],
  );
  const feed = useApi(
    async () =>
      unwrap(
        await api.GET("/clients/{client_id}/feed", {
          params: { path: { client_id: clientId }, query: { role, topic, limit: 15 } },
        }),
      ),
    [clientId, role, topic],
  );
  const client = profile.data?.client;
  const topExposures = [...(profile.data?.exposures ?? [])].sort((a, b) => b.score - a.score).slice(0, 4);

  return (
    <section>
      <p className="crumb">
        <Link to="/">Главная</Link> / <Link to={`/clients?role=${role}`}>Сводка</Link> / {client?.name ?? clientId}
      </p>
      <div className="feed-head">
        <h1>{client?.name ?? "Компания"}</h1>
        <p className="lead">
          События отобраны и упорядочены по значимости для этой компании. У каждого указано, почему оно в ленте.
        </p>
      </div>
      <div className="toolbar">
        <RolePicker />
      </div>
      <div className="topic-filter" role="group" aria-label="Темы">
        <button type="button" aria-pressed={topic === null} onClick={() => setTopic(null)}>
          Все темы
        </button>
        {Object.entries(feed.data?.topics ?? {})
          .filter(([k]) => k !== "other")
          .map(([k, title]) => (
            <button key={k} type="button" aria-pressed={topic === k} onClick={() => setTopic(k)}>
              {title}
            </button>
          ))}
      </div>

      <div className="feed-layout">
        <div className="events">
          {feed.loading && <Loading text="Ранжируем события для компании" />}
          {feed.error && <ErrorBox error={feed.error} onRetry={feed.reload} />}
          {feed.data && feed.data.events.length === 0 && <Empty text="По этой теме событий нет." />}
          {!feed.loading &&
            feed.data?.events.map((e) => (
              <Link key={e.event_id} to={`/clients/${clientId}/events/${e.event_id}?role=${role}`}
                    className="card event-card">
                <div className="event-top">
                  <span className="chip">{e.topic_title}</span>
                  <span className="score" title="Значимость для компании, 0–100">
                    значимость {pct(e.score)}
                    <span className="score-bar" aria-hidden="true">
                      <i style={{ width: `${pct(e.score)}%` }} />
                    </span>
                  </span>
                </div>
                <h2>{e.title}</h2>
                <p className="muted" style={{ margin: 0 }}>{e.annotation}</p>
                <div>
                  <p className="sub-title" style={{ marginTop: 0 }}>Почему в вашей ленте</p>
                  <ul className="why">
                    {e.reasons.slice(0, 3).map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
                <span className="muted small">
                  {date(e.first_seen)} · источников: {e.sources.length} ({[...new Set(e.sources)].join(", ")})
                </span>
              </Link>
            ))}
        </div>

        <aside className="side">
          {profile.error && <ErrorBox error={profile.error} onRetry={profile.reload} />}
          {client && (
            <div className="card">
              <h3>Контекст компании</h3>
              <dl>
                <dt>Отрасль</dt>
                <dd>{client.sector_title}</dd>
                <dt>Регион</dt>
                <dd>{client.region ?? "нет данных"}</dd>
                <dt>Выручка</dt>
                <dd>{rub(client.revenue_rub)}</dd>
                <dt>Продукты</dt>
                <dd>{client.products.join(", ") || "нет"}</dd>
                <dt>ВЭД</dt>
                <dd>{client.fts_countries.join(", ") || "нет"}</dd>
              </dl>
              <p className="sub-title">Главные чувствительности</p>
              {topExposures.map((x) => (
                <div key={x.name} className="exp-row" title={x.explanation}>
                  <span>{EXPOSURE_TITLES[x.name] ?? x.name}</span>
                  <span className="muted">{pct(x.score)}</span>
                  <span className="score-bar" aria-hidden="true">
                    <i style={{ width: `${pct(x.score)}%` }} />
                  </span>
                </div>
              ))}
              <p className="muted small" style={{ marginBottom: 0 }}>
                Признаки рассчитаны по данным банка (синтетика) с указанием источника каждого поля.
              </p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
