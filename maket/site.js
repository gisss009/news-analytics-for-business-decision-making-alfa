const home = document.querySelector("#home");
const newsList = document.querySelector("#news-list");
const newsScreen = document.querySelector("#news");
const companies = document.querySelector("#companies");
const entry = document.querySelector("#entry");
const events = document.querySelector("#events");
const reading = document.querySelector("#reading");
const readingBody = document.querySelector("#reading-body");
const stories = document.querySelector("#stories");
const count = document.querySelector("#count");
const crumb = document.querySelector("#crumb");
const eventsTitle = document.querySelector("#events-title");
const eventsLead = document.querySelector("#events-lead");
const navHome = document.querySelector("#nav-home");
const navNews = document.querySelector("#nav-news");
const navEntry = document.querySelector("#nav-entry");
const parade = document.querySelector("#parade");
const minionSwitch = document.querySelector("#minion-switch");

const state = {
  cards: [],
  news: [],
  pool: [],
  ready: false,
  clientId: null,
  screen: "home",
  storyId: null,
};

minionSwitch.addEventListener("click", () => {
  const on = document.body.classList.toggle("minions-on");
  minionSwitch.setAttribute("aria-pressed", on ? "true" : "false");
});

const godzillaShow = document.querySelector("#godzilla-show");
const toaster = document.querySelector("#toaster");
const godzillaLive = godzillaShow.querySelector(".godzilla-live");
let yellTimers = [];

function stopYell() {
  yellTimers.forEach((timer) => clearTimeout(timer));
  yellTimers = [];
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

function yellRickroll() {
  stopYell();
  godzillaLive.textContent = "Тебя зарикроллили!";
  if (!window.speechSynthesis) return;
  const line = "Тебя зарикроллили!";
  [{ pitch: 0.4, delay: 0 }, { pitch: 0.75, delay: 160 }, { pitch: 0.35, delay: 1300 }].forEach((voice) => {
    yellTimers.push(setTimeout(() => {
      const utter = new SpeechSynthesisUtterance(line);
      utter.lang = "ru-RU";
      utter.pitch = voice.pitch;
      utter.rate = voice.pitch < 0.5 ? 0.9 : 1.05;
      utter.volume = 1;
      window.speechSynthesis.speak(utter);
    }, voice.delay));
  });
}

function openGodzillas() {
  godzillaShow.hidden = false;
  toaster.setAttribute("aria-expanded", "true");
  requestAnimationFrame(() => godzillaShow.classList.add("on"));
  yellRickroll();
}

function closeGodzillas() {
  godzillaShow.classList.remove("on");
  godzillaShow.hidden = true;
  toaster.setAttribute("aria-expanded", "false");
  godzillaLive.textContent = "";
  stopYell();
}

toaster.addEventListener("click", () => {
  if (godzillaShow.hidden) openGodzillas();
  else closeGodzillas();
});
document.querySelector("#godzilla-close").addEventListener("click", closeGodzillas);
godzillaShow.addEventListener("click", (event) => {
  if (event.target === godzillaShow) closeGodzillas();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !godzillaShow.hidden) closeGodzillas();
});

navHome.addEventListener("click", () => show("home"));
navNews.addEventListener("click", () => show("news"));
navEntry.addEventListener("click", () => show(state.clientId ? "events" : "entry"));
document.querySelector("#enter-service").addEventListener("click", () => show("entry"));
document.querySelector("#back").addEventListener("click", () => show("events"));

buildParade();
renderCompanies();
show("home");
load();

async function load() {
  const business = await fetchJson("../data/out/business_news.json");
  const materials = await fetchJson("../data/out/materials.json");
  state.cards = materials || [];
  const businessNews = (business && business.length ? business : state.cards).filter(isBusinessNews);
  state.news = businessNews.sort(byDate);
  const bank = state.cards.filter((card) => card.source_type === "alfa_research");
  state.pool = [...bank, ...state.news];
  state.ready = Boolean(materials || business);
  if (!state.ready) {
    count.textContent = "Нет файла выгрузки";
    newsList.append(note("Запустите сайт из корня проекта, чтобы страница увидела data/out."));
    return;
  }
  renderNews();
}

