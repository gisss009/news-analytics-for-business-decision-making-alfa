"use strict";

const CLIENTS = [
  {
    id: "oil",
    name: "Северная нефть",
    sector: "Нефтегаз",
    activity: "добыча и экспорт нефти",
    region: "Западная Сибирь, отгрузка морем",
    finance: "часть инвестиций и оборота финансируется кредитами",
    features: [
      { id: "debt", text: "есть кредиты, инвестиции частично на заёмные деньги" },
      { id: "export", text: "выручка в валюте, результат в рублях" },
      { id: "commodity", text: "цена нефти входит в выручку" },
      { id: "freight", text: "отгрузка танкерами" },
    ],
  },
  {
    id: "retail",
    name: "Дом торговли",
    sector: "Ритейл",
    activity: "розничная сеть",
    region: "крупные города России",
    finance: "товарный запас закупается в кредит",
    features: [
      { id: "debt", text: "товарный запас финансируется коротким долгом" },
      { id: "demand", text: "выручка зависит от спроса" },
      { id: "wages", text: "фонд оплаты: крупный расход" },
      { id: "prices", text: "ценник зависит от инфляции" },
    ],
  },
  {
    id: "steel",
    name: "Северный прокат",
    sector: "Металлургия",
    activity: "производство и экспорт плоского проката",
    region: "Урал, часть контрактов на экспорт",
    finance: "оборотный капитал на кредитах",
    features: [
      { id: "debt", text: "оборотный капитал заёмный" },
      { id: "export", text: "часть контрактов в валюте" },
      { id: "steel", text: "выручка зависит от цены проката" },
    ],
  },
  {
    id: "agro",
    name: "Поле и зерно",
    sector: "Агросектор",
    activity: "производство и экспорт зерна",
    region: "юг России, партии в Китай",
    finance: "сезонный кредит под урожай",
    features: [
      { id: "debt", text: "сезонное финансирование на заёмных деньгах" },
      { id: "export", text: "экспортная выручка в валюте" },
      { id: "grain", text: "основная поставка: зерно" },
    ],
  },
];

const TOPIC_TESTS = [
  ["Ключевая ставка", /ключев[а-яё]*\s+ставк|ставк[а-яё]*\s+цб|банк[ае]?\s+россии/i],
  ["Инфляция", /инфляц/i],
  ["Валютные курсы", /рубл|доллар|юан|курс валют|крепок/i],
  ["Сырьё", /нефт|brent|уг[ое]л/i],
  ["Спрос", /спрос|потреблен|розничн/i],
  ["Рынок труда", /зарплат/i],
  ["Санкции и дипломатия", /санкц/i],
  ["Внешняя торговля", /экспорт|импорт(?!озамещ)|спг/i],
  ["Логистика и поставки", /фрахт|логист/i],
  ["Долг и облигации", /облигац|\bофз\b/i],
  ["Сталь", /стал[ьи]|прокат/i],
  ["Зерно", /зерн/i],
];

const BANK_TOPICS = {
  "Ключевая ставка ЦБ РФ": ["Ключевая ставка"],
  "Потребление на пике": ["Спрос", "Рынок труда"],
  "Российская сталь": ["Сталь"],
  "Инфляция 25–31 августа: основные выводы": ["Инфляция"],
  "Макростатистика 7М26": ["Рынок труда"],
  "Макростатистика 1П26": ["Инфляция"],
  "Бонд Бриф: итоги недели": ["Ключевая ставка"],
  "Тактический взгляд на 3-й квартал 2026": ["Долг и облигации"],
};

const FEATURE_TOPICS = {
  debt: ["Ключевая ставка"],
  export: ["Валютные курсы", "Внешняя торговля", "Санкции и дипломатия"],
  commodity: ["Сырьё"],
  freight: ["Логистика и поставки"],
  demand: ["Спрос"],
  wages: ["Рынок труда"],
  prices: ["Инфляция"],
  steel: ["Сталь"],
  grain: ["Зерно", "Внешняя торговля"],
};

