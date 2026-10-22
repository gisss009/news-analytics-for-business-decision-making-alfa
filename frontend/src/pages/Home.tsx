import { Link } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useApi } from "../api/useApi";

/** Главный экран: постоянная точка входа в сервис (по макету ветки frontend). */
export function Home() {
  const health = useApi(async () => unwrap(await api.GET("/health")), []);
  return (
    <section className="home">
      <p className="crumb">Главный экран</p>
      <h1>Сводка для решений</h1>
      <p className="lead">
        Выберите компанию — сервис покажет события, которые важны именно ей, и разберёт каждое: факты, позиция банка,
        риски, возможности и следующий шаг.
      </p>
      <Link className="entry-tile" to="/clients">
        <span className="kicker">Открыть сервис</span>
        <strong>Разобрать события для компании</strong>
        <span>Не лента новостей: интерпретация с учётом кредитов, выручки, поставок и ВЭД.</span>
      </Link>
      <p className="top-note">
        {health.loading && "Проверяем сервис…"}
        {health.error && "Backend недоступен: запустите его командой из README."}
        {health.data &&
          `Сервис работает · компаний: ${health.data.companies} · событий: ${health.data.events} · режим модели: ${health.data.llm_mode}`}
      </p>
    </section>
  );
}