async function fetchJson(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

function renderCompanies() {
  companies.innerHTML = "";
  for (const client of Scenario.clients) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "company";
    const title = document.createElement("h2");
    title.textContent = client.name;
    const sector = document.createElement("p");
    sector.className = "kicker";
    sector.textContent = `${client.sector} · ${client.region}`;
    const traits = document.createElement("ul");
    traits.className = "traits";
    const finance = document.createElement("p");
    finance.textContent = client.finance;
    for (const trait of client.features) {
      const item = document.createElement("li");
      item.textContent = trait.text;
      traits.append(item);
    }
    button.append(sector, title, finance, traits);
    button.addEventListener("click", () => openClient(client.id));
    companies.append(button);
  }
}

function openClient(clientId) {
  if (!state.ready) return;
  state.clientId = clientId;
  state.storyId = null;
  state.extraEvent = null;
  show("events");
}

function show(screen) {
  state.screen = screen;
  home.hidden = screen !== "home";
  newsScreen.hidden = screen !== "news";
  entry.hidden = screen !== "entry";
  events.hidden = screen !== "events";
  reading.hidden = screen !== "reading";
  markTab(navHome, screen === "home");
  markTab(navNews, screen === "news");
  markTab(navEntry, screen === "entry" || screen === "events" || screen === "reading");
  if (screen === "news") renderNews();
  if (screen === "events") renderEvents();
  if (screen === "reading") renderReading();
  if (screen === "home") count.textContent = "Вход в сервис";
  if (screen === "entry") count.textContent = state.ready ? "Выберите компанию" : count.textContent;
}

function markTab(button, on) {
  if (on) button.setAttribute("aria-current", "page");
  else button.removeAttribute("aria-current");
}

function renderNews() {
  if (!state.ready && !state.news.length) return;
  newsList.innerHTML = "";
  if (state.screen === "news") {
    count.textContent = state.news.length
      ? `${state.news.length} ${newsWord(state.news.length)}`
      : "В ленте пусто";
  }
  if (!state.news.length) {
    newsList.append(note("В выгрузке нет деловых новостей."));
    return;
  }
  for (const card of state.news) {
    const link = document.createElement("a");
    link.className = "news-item";
    link.href = (card.anchor && card.anchor.url) || "#";
    link.target = "_blank";
    link.rel = "noreferrer";
    const meta = document.createElement("p");
    meta.className = "news-meta";
    const source = document.createElement("span");
    source.className = "news-source";
    source.textContent = sourceLabel(card);
    const when = document.createElement("span");
    when.textContent = ago(card.published_at);
    meta.append(source, document.createTextNode(" · "), when);
    const title = document.createElement("h2");
    title.textContent = cleanTitle(card.title, card.source_name);
    link.append(meta, title);
    newsList.append(link);
  }
}

function isBusinessNews(card) {
  if (!card || card.source_type !== "external_news") return false;
  const title = String(card.title || "");
  const cyrillic = (title.match(/[а-яё]/gi) || []).length;
  if (cyrillic < 12) return false;
  return !/пособи|tesla|cybercab|черногор|севастопол|ревд|бурят|пензен|хакаси|vietnam|вьетнам|винодел|\bвина\b|почт|безработиц|водоканал|школьник|мастер-класс|мастер-лекц|ножки буша|бепешк/i.test(title);
}

function byDate(left, right) {
  return String(right.published_at || "").localeCompare(String(left.published_at || ""));
}

function sourceLabel(card) {
  const name = String(card.source_name || "").trim();
  if (/^https?:\/\//i.test(name)) {
    try {
      return new URL(name).hostname.replace(/^www\./, "");
    } catch (error) {
      return name;
    }
  }
  return name || "Источник не указан";
}