const RELATED = {
  "Ключевая ставка": ["Инфляция"],
  "Инфляция": ["Спрос", "Ключевая ставка"],
  "Спрос": ["Инфляция", "Рынок труда"],
  "Валютные курсы": ["Сырьё", "Внешняя торговля"],
  "Сырьё": ["Валютные курсы"],
  "Сталь": ["Валютные курсы"],
  "Зерно": ["Валютные курсы", "Внешняя торговля"],
  "Внешняя торговля": ["Валютные курсы", "Санкции и дипломатия"],
  "Санкции и дипломатия": ["Внешняя торговля"],
  "Логистика и поставки": ["Сырьё"],
  "Долг и облигации": ["Ключевая ставка"],
  "Рынок труда": ["Спрос"],
};

function eventsFor(clientId, cards, options) {
  const client = CLIENTS.find((item) => item.id === clientId);
  if (!client || !Array.isArray(cards)) return [];
  const only = options && options.only;
  const limit = options && options.limit ? options.limit : 3;
  const topics = only ? [only] : clientTopics(client);
  const events = topics
    .map((topic) => buildEvent(client, topic, cards))
    .filter(Boolean)
    .sort((left, right) => right.rank - left.rank);
  return events.slice(0, limit);
}

function answerQuestion(clientId, cards, question) {
  const topic = topicFromQuestion(question);
  if (!topic) {
    return { error: "В материалах нет такого среза. Спросите про ставку, курс, нефть, инфляцию, спрос, сталь или зерно." };
  }
  const found = eventsFor(clientId, cards, { only: topic, limit: 1 });
  if (!found.length) return { error: `По теме «${topic}» в текущей выгрузке материалов нет.` };
  return { event: found[0] };
}

function storiesFor(clientId, cards) {
  return eventsFor(clientId, cards);
}

function buildEvent(client, topic, cards) {
  const own = matching(cards, topic, client).sort(byDate);
  if (!own.length) return null;
  const extras = [];
  for (const related of RELATED[topic] || []) {
    if (!clientTopics(client).includes(related)) continue;
    const hit = matching(cards, related, client).find((card) => !own.some((item) => item.id === card.id));
    if (hit) extras.push(hit);
  }
  const news = own.filter((card) => card.source_type !== "alfa_research").slice(0, 2);
  const bankCard = own.find((card) => card.source_type === "alfa_research" && titleHits(card, topic))
    || own.find((card) => card.source_type === "alfa_research");
  const picked = unique([...news, ...(bankCard ? [bankCard] : []), ...extras.slice(0, 2)]);
  const fits = clientTopics(client).includes(topic);
  const effectTopics = [topic, ...extras.map((card) => primaryTopic(card, topic))].filter(Boolean);
  const effects = effectsFor(client, effectTopics);
  const happened = picked.map(presentCard);
  const bank = bankQuotes(picked.filter((card) => card.source_type === "alfa_research"), topic);
  const risks = effects.map((item) => item.risk).filter(Boolean);
  const opportunities = effects.map((item) => item.opportunity).filter(Boolean);
  const action = fits
    ? effects.filter((item) => item.topic === topic).map((item) => item.action).filter(Boolean)[0] || ""
    : "";
  const featuresUsed = client.features.filter((feature) => (FEATURE_TOPICS[feature.id] || []).includes(topic) || effects.some((item) => item.feature === feature.id));
  return {
    id: topic,
    title: eventTitle(topic, client),
    why: fits ? whyLine(client, topic, picked) : `Тема есть в материалах, но на признаки «${client.name}» она не садится.`,
    factors: [...new Set(picked.flatMap((card) => topicsOf(card)))].slice(0, 4).map((label) => ({ label })),
    happened,
    whyCompany: whyCompany(client, topic, fits, picked),
    risks: fits ? risks : ["Отдельного риска для этой компании из темы не следует: нет подходящего признака."],
    opportunities: fits ? opportunities : [],
    action,
    actionWhy: action
      ? "Шаг привязан к признаку компании и к материалам по теме, а не к одному заголовку."
      : fits
        ? "Отдельный шаг не предлагаем: из материалов не следует конкретное действие сверх наблюдения."
        : "Шаг не предлагаем. Иначе это был бы отраслевой пересказ без контекста компании.",
    bank,
    conclusion: conclusion(client, topic, fits, picked, bank),
    sources: unique(picked).map(presentSource),
    trace: trace(client, topic, picked, bank, featuresUsed),
    featuresUsed: featuresUsed.map((feature) => feature.text),
    rank: rankEvent(client, topic, picked, bank, fits, extras),
  };
}

