import { api, unwrap } from "../api/client";
import { useApi } from "../api/useApi";
import { REF_KIND_TITLES, refKind } from "./Claims";
import { ErrorBox } from "./Status";

/** Переход к первоисточнику: текст факта, страница аналитики банка, тезис или признак компании. */
export function SourcePanel({ refId, client, onClose }: { refId: string; client: string; onClose: () => void }) {
  const src = useApi(async () => unwrap(await api.GET("/refs", { params: { query: { ref: refId, client } } })),
    [refId, client]);
  const isLink = src.data?.url?.startsWith("http");
  return (
    <div className="card" aria-live="polite">
      <div className="event-top">
        <span className="kicker">{REF_KIND_TITLES[refKind(refId)] ?? "Источник"}</span>
        <button type="button" className="btn light" onClick={onClose} aria-label="Закрыть источник">
          Закрыть
        </button>
      </div>
      <p className="muted small" style={{ margin: "4px 0 0" }}>{refId}</p>
      {src.loading && <p className="muted">Открываем источник…</p>}
      {src.error && <ErrorBox error={src.error} />}
      {src.data && (
        <>
          <h3 style={{ marginTop: 8 }}>{src.data.title}</h3>
          <p className="muted small" style={{ margin: "4px 0 0" }}>
            {[src.data.source, src.data.date, src.data.page ? `стр. ${src.data.page}` : null].filter(Boolean).join(" · ")}
          </p>
          {src.data.quote && src.data.quote !== src.data.text ? (
            <>
              <p className="source-text">{src.data.text}</p>
              <blockquote className="source-quote">«{src.data.quote}»</blockquote>
            </>
          ) : (
            <p className="source-text">{src.data.text}</p>
          )}
          {src.data.excerpt_only && (
            <p className="muted small">Показаны фрагменты страницы, перенесённые из PDF-материала банка.</p>
          )}
          {isLink ? (
            <a href={src.data.url ?? undefined} target="_blank" rel="noreferrer">Открыть оригинал</a>
          ) : (
            src.data.url && <p className="muted small">Демо-новость из офлайн-набора: внешней ссылки нет.</p>
          )}
        </>
      )}
    </div>
  );
}

