export function ru(value: number, one: string, few: string, many: string) {
  const mod10 = value % 10
  const mod100 = value % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

export function ago(iso?: string) {
  if (!iso) return "время не указано"
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return "время не указано"
  const minutes = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000))
  if (minutes < 1) return "только что"
  if (minutes < 60) return `${minutes} ${ru(minutes, "минуту", "минуты", "минут")} назад`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ${ru(hours, "час", "часа", "часов")} назад`
  const days = Math.round(hours / 24)
  if (days === 1) return "вчера"
  return `${days} ${ru(days, "день", "дня", "дней")} назад`
}

export function sourceLabel(name?: string) {
  const text = String(name || "").trim()
  if (/^https?:\/\//i.test(text)) {
    try {
      return new URL(text).hostname.replace(/^www\./, "")
    } catch {
      return text
    }
  }
  return text || "Источник не указан"
}

export function cleanTitle(title: string, source?: string) {
  let text = String(title || "").trim()
  for (let pass = 0; pass < 2; pass += 1) {
    const cut = text.lastIndexOf(" - ")
    if (cut === -1) break
    const tail = text.slice(cut + 3).trim()
    if (!tail || tail.length > 40 || tail.split(/\s+/).length > 4) break
    text = text.slice(0, cut).trim()
  }
  text = text.replace(/\s+\/\s+Экономика$/i, "").replace(/\s+[–—-]\s+Публикации$/i, "")
  if (source && text.toLowerCase().endsWith(source.toLowerCase())) {
    text = text.slice(0, -source.length).replace(/[\s\-–—|]+$/g, "").trim()
  }
  return text || title
}

const noise = /пособи|tesla|cybercab|черногор|севастопол|ревд|бурят|пензен|хакаси|vietnam|вьетнам|винодел|\bвина\b|почт|безработиц|водоканал|школьник|мастер-класс|мастер-лекц|ножки буша|бепешк/i

export function isBusinessNews(card: { source_type?: string; title?: string }) {
  if (!card || card.source_type !== "external_news") return false
  const title = String(card.title || "")
  const cyrillic = (title.match(/[а-яё]/gi) || []).length
  return cyrillic >= 12 && !noise.test(title)
}
