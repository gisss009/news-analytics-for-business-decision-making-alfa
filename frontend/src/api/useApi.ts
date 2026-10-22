import { useCallback, useEffect, useState } from "react";

import { type ApiError, toApiError } from "./client";

export interface Loadable<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** Загрузка данных с сервера: состояние запроса не дублируется в глобальном хранилище. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]): Loadable<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    load()
      .then((d) => alive && setData(d))
      .catch((e: unknown) => alive && setError(toApiError(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [...deps, tick]);

  return { data, error, loading, reload };
}
