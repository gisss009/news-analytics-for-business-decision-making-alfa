import { useState } from "react";
import { Link } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useApi } from "../api/useApi";
import { RolePicker, useRole } from "../components/RolePicker";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { rub } from "../format";

/** Выбор клиента и роли: в прототипе нет входа, компания выбирается явно. */
export function Clients() {
  const clients = useApi(async () => unwrap(await api.GET("/clients")), []);
  const [role] = useRole();
  const [q, setQ] = useState("");
  const list = (clients.data ?? []).filter((c) =>
    `${c.name} ${c.sector_title} ${c.region ?? ""}`.toLowerCase().includes(q.trim().toLowerCase()),
  );
  return (
    <section>
      <p className="crumb">
        <Link to="/">Главная</Link> / Сводка
      </p>
      <h1>Для кого сводка</h1>
      <p className="lead">
        Выберите компанию. Лента событий и их разбор строятся по её отрасли, продуктам банка, ВЭД, региону и платежам.
        Компании синтетические: реальных клиентов в этой сборке нет.
      </p>
      <div className="toolbar">
        <label>
          Поиск
          <input id="client-search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Название, отрасль или регион" />
        </label>
        <RolePicker />
      </div>
      {clients.loading && <Loading text="Загружаем компании" />}
      {clients.error && <ErrorBox error={clients.error} onRetry={clients.reload} />}
      {clients.data && list.length === 0 && <Empty text="Ничего не найдено. Измените запрос." />}
      <div className="companies">
        {list.map((c) => (
          <Link key={c.id} to={`/clients/${c.id}?role=${role}`} className="card company-card">
            <h2>{c.name}</h2>
            <span className="meta">
              {c.sector_title} · {c.region} · {rub(c.revenue_rub)}
            </span>
            <div className="chips">
              {c.products.slice(0, 4).map((p) => (
                <span key={p} className="chip">{p}</span>
              ))}
              {c.fts_countries.length > 0 && <span className="chip">ВЭД: {c.fts_countries.join(", ")}</span>}
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
