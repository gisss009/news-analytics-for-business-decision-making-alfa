import { useSearchParams } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useApi } from "../api/useApi";

export const DEFAULT_ROLE = "cfo";

/** Роль ЛПР хранится в адресе (?role=), чтобы ссылку на ленту можно было переслать. */
export function useRole(): [string, (role: string) => void] {
  const [params, setParams] = useSearchParams();
  const role = params.get("role") ?? DEFAULT_ROLE;
  const setRole = (r: string) => {
    const next = new URLSearchParams(params);
    next.set("role", r);
    setParams(next, { replace: true });
  };
  return [role, setRole];
}

export function RolePicker() {
  const [role, setRole] = useRole();
  const roles = useApi(async () => unwrap(await api.GET("/roles")), []);
  return (
    <label>
      Роль пользователя
      <select id="role-picker" value={role} onChange={(e) => setRole(e.target.value)} disabled={!roles.data}>
        {(roles.data ?? [{ id: role, title: "…" }]).map((r) => (
          <option key={r.id} value={r.id}>
            {r.title}
          </option>
        ))}
      </select>
    </label>
  );
}
