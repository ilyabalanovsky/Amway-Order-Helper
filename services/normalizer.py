from __future__ import annotations

import re


SPACE_RE = re.compile(r"\s+")
PATRONYMIC_RE = re.compile(
    r"(?i)^(?:[А-ЯЁ][а-яё]+(?:вич|вна|ична|оглы|кызы))$"
)


def normalize_name(value: str) -> str:
    cleaned = SPACE_RE.sub(" ", value.replace("ё", "е").replace("Ё", "Е").strip())
    return cleaned.casefold()


def clean_name(value: str) -> str:
    return SPACE_RE.sub(" ", value.strip())


def strip_patronymic(value: str) -> str:
    tokens = clean_name(value).split(" ")
    if len(tokens) < 3:
        return " ".join(tokens)
    filtered: list[str] = []
    removed = False
    for index, token in enumerate(tokens):
        if 0 < index < len(tokens) - 1 and not removed and PATRONYMIC_RE.match(token):
            removed = True
            continue
        filtered.append(token)
    return " ".join(filtered)