function cleanTitle(title, source) {
  let text = String(title || "").trim();
  for (let pass = 0; pass < 2; pass += 1) {
    const cut = text.lastIndexOf(" - ");
    if (cut === -1) break;
    const tail = text.slice(cut + 3).trim();
    if (!tail || tail.length > 40 || tail.split(/\s+/).length > 4) break;
    text = text.slice(0, cut).trim();
  }
  text = text.replace(/\s+\/\s+Экономика$/i, "").replace(/\s+[–—-]\s+Публикации$/i, "");
  if (source && text.toLowerCase().endsWith(source.toLowerCase())) {
    text = text.slice(0, -source.length).replace(/[\s\-–—|]+$/g, "").trim();
  }
  return text || title;
}

function ago(iso) {
  if (!iso) return "время не указано";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "время не указано";
  const minutes = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000));
  if (minutes < 1) return "только что";
  if (minutes < 60) return `${minutes} ${ru(minutes, "минуту", "минуты", "минут")} назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ${ru(hours, "час", "часа", "часов")} назад`;
  const days = Math.round(hours / 24);
  if (days === 1) return "вчера";
  return `${days} ${ru(days, "день", "дня", "дней")} назад`;
}

function ru(value, one, few, many) {
  const mod10 = value % 10;
  const mod100 = value % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function newsWord(value) {
  const mod10 = value % 10;
  const mod100 = value % 100;
  if (mod10 === 1 && mod100 !== 11) return "новость";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "новости";
  return "новостей";
}

function renderEvents() {
  const client = currentClient();
  const items = Scenario.storiesFor(client.id, state.pool);
  crumb.textContent = client.name;
  eventsTitle.textContent = `Что важно компании «${client.name}»`;
  eventsLead.textContent = "События отбираются по признакам этой компании: кредиты, выручка, поставки. У другой компании список другой.";
  count.textContent = `${items.length} ${eventsWord(items.length)} · ${client.sector}`;
  stories.innerHTML = "";
  if (!items.length) {
    stories.append(note("Для этой компании в текущей выгрузке нет события из двух независимых материалов."));
    return;
  }
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "story";
    const kicker = document.createElement("p");
    kicker.className = "kicker";
    kicker.textContent = item.action ? "Есть следующий шаг" : "Шаг не следует";
    const title = document.createElement("h2");
    title.textContent = item.title;
    const why = document.createElement("p");
    why.textContent = item.why;
    const tags = document.createElement("ul");
    tags.className = "traits";
    for (const factor of item.factors) {
      const tag = document.createElement("li");
      tag.textContent = factor.label;
      tags.append(tag);
    }
    button.append(kicker, title, why, tags);
    button.addEventListener("click", () => {
      state.storyId = item.id;
      show("reading");
    });
    stories.append(button);
  }
}

function renderReading() {
  const client = currentClient();
  const listed = Scenario.storiesFor(client.id, state.pool).find((story) => story.id === state.storyId);
  const item = listed || (state.extraEvent && state.extraEvent.id === state.storyId ? state.extraEvent : null);
  readingBody.innerHTML = "";
  if (!item) {
    readingBody.append(note("Событие не найдено."));
    return;
  }
  count.textContent = client.name;
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = `${client.name} · ${client.sector}`;
  const title = document.createElement("h1");
  title.textContent = item.title;
  const why = document.createElement("p");
  why.className = "why";
  why.textContent = item.why;
  readingBody.append(kicker, title, why);
  readingBody.append(block("Что произошло", factorList(item.happened)));
  readingBody.append(block("Почему это важно для этой компании", paragraphs(item.whyCompany)));
  readingBody.append(block("Какие последствия возможны", consequences(item)));
  readingBody.append(block("Какое действие уместно", actionBlock(item)));
  readingBody.append(block("Как это оценивает банк", bankBlock(item.bank)));
  readingBody.append(block("На чём основан вывод", basis(item)));
  readingBody.append(block("Как это собрано", traceList(item.trace)));
  readingBody.append(block("Уточнить или взять другой срез", cutForm()));
}

