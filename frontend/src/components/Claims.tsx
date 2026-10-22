import type { Claim } from "../api/client";

export const LABEL_TITLES: Record<Claim["label"], string> = {
  fact: "Факт",
  bank_analytics: "Аналитика Альфа-Банка",
  model_inference: "Вывод ИИ",
};

export const REF_KIND_TITLES: Record<string, string> = {
  news: "Новость",
  news_fact: "Факт из новости",
  doc: "Аналитика банка",
  thesis: "Тезис банка",
  feat: "Признак компании",
  exp: "Чувствительность",
  cp: "Контрагент",
};

export function refKind(ref: string): string {
  if (/^news:[^#]+#f\d+$/.test(ref)) return "news_fact";
  return ref.split(":", 1)[0];
}

export function LabelChip({ label }: { label: Claim["label"] }) {
  return <span className={`label ${label}`}>{LABEL_TITLES[label]}</span>;
}

interface RefProps {
  refId: string;
  active: boolean;
  onOpen: (ref: string) => void;
}

export function RefChip({ refId, active, onOpen }: RefProps) {
  return (
    <button type="button" className="ref" aria-pressed={active} title={`Открыть источник: ${REF_KIND_TITLES[refKind(refId)] ?? refId}`}
            onClick={() => onOpen(refId)}>
      {refId}
    </button>
  );
}

interface ClaimListProps {
  claims: Claim[];
  activeRef: string | null;
  onOpen: (ref: string) => void;
}

/** Утверждения блока: у каждого видна метка происхождения и ссылки на источники. */
export function ClaimList({ claims, activeRef, onOpen }: ClaimListProps) {
  return (
    <ul className="claims">
      {claims.map((c) => (
        <li key={c.id} className={`claim ${c.label}`}>
          <p>{c.text}</p>
          <div className="claim-meta">
            <LabelChip label={c.label} />
            {c.refs.map((r) => (
              <RefChip key={r} refId={r} active={activeRef === r} onOpen={onOpen} />
            ))}
            {c.confidence < 0.5 && <span className="chip">низкая уверенность</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