function whyCompany(client, topic, fits, picked) {
  if (!fits) {
    return [
      `${client.name}: ${client.activity}, ${client.region}. Финансы: ${client.finance}.`,
      `Тема «${topic}» не пересекается с этими признаками. Показывать её как событие компании было бы отраслевым трендом, а не контекстом клиента.`,
    ];
  }
  const lines = [
    `${client.name}: ${client.activity}. Регион: ${client.region}. ${client.finance}.`,
    whyLine(client, topic, picked),
  ];
  if (picked.length > 1) {
    lines.push("В разборе больше одного материала. Вывод не сводится к очевидному следствию из одной новости.");
  }
  return lines;
}

function whyLine(client, topic, picked) {
  const feature = client.features.find((item) => (FEATURE_TOPICS[item.id] || []).includes(topic));
  const lead = picked[0];
  const source = lead ? sourceName(lead) : "материал";
  if (topic === "Ключевая ставка" && feature && feature.id === "debt") {
    return `Ставка важна не как новость ЦБ, а потому что у компании ${feature.text}. Пока снижения нет, кредитная нагрузка не дешевеет.`;
  }
  if (!feature) return `${source} пишет про «${topic}». Прямого признака компании под эту тему нет.`;
  return `«${topic}» садится на признак компании: ${feature.text}. Источник: ${source}.`;
}

function conclusion(client, topic, fits, picked, bank) {
  if (!fits) return `Для «${client.name}» тема «${topic}» остаётся фоном. На её признаки она не влияет, поэтому отдельного вывода для компании нет.`;
  if (topic === "Ключевая ставка") {
    const pause = picked.some((card) => /14/.test(blob(card)) && /ставк|пауз/i.test(blob(card)));
    const core = pause
      ? `Для «${client.name}» пауза ставки около 14% значит, что кредиты дешевле не станут. Деньги остаются дорогими, и нагрузка на заёмное финансирование в ближайшее время не снизится.`
      : `Для «${client.name}» новости о ставке важны из-за заёмного финансирования. Снижения нагрузки нет, пока материалы сами не фиксируют более дешёвые деньги.`;
    const bankBit = bank.length ? " Позиция банка в разборе отделена и приведена выше по обзору, а не смешана с этим выводом." : " Прямой формулировки банка по этой подборке нет, поэтому вывод на неё не опирается.";
    return core + bankBit;
  }
  if (topic === "Валютные курсы" || topic === "Сталь" || topic === "Зерно" || topic === "Сырьё") {
    return `Для «${client.name}» это не заголовок сам по себе. ${topic === "Валютные курсы" ? "Курс меняет рублёвую выручку с валютного контракта." : "Цена и объём поставки меняют выручку, а курс может тянуть её в другую сторону, если рядом есть такой материал."} Это чтение признаков компании, не позиция банка.`;
  }
  if (topic === "Спрос") {
    return `Для «${client.name}» спрос читается через продажи и запас. Если материалы показывают остывание, запас на кредите не повод наращивать закупку.`;
  }
  if (topic === "Инфляция") {
    return `Для «${client.name}» инфляция важна как ценник, а не как сводка Росстата. Замедление цен само по себе не значит, что продажи вырастут, поэтому отдельный шаг из одной инфляции не следует.`;
  }
  return `Вывод для «${client.name}» собран из признаков компании и материалов по теме «${topic}». Это не пересказ одной новости и не позиция банка.`;
}

function effectsFor(client, topics) {
  const effects = [];
  for (const feature of client.features) {
    for (const topic of topics) {
      if (!(FEATURE_TOPICS[feature.id] || []).includes(topic)) continue;
      const effect = EFFECT[`${topic}:${feature.id}`];
      if (effect && effect.risk) effects.push({ feature: feature.id, topic, ...effect });
    }
  }
  return effects;
}

