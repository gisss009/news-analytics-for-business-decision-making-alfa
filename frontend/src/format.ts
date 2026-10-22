export function rub(v: number | null | undefined): string {
  if (v == null || v <= 1000) return "нет данных";
  if (v >= 1e9) return `${(v / 1e9).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} млрд ₽`;
  return `${(v / 1e6).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} млн ₽`;
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function pct(score: number): string {
  return `${Math.round(score * 100)}`;
}

export const EXPOSURE_TITLES: Record<string, string> = {
  rate_sensitivity: "Ключевая ставка",
  fx_exposure: "Курс рубля",
  commodity_links: "Цены сырья",
  supply_concentration: "Концентрация поставщиков",
  region_risk: "Регион",
  group_dependency: "Зависимость от группы",
  inflation_sensitivity: "Инфляция издержек",
  demand_sensitivity: "Потребительский спрос",
  sanctions_exposure: "Санкции и ВЭД",
  regulation_sensitivity: "Регулирование и тарифы",
};
