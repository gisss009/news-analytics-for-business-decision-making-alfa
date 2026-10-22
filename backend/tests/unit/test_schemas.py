import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.agents.schemas import (BankViewBlock, Blocks, Claim, ClaimsBlock, EventRef, Insight, Plan, Relevance,
                                Verification, export_json_schemas, ref_kind)


def claim(**kw):
    base = {"id": "c1", "text": "Ставка сохранена на уровне 14%", "label": "fact", "refs": ["news:n001#f1"]}
    base.update(kw)
    return Claim(**base)


def test_valid_claims_accepted():
    claim()
    claim(label="bank_analytics", refs=["doc:key_rate_11sep2026#p1"])
    claim(label="model_inference", refs=["feat:has_loans", "news:n001#f1"])
    claim(label="model_inference", refs=["exp:rate_sensitivity", "thesis:key_rate_11sep2026#t1"])


@pytest.mark.parametrize("kw", [
    {"refs": []},                                              # без ссылок
    {"label": "opinion"},                                      # неизвестная метка
    {"label": "fact", "refs": ["feat:has_loans"]},             # факт без источника
    {"label": "bank_analytics", "refs": ["news:n001#f1"]},     # позиция банка без документа банка
    {"label": "model_inference", "refs": ["news:n001#f1"]},    # вывод без признака компании
    {"label": "model_inference", "refs": ["feat:has_loans"]},  # вывод без источника
    {"refs": ["http://example.com"]},                          # неизвестный формат ссылки
])
def test_invalid_claims_rejected(kw):
    with pytest.raises(ValidationError):
        claim(**kw)


def test_bank_block_accepts_only_bank_claims():
    with pytest.raises(ValidationError):
        BankViewBlock(claims=[claim()])


def test_ref_kinds():
    assert ref_kind("news:n001") == "news" and ref_kind("news:n001#f2") == "news_fact"
    assert ref_kind("doc:gold_aug2026#p7") == "doc" and ref_kind("cp:U_S1001") == "cp" and ref_kind("x") is None


def test_insight_roundtrip_and_basis():
    blocks = Blocks(what_happened=ClaimsBlock(claims=[claim()]),
                    why_it_matters=ClaimsBlock(claims=[claim(id="c2", label="model_inference",
                                                             refs=["feat:has_loans", "news:n001#f1"])])).collect_basis()
    assert blocks.basis.refs == ["news:n001#f1", "feat:has_loans"]
    ins = Insight(run_id="r1", company_id="U_S0001", role="cfo",
                  event=EventRef(id="ev_n001", title="t", published_at=datetime(2026, 9, 11, tzinfo=timezone.utc)),
                  relevance=Relevance(score=0.8), blocks=blocks, verification=Verification(passed=True),
                  prompt_version="interp-v1")
    assert Insight.model_validate_json(ins.model_dump_json()) == ins


def test_plan_limits():
    with pytest.raises(ValidationError):
        Plan(steps=[])


def test_json_schema_export(tmp_path):
    paths = export_json_schemas(tmp_path)
    data = json.loads((tmp_path / "Claim.schema.json").read_text(encoding="utf-8"))
    assert len(paths) == 6 and "label" in data["properties"]