const EFFECT = {
  "Ключевая ставка:debt": {
    risk: "Кредитная нагрузка не снижается, пока ставка не пошла вниз.",
    opportunity: "Пауза не добавляет нового повышения к уже дорогому долгу.",
    action: "Не переносить инвестиции и оборот на надежду, что кредиты скоро подешевеют.",
  },
  "Валютные курсы:export": {
    risk: "Крепкий рубль оставляет меньше рублей с той же валютной выручки.",
    opportunity: "Рублёвый контракт курс не съедает.",
    action: "Разложить ближайшие контракты на валютные и рублёвые и смотреть курс только по валютной доле.",
  },
  "Сырьё:commodity": {
    risk: "Выручка двигается вместе с ценой нефти, но курс и фрахт могут забрать часть плюса.",
    opportunity: "Более высокая цена увеличивает валютную выручку по незакрытым поставкам.",
    action: "Сверить цену поставки с курсом и фрахтом, а не смотреть на нефть отдельно.",
  },
  "Логистика и поставки:freight": {
    risk: "Дорогая доставка уменьшает то, что остаётся от цены сырья.",
    opportunity: "",
    action: "Заложить новый фрахт в маржу ближайших отгрузок.",
  },
  "Инфляция:prices": {
    risk: "Замедление инфляции не равно росту продаж.",
    opportunity: "Спокойный ценник проще держать, если закупка не раздута.",
    action: "",
  },
  "Спрос:demand": {
    risk: "Запас, собранный под прежний спрос, зависает.",
    opportunity: "",
    action: "Не наращивать закупку, пока материалы не показывают оживление спроса.",
  },
  "Рынок труда:wages": {
    risk: "Фонд оплаты не остывает так же быстро, как продажи.",
    opportunity: "",
    action: "",
  },
  "Ключевая ставка:debt-retail": {},
  "Сталь:steel": {
    risk: "Ценовой плюс по прокату не доходит до рублёвой выручки, если контракт валютный и рубль крепкий.",
    opportunity: "В рублёвом контракте цена проката доходит до выручки целиком.",
    action: "Проверить, какая доля ближайших контрактов в валюте.",
  },
  "Зерно:grain": {
    risk: "Больше тонн не значит больше рублей с тонны, если рубль крепчает.",
    opportunity: "Сам спрос на партию материалами подтверждается, если объём экспорта растёт.",
    action: "Зафиксировать цену и валюту ближайших партий, пока объём и курс не сложены в одну выручку.",
  },
  "Внешняя торговля:export": {
    risk: "Экспортный сюжет может касаться другого товара, чем поставка компании.",
    opportunity: "",
    action: "",
  },
  "Внешняя торговля:grain": {
    risk: "Рост чужого экспорта не равен выручке этой компании.",
    opportunity: "Если материал прямо про зерно, объём партий это подтверждённый спрос.",
    action: "",
  },
  "Санкции и дипломатия:export": {
    risk: "Курс и цена не открывают маршрут, пока санкции в материалах остаются условием.",
    opportunity: "",
    action: "Не менять маршруты отгрузки из-за одного разговора о нормализации.",
  },
  "Долг и облигации:debt": {
    risk: "Рынок долга и ставка компании это разные вещи.",
    opportunity: "",
    action: "",
  },
};

function bankQuotes(cards, topic) {
  const lines = [];
  for (const card of cards) {
    const quote = pointedQuote(card, topic);
    if (!quote) continue;
    lines.push({ role: quote.role, text: quote.text, source: card.title, href: hrefOf(card) });
  }
  return lines.slice(0, 2);
}

function pointedQuote(card, topic) {
  const needles = {
    "Ключевая ставка": /пауз|14,0|ставк/i,
    "Инфляция": /инфляц/i,
    "Спрос": /спрос|потреблен/i,
    "Рынок труда": /зарплат/i,
    "Сталь": /прокат|стал/i,
    "Валютные курсы": /рубл|доллар|курс/i,
    "Сырьё": /нефт|brent/i,
  };
  const needle = needles[topic];
  if (!needle) return null;
  const position = bestQuote(card.bank_position, needle, "Позиция банка");
  if (position) return position;
  return bestQuote(card.facts, needle, "Факт из обзора банка");
}

