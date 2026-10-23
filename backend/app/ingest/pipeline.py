"""Одна команда для всего ingest: аналитика банка, новости, дедупликация, классификация, факты, индекс.

  python -m app.ingest.pipeline                                  # офлайн: фикстуры новостей, аналитика auto
  python -m app.ingest.pipeline --news live                      # живые новости pyfinews вместо фикстур
  python -m app.ingest.pipeline --analytics pdf                  # тезисы только из OCR (нужен python scripts/ocr.py)

Аналитика: fixtures — ручные тезисы data/analytics/fixtures/theses.json (фрагменты страниц);
pdf — полный OCR-текст страниц и тезисы правилами (analytics_chunk); auto — pdf, если у всех PDF в
data/analytics есть актуальный кэш OCR, иначе fixtures. Ручные тезисы в режиме pdf не смешиваются:
они остаются режимом fixtures и эталоном для analytics_chunk.evaluate().
Новости: fixtures — офлайн-набор; live — вымышленные новости убираются, свежие берутся из pyfinews;
если живых не набралось (нет сети), остаётся офлайн-набор. Повторный запуск идемпотентен.
"""
import argparse
import sys

from app.core.logging import get_logger
from app.ingest import analytics_chunk, classify, dedupe, facts, fetch, index, offline
from app.ingest.analytics_parse import parse_all
from app.ingest.sources.fixtures import FixtureSource
from app.ingest.sources.pyfinews_source import PyfinewsSource

log = get_logger("ingest.pipeline")

NEWS_MODES = ("fixtures", "live")
ANALYTICS_MODES = ("auto", "fixtures", "pdf")


class PipelineError(RuntimeError):
    """Выбранный режим нельзя выполнить (например, --analytics pdf без кэша OCR)."""


def live_source() -> PyfinewsSource:
    return PyfinewsSource()


def load_analytics(mode: str = "auto") -> dict:
    if mode not in ANALYTICS_MODES:
        raise PipelineError(f"неизвестный режим аналитики: {mode}")
    if mode != "fixtures":
        docs, skipped = parse_all()
        if docs and not skipped:
            return analytics_chunk.load_from_pdfs(docs) | {"analytics_skipped": 0}
        reason = "; ".join(skipped) or "в data/analytics нет PDF"
        if mode == "pdf":
            raise PipelineError(f"режим pdf недоступен: {reason}")
        log.info("analytics_fallback_fixtures", extra={"reason": reason[:300]})
        return offline.load_analytics() | {"analytics_source": "fixtures", "analytics_skipped": len(skipped)}
    return offline.load_analytics() | {"analytics_source": "fixtures", "analytics_skipped": 0}


def load_news(mode: str = "fixtures", include_holdout: bool = True) -> dict:
    if mode not in NEWS_MODES:
        raise PipelineError(f"неизвестный режим новостей: {mode}")
    live_errors = 0
    if mode == "live":
        stats = offline.load_news([live_source()])
        if stats["news"] > 0:
            removed = fetch.remove_synthetic()
            return stats | {"news_source": "live", "news_synthetic_removed": removed}
        live_errors = stats["news_errors"]
        log.warning("live_news_empty_fallback_fixtures", extra={"errors": live_errors})
    stats = offline.load_news([FixtureSource(include_holdout=include_holdout)])
    stats["news_errors"] += live_errors
    return stats | {"news_source": "fixtures", "news_synthetic_removed": 0}


def run(news: str = "fixtures", analytics: str = "auto", include_holdout: bool = True) -> dict:
    stats = load_analytics(analytics)
    stats.update(load_news(news, include_holdout))
    stats.update(dedupe.run())
    stats.update(classify.run())
    stats.update(facts.run())
    stats.update(index.build())
    return stats


def summary(stats: dict) -> str:
    return "\n".join([
        f"аналитика: {stats['analytics_source']}, документов {stats['analytics_docs']}, тезисов {stats['theses']}"
        + (f" (без кэша OCR: {stats['analytics_skipped']})" if stats.get("analytics_skipped") else ""),
        f"новости: {stats['news_source']}, загружено {stats['news']}, дублей {stats['news_duplicates']}, "
        f"ошибок {stats['news_errors']}",
        "итог: " + ", ".join(f"{k}={v}" for k, v in stats.items()),
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--news", choices=NEWS_MODES, default="fixtures")
    ap.add_argument("--analytics", choices=ANALYTICS_MODES, default="auto")
    a = ap.parse_args(argv)
    try:
        stats = run(a.news, a.analytics)
    except PipelineError as e:
        print(f"[pipeline] {e}", file=sys.stderr)
        return 2
    print(summary(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