function consequences(item) {
  const wrap = document.createElement("div");
  if (item.risks.length) {
    const label = document.createElement("p");
    label.className = "kicker";
    label.textContent = "Риски";
    wrap.append(label, bullets(item.risks));
  }
  if (item.opportunities.length) {
    const label = document.createElement("p");
    label.className = "kicker";
    label.textContent = "Возможности";
    wrap.append(label, bullets(item.opportunities));
  }
  if (!wrap.childNodes.length) wrap.append(note("По этой теме отдельных последствий для компании нет."));
  return wrap;
}

function basis(item) {
  const wrap = document.createElement("div");
  wrap.append(serviceNote(item.conclusion));
  if (item.featuresUsed.length) {
    const label = document.createElement("p");
    label.className = "kicker";
    label.textContent = "Признаки компании";
    wrap.append(label, bullets(item.featuresUsed));
  }
  const sources = document.createElement("p");
  sources.className = "kicker";
  sources.textContent = "Источники";
  wrap.append(sources, sourceList(item.sources));
  return wrap;
}

function traceList(steps) {
  const list = document.createElement("ol");
  list.className = "trace";
  for (const step of steps) {
    const item = document.createElement("li");
    item.textContent = `${step.name}. ${step.text}`;
    list.append(item);
  }
  return list;
}

function cutForm() {
  const form = document.createElement("form");
  form.className = "cut";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Ставка, курс, нефть, спрос, сталь, зерно";
  input.setAttribute("aria-label", "Другой срез");
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = "Показать срез";
  const error = document.createElement("p");
  error.className = "source-line";
  form.append(input, button);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const result = Scenario.answerQuestion(state.clientId, state.pool, input.value);
    if (result.error) {
      error.textContent = result.error;
      form.after(error);
      return;
    }
    error.remove();
    state.storyId = result.event.id;
    state.extraEvent = result.event;
    renderReading();
  });
  return form;
}

function factorList(factors) {
  const list = document.createElement("div");
  for (const factor of factors) {
    const row = document.createElement("div");
    row.className = "factor";
    const label = document.createElement("p");
    label.className = "kicker";
    label.textContent = factor.kind || factor.label;
    const gloss = document.createElement("p");
    gloss.textContent = factor.gloss;
    const source = document.createElement("p");
    source.className = "source-line";
    source.textContent = `${factor.source}. ${factor.title}`;
    row.append(label, gloss, source);
    if (factor.href) row.append(link(factor.href, "Открыть материал"));
    list.append(row);
  }
  return list;
}

function bankBlock(lines) {
  if (!lines.length) {
    const paragraph = document.createElement("p");
    paragraph.textContent = "В обзорах банка по этому сочетанию факторов прямой формулировки нет. Ниже вывод сервиса на неё не опирается.";
    return paragraph;
  }
  const list = document.createElement("div");
  for (const line of lines) {
    const paragraph = document.createElement("p");
    paragraph.className = "bank-note";
    paragraph.textContent = `${line.role}. ${line.text}`;
    const source = document.createElement("p");
    source.className = "source-line";
    source.textContent = line.source;
    list.append(paragraph, source);
    if (line.href) list.append(link(line.href, "Открыть обзор"));
  }
  return list;
}

function serviceNote(text) {
  const wrap = document.createElement("div");
  wrap.className = "service-note";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  const mark = document.createElement("p");
  mark.className = "fine";
  mark.textContent = "Собрано правилами из нескольких материалов. Это не позиция банка и не ответ модели.";
  wrap.append(paragraph, mark);
  return wrap;
}

function actionBlock(item) {
  const wrap = document.createElement("div");
  wrap.className = item.action ? "action-note" : "no-action";
  const paragraph = document.createElement("p");
  paragraph.textContent = item.action || "Отдельное действие не предлагаем.";
  const why = document.createElement("p");
  why.textContent = item.actionWhy;
  wrap.append(paragraph, why);
  return wrap;
}

