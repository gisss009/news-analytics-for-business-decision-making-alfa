import json
import logging

from app.core.db import connect
from app.core.logging import JsonFormatter, log_tool_call, mask, run_id_var


def test_tool_call_written_with_masked_args():
    token = run_id_var.set("r_test")
    try:
        log_tool_call("ranker", "profile_get", {"company_id": "U_0000123456789", "api_key": "sk-secret", "q": "ставка"},
                      result={"ok": 1}, tokens=7)
    finally:
        run_id_var.reset(token)
    row = connect().execute("SELECT * FROM tool_calls").fetchone()
    args = json.loads(row["args_masked"])
    assert row["run_id"] == "r_test" and row["tokens"] == 7 and row["ok"] == 1 and row["result_hash"]
    assert args["api_key"] == "***"
    assert args["company_id"] == "U_0***89"
    assert args["q"] == "ставка"


def test_mask_keeps_short_and_text_values():
    assert mask("U_01") == "U_01"
    assert mask("ключевая ставка 14%") == "ключевая ставка 14%"
    assert mask({"nested": [{"token": "x"}]}) == {"nested": [{"token": "***"}]}


def test_json_log_format():
    rec = logging.LogRecord("app.x", logging.INFO, "", 0, "hello", None, None)
    rec.tool = "news_search"
    data = json.loads(JsonFormatter().format(rec))
    assert data["msg"] == "hello" and data["tool"] == "news_search" and data["level"] == "INFO"
