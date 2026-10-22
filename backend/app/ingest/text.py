"""Общая нормализация русского текста: токены, основы слов (Snowball), числа."""
import re
from functools import lru_cache

import snowballstemmer

_stemmer = snowballstemmer.stemmer("russian")
_WORD = re.compile(r"[a-zа-яё]+", re.I)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

STOPWORDS = frozenset("""
а без более бы был была были было быть в вам вас весь во вот все всего всех вы где да даже для до его ее если
есть еще же за здесь и из или им их к как ко когда кто ли либо мне может мы на над надо наш не него нее нет ни
них но ну о об однако он она они оно от очень по под при с со так также такой там те тем то того тоже той только
том ты у уже хотя чего чей чем что чтобы чье чья эта эти это этот я год года году годом году млрд млн тыс руб
рублей процент процентов который которые которая которое сообщил сообщили сообщает считают отмечают
""".split())


@lru_cache(maxsize=50_000)
def stem(word: str) -> str:
    return _stemmer.stemWord(word.lower().replace("ё", "е"))


def words(text: str) -> list[str]:
    return [w.lower().replace("ё", "е") for w in _WORD.findall(text)]


def stems(text: str, drop_stopwords: bool = True) -> list[str]:
    return [stem(w) for w in words(text) if len(w) > 2 and not (drop_stopwords and w in STOPWORDS)]


def numbers(text: str) -> set[str]:
    """Числа в нормализованном виде: '14,0' и '14.0' и '14' совпадают."""
    out = set()
    for n in _NUMBER.findall(text):
        v = n.replace(",", ".")
        if "." in v:
            v = v.rstrip("0").rstrip(".")
        out.add(v)
    return out