function sourceList(sources) {
  const list = document.createElement("ul");
  list.className = "sources";
  for (const source of sources) {
    const item = document.createElement("li");
    item.textContent = `${source.kind}: ${source.name}. ${source.title}`;
    if (source.href) item.append(" ", link(source.href, "открыть"));
    list.append(item);
  }
  return list;
}

function block(heading, node) {
  const section = document.createElement("section");
  const title = document.createElement("h2");
  title.textContent = heading;
  section.append(title, node);
  return section;
}

function paragraphs(items) {
  const wrap = document.createElement("div");
  for (const text of items) {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    wrap.append(paragraph);
  }
  return wrap;
}

function bullets(items) {
  const list = document.createElement("ul");
  for (const text of items) {
    const item = document.createElement("li");
    item.textContent = text;
    list.append(item);
  }
  return list;
}

function link(href, label) {
  const anchor = document.createElement("a");
  anchor.className = "out";
  anchor.href = href;
  anchor.textContent = label;
  if (/^https?:/i.test(href)) {
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
  }
  return anchor;
}

function note(text) {
  const paragraph = document.createElement("p");
  paragraph.className = "paper-note";
  paragraph.textContent = text;
  return paragraph;
}

function currentClient() {
  return Scenario.clients.find((client) => client.id === state.clientId);
}

function eventsWord(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return "событие";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "события";
  return "событий";
}

function buildParade() {
  const crew = [
    { left: "6%", delay: "0s", eyes: 2, scale: 0.92 },
    { left: "22%", delay: "0.08s", eyes: 1, scale: 1.05 },
    { left: "40%", delay: "0.16s", eyes: 2, scale: 0.84 },
    { left: "58%", delay: "0.05s", eyes: 2, scale: 1 },
    { left: "76%", delay: "0.2s", eyes: 1, scale: 0.96 },
  ];
  for (const minion of crew) {
    const figure = document.createElement("div");
    figure.className = "minion";
    figure.style.left = minion.left;
    figure.style.transitionDelay = minion.delay;
    figure.innerHTML = `<div class="minion-size" style="transform:scale(${minion.scale})"><div class="minion-bob">${minionSvg(minion.eyes)}</div></div>`;
    parade.append(figure);
  }
}

function minionSvg(eyes) {
  const goggles = eyes === 1
    ? `<circle cx="46" cy="46" r="16" fill="#f7f7f7" stroke="#222" stroke-width="3"/>
       <circle cx="46" cy="48" r="6" fill="#5a3318"/>`
    : `<circle cx="34" cy="46" r="13" fill="#f7f7f7" stroke="#222" stroke-width="3"/>
       <circle cx="58" cy="46" r="13" fill="#f7f7f7" stroke="#222" stroke-width="3"/>
       <circle cx="35" cy="48" r="5" fill="#5a3318"/>
       <circle cx="59" cy="48" r="5" fill="#5a3318"/>`;
  return `
    <svg viewBox="0 0 92 150" width="92" height="150" aria-hidden="true">
      <ellipse cx="46" cy="58" rx="28" ry="40" fill="#f5d90a"/>
      <rect x="22" y="78" width="48" height="40" rx="10" fill="#3d5a99"/>
      <rect x="22" y="78" width="48" height="10" fill="#222"/>
      <path d="M18 48h56" stroke="#222" stroke-width="4"/>
      <g class="lid">${goggles}</g>
      <path d="M36 66q10 8 20 0" fill="none" stroke="#222" stroke-width="2" stroke-linecap="round"/>
      <rect x="18" y="112" width="16" height="14" rx="4" fill="#111"/>
      <rect x="58" y="112" width="16" height="14" rx="4" fill="#111"/>
      <rect x="8" y="84" width="12" height="10" rx="4" fill="#111"/>
      <rect x="72" y="84" width="12" height="10" rx="4" fill="#111"/>
    </svg>`;
}
