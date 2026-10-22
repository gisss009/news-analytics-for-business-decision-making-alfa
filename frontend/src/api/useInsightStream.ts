import { useEffect, useState } from "react";

import { type ApiError, type InsightResponse, type StepEvent, api, toApiError, unwrap } from "./client";

export interface InsightState {
  steps: StepEvent[];
  result: InsightResponse | null;
  error: ApiError | null;
}

/**
 * Инсайт с прогрессом шагов агента: поток SSE /insight/stream (шаги, затем результат).
 * Если поток недоступен, данные берутся обычным запросом /insight.
 */
export function useInsightStream(eventId: string, client: string, role: string): InsightState {
  const [state, setState] = useState<InsightState>({ steps: [], result: null, error: null });

  useEffect(() => {
    setState({ steps: [], result: null, error: null });
    let finished = false;
    const qs = new URLSearchParams({ client, role }).toString();
    const es = new EventSource(`/api/events/${encodeURIComponent(eventId)}/insight/stream?${qs}`);

    const fallback = () => {
      api
        .GET("/events/{event_id}/insight", { params: { path: { event_id: eventId }, query: { client, role } } })
        .then((res) => setState((s) => ({ ...s, result: unwrap(res) })))
        .catch((e: unknown) => setState((s) => ({ ...s, error: toApiError(e) })));
    };

    es.addEventListener("step", (e) => {
      const step = JSON.parse((e as MessageEvent<string>).data) as StepEvent;
      setState((s) => ({ ...s, steps: [...s.steps, step] }));
    });
    es.addEventListener("done", (e) => {
      finished = true;
      es.close();
      const result = JSON.parse((e as MessageEvent<string>).data) as InsightResponse;
      setState((s) => ({ ...s, result }));
    });
    es.addEventListener("error", () => {
      es.close();
      if (!finished) {
        finished = true;
        fallback();
      }
    });
    return () => {
      finished = true;
      es.close();
    };
  }, [eventId, client, role]);

  return state;
}