function bestQuote(list, needle, role) {
  let best = null;
  for (const item of list || []) {
    const text = cleanQuote(item.text);
    if (!text || !needle.test(text)) continue;
    let score = Math.min(text.length, 180);
    if (/^[А-ЯЁA-Z0-9«"]/.test(text)) score += 25;
    if (/охлажд|пауз|14[,.]0|устойчив/i.test(text)) score += 40;
    if (!best || score > best.score) best = { role, text, score };
  }
  return best ? { role: best.role, text: best.text } : null;
}

function trace(client, topic, picked, bank, features) {
  return [
    { name: "Признаки клиента", text: features.length ? features.map((item) => item.text).join("; ") : "подходящего признака нет" },
    { name: "Отбор материалов", text: `${picked.length} по теме «${topic}» и соседним темам, которые есть у компании` },
    { name: "Обзоры банка", text: bank.length ? bank.map((item) => item.source).join("; ") : "по этой подборке прямой формулировки нет" },
    { name: "Разделение", text: "позиция банка и вывод сервиса показаны отдельно, в один абзац не склеены" },
  ];
}

function rankEvent(client, topic, picked, bank, fits, extras) {
  let rank = picked.length + (bank.length ? 2 : 0) + (fits ? 2 : 0) + extras.length;
  if (topic === "Ключевая ставка" && client.features.some((feature) => feature.id === "debt")) rank += 6;
  if (topic === "Сырьё" && client.features.some((feature) => feature.id === "commodity")) rank += 4;
  if (topic === "Сталь" || topic === "Зерно" || topic === "Спрос") rank += 4;
  return rank;
}

function matching(cards, topic, client) {
  let list = cards.filter((card) => topicsOf(card).includes(topic) && !isNoise(card));
  const product = client ? productTest(client) : null;
  if (product && ["Внешняя торговля", "Сырьё", "Зерно", "Сталь"].includes(topic)) {
    list = list.filter((card) => product.test(card.title || ""));
  }
  return list;
}

function productTest(client) {
  if (client.features.some((feature) => feature.id === "commodity")) return /нефт|brent/i;
  if (client.features.some((feature) => feature.id === "steel")) return /стал|прокат/i;
  if (client.features.some((feature) => feature.id === "grain")) return /зерн/i;
  return null;
}

function titleHits(card, topic) {
  const test = TOPIC_TESTS.find(([label]) => label === topic);
  return Boolean(test && test[1].test(card.title || ""));
}

function topicsOf(card) {
  const fromTitle = TOPIC_TESTS.filter(([, test]) => test.test(card.title || "")).map(([label]) => label);
  const known = BANK_TOPICS[card.title] || [];
  return [...new Set([...fromTitle, ...known])];
}

function primaryTopic(card, fallback) {
  const topics = topicsOf(card);
  return topics.find((topic) => topic !== fallback) || topics[0] || "";
}

function clientTopics(client) {
  const topics = [];
  for (const feature of client.features) {
    for (const topic of FEATURE_TOPICS[feature.id] || []) {
      if (!topics.includes(topic)) topics.push(topic);
    }
  }
  return topics;
}

function topicFromQuestion(question) {
  const text = String(question || "").toLowerCase();
  const pairs = [
    [/ставк|кредит/, "Ключевая ставка"],
    [/доллар|рубл|курс/, "Валютные курсы"],
    [/нефт|brent|сырь/, "Сырьё"],
    [/инфляц|ценник/, "Инфляция"],
    [/спрос|продаж|закуп/, "Спрос"],
    [/зарплат/, "Рынок труда"],
    [/стал|прокат/, "Сталь"],
    [/зерн/, "Зерно"],
    [/санкц/, "Санкции и дипломатия"],
    [/экспорт|спг/, "Внешняя торговля"],
    [/фрахт|логист/, "Логистика и поставки"],
  ];
  const found = pairs.find(([test]) => test.test(text));
  return found ? found[1] : "";
}

function eventTitle(topic, client) {
  const titles = {
    "Ключевая ставка": "Ставка и стоимость денег компании",
    "Валютные курсы": "Курс и рублёвая выручка",
    "Сырьё": "Цена сырья и выручка",
    "Инфляция": "Инфляция и ценник",
    "Спрос": "Спрос и закупка",
    "Рынок труда": "Зарплаты и расход",
    "Сталь": "Цена проката и контракты",
    "Зерно": "Зерно и валюта партии",
    "Внешняя торговля": "Экспорт и поставки компании",
    "Санкции и дипломатия": "Санкции и маршруты",
    "Логистика и поставки": "Доставка и маржа",
    "Долг и облигации": "Долг и нагрузка компании",
  };
  return titles[topic] || `${topic} для «${client.name}»`;
}

function presentCard(card) {
  return {
    label: card.source_type === "alfa_research" ? "Обзор банка" : "Новость",
    source: sourceName(card),
    title: shortTitle(card.title),
    href: hrefOf(card),
    kind: card.source_type === "alfa_research" ? "Обзор банка" : "Новость",
    gloss: card.source_type === "alfa_research" ? "Внутренний материал банка по теме." : "Внешнее сообщение. Это ещё не вывод для компании.",
  };
}

function presentSource(card) {
  return {
    kind: card.source_type === "alfa_research" ? "Обзор банка" : "Новость",
    name: sourceName(card),
    title: shortTitle(card.title),
    href: hrefOf(card),
  };
}

function isNoise(card) {
  if (card.source_type === "alfa_research") return false;
  return /пособи|tesla|cybercab|школьник|винодел|vietnam|вьетнам/i.test(card.title || "");
}

function cleanQuote(raw) {
  const text = String(raw || "")
    .replace(/\s+/g, " ")
    .replace(/rir/gi, "г/г")
    .replace(/%\s*гг(?![а-яё])/gi, "% г/г")
    .replace(/^[а-яё]{3,14}:\s+/i, "")
    .replace(/^[^а-яёa-z0-9«"]+/i, "")
    .replace(/[,;:\s]+$/g, "")
    .trim();
  const cyr = (text.match(/[а-яё]/gi) || []).length;
  const lat = (text.match(/[a-z]/gi) || []).length;
  if (text.length < 28 || cyr < 18 || lat > 8) return "";
  if (/источник|vicmown|www\.|http|11126/i.test(text)) return "";
  return text;
}

function blob(card) {
  return [card.title, card.text, ...(card.facts || []).map((item) => item.text), ...(card.bank_position || []).map((item) => item.text)].join("\n");
}

function unique(cards) {
  const seen = new Set();
  return cards.filter((card) => {
    if (!card || seen.has(card.id)) return false;
    seen.add(card.id);
    return true;
  });
}

function byDate(left, right) {
  return String(right.published_at || "").localeCompare(String(left.published_at || ""));
}

function sourceName(card) {
  if (card.source_type === "alfa_research") return "Аналитика банка";
  const name = String(card.source_name || "").trim();
  if (/^https?:\/\//i.test(name)) {
    try { return new URL(name).hostname.replace(/^www\./, ""); } catch (error) { return name; }
  }
  return name || "Новость";
}

function shortTitle(title) {
  let text = String(title || "").trim();
  for (let pass = 0; pass < 2; pass += 1) {
    const cut = text.lastIndexOf(" - ");
    if (cut === -1) break;
    const tail = text.slice(cut + 3).trim();
    if (!tail || tail.length > 40 || tail.split(/\s+/).length > 4) break;
    text = text.slice(0, cut).trim();
  }
  return text;
}

function hrefOf(card) {
  const anchor = card.anchor || {};
  if (anchor.url) return anchor.url;
  if (anchor.path) return `../${anchor.path}`;
  return "";
}

const Scenario = { clients: CLIENTS, storiesFor, eventsFor, answerQuestion };
globalThis.Scenario = Scenario;
export { Scenario };
