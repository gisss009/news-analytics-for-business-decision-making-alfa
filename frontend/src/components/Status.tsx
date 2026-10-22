import type { ApiError } from "../api/client";

export function Loading({ text = "Загружаем" }: { text?: string }) {
  return (
    <p className="status" role="status">
      <span className="spinner" aria-hidden="true" />
      {text}
    </p>
  );
}

export function ErrorBox({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <strong>Не получилось загрузить данные</strong>
      <p>{error.message}</p>
      {error.traceId && <p className="muted small">Код для разработчиков: {error.traceId}</p>}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}
