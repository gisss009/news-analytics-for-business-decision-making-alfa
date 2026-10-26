# Сторонние компоненты и лицензии

Проект «Сводка для решений» (кейс Альфа-Банка, Альфа Хак 2026) использует перечисленные ниже библиотеки,
шрифты, образы и данные. Код самого проекта написан командой. Готовые агентные и мультиагентные
фреймворки (LangChain, LangGraph, CrewAI, AutoGen и подобные) не используются.

Версии взяты из lock-файлов: `backend/requirements.lock`, `requirements.txt`, `frontend/package-lock.json`,
`web/package-lock.json`. Лицензии сверены по метаданным установленных пакетов (26.10.2026).
Полные тексты лицензий лежат в дистрибутивах пакетов и по ссылкам на проекты.

## Модели

Используются только модели из условий кейса, через общий ключ организаторов по OpenAI-совместимому API.
Веса моделей в репозиторий не входят и не распространяются.

| Модель | Шаги |
|---|---|
| Gemma 4 26B A4B | классификация, факты, краткий профиль, проверка релевантности |
| GLM-5.3-Flash | текст разбора события |
| Qwen3.6 35B A3B | план, позиция банка, проверка разбора, уточняющие вопросы |
| DeepSeek-V4.1-Flash, Qwen3-VL-30B-A3B-Instruct, Kimi-K2.6 | разрешены в белом списке клиента |

## Backend (`backend/`)

Прямые зависимости (`backend/requirements.txt`):

| Пакет | Версия | Лицензия | Проект |
|---|---|---|---|
| FastAPI | 0.161.0 | MIT | https://github.com/fastapi/fastapi |
| Uvicorn | 0.54.0 | BSD-3-Clause | https://github.com/encode/uvicorn |
| Pydantic | 2.14.1 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.16.1 | MIT | https://github.com/pydantic/pydantic-settings |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| PyYAML | 6.0.3 | MIT | https://pyyaml.org/ |
| snowballstemmer | 3.1.1 | BSD-3-Clause | https://github.com/snowballstem/snowball |
| pyfinews | 0.1.7 | MIT | https://github.com/sam-333/pyfinews |
| pytest (тесты) | 9.1.1 | MIT | https://pytest.org |
| gdown (скачивание данных кейса) | 6.4.2 | MIT | https://github.com/wkentaro/gdown |
| pypdf (инструменты разработки) | 6.21.2 | BSD-3-Clause | https://github.com/py-pdf/pypdf |

Транзитивные зависимости (`backend/requirements.lock`):

| Лицензия | Пакеты |
|---|---|
| MIT | annotated-doc, annotated-types, anyio, beautifulsoup4, charset-normalizer, filelock, googlenewsdecoder, h11, h2, hpack, httptools, hyperframe, iniconfig, pluggy, pydantic-core, pytz, selectolax, six, socksio, soupsieve, typing-inspection, tzlocal, urllib3, watchfiles |
| BSD-2-Clause / BSD-3-Clause | babel, click, colorama, dateparser, feedparser, httpcore, idna, jusText, lxml, lxml-html-clean, Pygments, PySocks, python-dotenv, starlette, websockets |
| Apache-2.0 | courlan, htmldate, opentelemetry-api, requests, trafilatura, tzdata |
| Apache-2.0 AND CNRI-Python | regex |
| Apache-2.0 OR BSD-2-Clause | packaging |
| Apache-2.0 / BSD (двойная) | python-dateutil |
| MPL-2.0 | certifi |
| MPL-2.0 AND MIT | tqdm |
| MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later (используется на условиях MPL-1.1) | tld |
| PSF-2.0 | feedparser-sgmllib, typing-extensions |

Хранилище и поиск — SQLite с модулем FTS5 из стандартной библиотеки Python (public domain).

## Парсер (`parser/`)

| Пакет | Версия | Лицензия | Проект |
|---|---|---|---|
| pyfinews | 0.1.7 | MIT | https://github.com/sam-333/pyfinews |
| PyMuPDF | 1.27.2.3 | AGPL-3.0 или коммерческая лицензия Artifex | https://pymupdf.readthedocs.io/ |

Транзитивные зависимости парсера — те же пакеты, что у backend (pyfinews, trafilatura, httpx, lxml и др.),
лицензии указаны выше.

