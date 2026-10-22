import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Типизированный клиент backend: типы генерируются из OpenAPI (npm run gen:api). */
export const api = createClient<paths>({ baseUrl: "/api" });

export type Schemas = components["schemas"];
export type ClientSummary = Schemas["ClientSummary"];
export type Role = Schemas["Role"];
export type Feed = Schemas["Feed"];
export type FeedEvent = Schemas["FeedEvent"];
export type InsightResponse = Schemas["InsightResponse"];
export type Insight = Schemas["Insight"];
export type Claim = Schemas["Claim"];
export type RefView = Schemas["RefView"];
export type StepEvent = Schemas["StepEvent"];

/** Ошибка API в едином формате backend: {error: {code, message, trace_id}}. */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public traceId: string | null,
  ) {
    super(message);
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; trace_id?: string };
}

/** Превращает ответ openapi-fetch в данные или понятную ошибку. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.data !== undefined && res.response.ok) return res.data;
  const env = (res.error ?? {}) as ErrorEnvelope;
  throw new ApiError(
    env.error?.code ?? `http_${res.response.status}`,
    env.error?.message ?? (res.response.status >= 500 || res.response.status === 0
      ? "Сервис недоступен. Проверьте, что backend запущен."
      : `Ошибка запроса (${res.response.status})`),
    env.error?.trace_id ?? res.response.headers.get("X-Trace-Id"),
  );
}

export function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  return new ApiError("network", "Нет связи с сервисом. Проверьте, что backend запущен.", null);
}
