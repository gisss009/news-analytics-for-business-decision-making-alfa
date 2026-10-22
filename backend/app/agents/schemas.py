"""Типизированные контракты между шагами агентного ядра (docs/ARCHITECTURE.md §5).

Главное правило: у каждого утверждения (Claim) есть label и refs. Вывод без источника не создаётся:
- fact — ссылка на факт новости (news:<id>#f<n>) или страницу аналитики (doc:<id>#p<n>);
- bank_analytics — ссылка на страницу аналитики банка (doc:<id>#p<n>) или тезис (thesis:<id>);
- model_inference — хотя бы один признак компании (feat:* / exp:* / cp:*) и хотя бы один источник (news:* / doc:* / thesis:*).
Экспорт JSON Schema: python -m app.agents.schemas --export
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Label = Literal["fact", "bank_analytics", "model_inference"]
LABEL_TITLES = {"fact": "Факт", "bank_analytics": "Аналитика Альфа-Банка", "model_inference": "Вывод ИИ"}

REF_PATTERNS = {
    "news": re.compile(r"^news:[A-Za-z0-9_\-]+$"),
    "news_fact": re.compile(r"^news:[A-Za-z0-9_\-]+#f\d+$"),
    "doc": re.compile(r"^doc:[A-Za-z0-9_\-]+#p\d+$"),
    "thesis": re.compile(r"^thesis:[A-Za-z0-9_\-]+#t\d+$"),
    "feat": re.compile(r"^feat:[a-z0-9_]+$"),
    "exp": re.compile(r"^exp:[a-z0-9_]+$"),
    "cp": re.compile(r"^cp:[A-Za-z0-9_\-]+$"),
}
SOURCE_KINDS = {"news", "news_fact", "doc", "thesis"}
FEATURE_KINDS = {"feat", "exp", "cp"}


def ref_kind(ref: str) -> str | None:
    for kind, pat in REF_PATTERNS.items():
        if pat.match(ref):
            return kind
    return None


def label_problem(label: str, refs: list[str]) -> str | None:
    """Почему набор ссылок не подходит к метке (None — подходит)."""
    if not refs:
        return "нет ссылок на источники"
    kinds = [ref_kind(r) for r in refs]
    if None in kinds:
        return f"неизвестный формат ссылки: {refs[kinds.index(None)]}"
    ks = set(kinds)
    if label == "fact" and not ks & {"news_fact", "doc"}:
        return "у факта нет ссылки на факт новости или страницу документа"
    if label == "bank_analytics" and not ks & {"doc", "thesis"}:
        return "у позиции банка нет ссылки на документ аналитики"
    if label == "model_inference" and not (ks & FEATURE_KINDS and ks & SOURCE_KINDS):
        return "у вывода ИИ должны быть ссылки и на признак компании, и на источник"
    return None


class Claim(BaseModel):
    id: str
    text: str = Field(min_length=3)
    label: Label
    refs: list[str]
    confidence: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="after")
    def _refs_match_label(self):
        problem = label_problem(self.label, self.refs)
        if problem:
            raise ValueError(f"claim {self.id}: {problem}")
        return self


class Fact(BaseModel):
    fact_id: str
    values: list[str] = []
    date: str | None = None
    quote: str
    modality: Literal["stated", "expected", "speculation"]


class SourceLink(BaseModel):
    name: str
    url: str
    ref: str


class EventRef(BaseModel):
    id: str
    title: str
    published_at: datetime
    topic: str | None = None
    sources: list[SourceLink] = []


class ClientFeature(BaseModel):
    name: str
    value: object = None
    source: str


class Relevance(BaseModel):
    score: float = Field(ge=0, le=1)
    reasons: list[str] = []
    matched_features: list[str] = []
    components: dict[str, float] = {}


class ClaimsBlock(BaseModel):
    claims: list[Claim] = []


class ConsequencesBlock(BaseModel):
    risks: list[Claim] = []
    opportunities: list[Claim] = []


class BankViewBlock(BaseModel):
    claims: list[Claim] = []
    absent: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def _bank_claims_only(self):
        for c in self.claims:
            if c.label != "bank_analytics":
                raise ValueError(f"в блоке позиции банка допустимы только claims с label=bank_analytics ({c.id})")
        return self


class BasisBlock(BaseModel):
    refs: list[str] = []


class Blocks(BaseModel):
    what_happened: ClaimsBlock = ClaimsBlock()
    why_it_matters: ClaimsBlock = ClaimsBlock()
    consequences: ConsequencesBlock = ConsequencesBlock()
    actions: ClaimsBlock = ClaimsBlock()
    bank_view: BankViewBlock = BankViewBlock()
    basis: BasisBlock = BasisBlock()

    def all_claims(self) -> list[tuple[str, Claim]]:
        out = [("what_happened", c) for c in self.what_happened.claims]
        out += [("why_it_matters", c) for c in self.why_it_matters.claims]
        out += [("consequences.risks", c) for c in self.consequences.risks]
        out += [("consequences.opportunities", c) for c in self.consequences.opportunities]
        out += [("actions", c) for c in self.actions.claims]
        out += [("bank_view", c) for c in self.bank_view.claims]
        return out

    def collect_basis(self) -> "Blocks":
        refs = []
        for _, c in self.all_claims():
            refs += [r for r in c.refs if r not in refs]
        self.basis = BasisBlock(refs=refs)
        return self


IssueType = Literal["missing_ref", "bad_ref", "number_mismatch", "contradiction", "empty_block", "unsupported"]


class Issue(BaseModel):
    claim_id: str | None = None
    block: str | None = None
    type: IssueType
    detail: str


class Verification(BaseModel):
    passed: bool
    iterations: int = 1
    issues: list[Issue] = []


class PlanStep(BaseModel):
    tool: str
    args: dict = {}
    purpose: str = ""


class Plan(BaseModel):
    steps: list[PlanStep] = Field(min_length=1)
    questions: list[str] = []
    source: Literal["llm", "default"] = "default"

    @field_validator("steps")
    @classmethod
    def _max_steps(cls, v):
        if len(v) > 8:
            raise ValueError("слишком длинный план (больше 8 шагов)")
        return v


class TraceStep(BaseModel):
    step: str
    status: Literal["ok", "fallback", "error", "skipped"] = "ok"
    started_at: datetime
    duration_ms: int = 0
    detail: dict = {}


InsightStatus = Literal["DONE", "DONE_WITH_WARNINGS", "FALLBACK"]


class Insight(BaseModel):
    run_id: str
    event: EventRef
    company_id: str
    role: str
    client_features: list[ClientFeature] = []
    relevance: Relevance
    blocks: Blocks
    verification: Verification
    warnings: list[str] = []
    status: InsightStatus = "DONE"
    prompt_version: str


EXPORTED = {"Claim": Claim, "Insight": Insight, "Plan": Plan, "Verification": Verification, "TraceStep": TraceStep,
            "Fact": Fact}


def export_json_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, model in EXPORTED.items():
        p = out_dir / f"{name}.schema.json"
        p.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(p)
    return paths


if __name__ == "__main__" and "--export" in sys.argv:
    from app.core.config import REPO_ROOT
    for p in export_json_schemas(REPO_ROOT / "docs" / "schemas"):
        print("записано:", p)