**PyMuPDF используется на условиях GNU AGPL-3.0** (https://www.gnu.org/licenses/agpl-3.0.html), коммерческая
лицензия Artifex не приобреталась. Решение команды: оставить PyMuPDF в парсере и выполнять условия AGPL-3.0.
Он нужен только парсеру (`parser/`) для чтения PDF и вызова OCR и не входит в backend: OCR backend работает
на pypdfium2 и Tesseract (см. ниже). PyMuPDF не включён в репозиторий, а ставится из PyPI по `requirements.txt`.
Исходный код парсера полностью открыт в этом репозитории; при распространении парсера или при его работе как
сетевого сервиса пользователям предоставляется доступ к этому исходному коду, как требует AGPL-3.0.

Если Tesseract установлен на машину, парсер вызывает его через PyMuPDF: Tesseract OCR — Apache-2.0.

## OCR в Docker (`docker/ocr/`)

| Компонент | Лицензия | Проект |
|---|---|---|
| Tesseract OCR и языковые данные `rus`, `eng` (пакеты Debian) | Apache-2.0 | https://github.com/tesseract-ocr/tesseract |
| pypdfium2 4.30.0 (включает PDFium) | Apache-2.0 / BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2 |
| Pillow 11.0.0 | MIT-CMU (HPND) | https://python-pillow.org |
| Базовый образ `python:3.12-slim` | PSF-2.0 (Python), лицензии пакетов Debian | https://hub.docker.com/_/python |

## Интерфейсы (`web/`, `frontend/`)

Зависимости, попадающие в сборку:

| Пакет | Версия | Где | Лицензия | Проект |
|---|---|---|---|---|
| React, React DOM | 19.3.1 | `web/` | MIT | https://react.dev |
| React, React DOM | 18.3.1 | `frontend/` | MIT | https://react.dev |
| React Router (react-router-dom, @remix-run/router) | 6.30.6 / 1.23.4 | `frontend/` | MIT | https://reactrouter.com |
| openapi-fetch | 0.13.8 | `frontend/` | MIT | https://openapi-ts.dev |
| scheduler, loose-envify, js-tokens, openapi-typescript-helpers | — | `frontend/`, `web/` | MIT | npm |

Инструменты сборки и проверки (в сборку не попадают): Vite 6.4.5 и 5.4.21 (MIT), @vitejs/plugin-react (MIT),
TypeScript 5.8.3 и 5.6.3 (Apache-2.0), ESLint 9 и typescript-eslint (MIT), openapi-typescript (MIT)
и их зависимости. Лицензии всех npm-пакетов по lock-файлам:

| Лицензия | `web/` | `frontend/` |
|---|---|---|
| MIT | 188 | 134 |
| ISC | 11 | 7 |
| Apache-2.0 | 15 | 3 |
| BSD-2-Clause / BSD-3-Clause | 8 | 1 |
| BlueOak-1.0.0 | 1 | — |
| CC-BY-4.0 (caniuse-lite, данные о браузерах) | 1 | 1 |
| Python-2.0 (argparse) | 1 | 1 |
| MIT OR CC0-1.0 | — | 1 |

Node.js запускается в контейнере `node:24-slim` (Node.js — MIT; https://hub.docker.com/_/node) и в проект не входит.

## Макет (`maket/`)

Библиотеки лежат в `maket/vendor/` без изменений:

| Библиотека | Версия | Лицензия | Проект |
|---|---|---|---|
| Alpine.js | 3.17.4 | MIT | https://github.com/alpinejs/alpine |
| GSAP и ScrollTrigger | 3.12.7 | GreenSock Standard «No Charge» License | https://gsap.com/standard-license |
| Lenis | 1.1.20 | MIT | https://github.com/darkroomengineering/lenis |

## Шрифты

| Шрифт | Где | Лицензия | Проект |
|---|---|---|---|
| Onest | `frontend/src/assets/fonts`, `maket/assets/fonts`, `web/` | SIL Open Font License 1.1 | https://fonts.google.com/specimen/Onest |
| PT Serif (ParaType) | `maket/assets/fonts` | SIL Open Font License 1.1 | https://fonts.google.com/specimen/PT+Serif |

## Данные и материалы

| Источник | Как используется | Условия |
|---|---|---|
| Синтетические компании, физлица и платежи (`data/synthetic`) | демо и тесты | созданы командой по схеме датасета кейса; реальных данных клиентов нет |
| Офлайн-набор новостей (`data/fixtures/news`) | демо без сети | вымышленные тексты, написаны командой |
| Датасет кейса (`data/raw`) | локально, по ссылке организаторов | в репозиторий не входит |
| Аналитика Альфа-Банка, 9 PDF (`data/analytics`) | тезисы и цитаты со ссылкой на страницу | материалы банка из кейса; в репозиторий не входят, скачиваются по ссылке организаторов. Ручные тезисы `data/analytics/fixtures/theses.json` — короткие цитаты с указанием документа и страницы |
| Деловые новости (Google News RSS через pyfinews, тексты статей — trafilatura) | заголовки, короткие факты и цитаты со ссылкой на первоисточник | права на тексты принадлежат издателям; новости загружаются при запуске и в репозиторий не входят (`data/out`, `data/runtime` в `.gitignore`) |
