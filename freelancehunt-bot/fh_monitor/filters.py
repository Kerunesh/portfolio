"""Keyword / stop-word matching on whole word starts.

"бот" must match "бот", "бота", "ботів", but not "робота"; "seo" must not match "videos".
"""

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .freelancehunt import Project


def _compile(words: Iterable[str]) -> Optional[re.Pattern]:
    words = [w.strip().lower() for w in words if w and w.strip()]
    if not words:
        return None
    alternatives = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})", re.IGNORECASE)


@dataclass
class Decision:
    send: bool
    reason: str


class ProjectFilter:
    def __init__(
        self,
        keywords: List[str],
        stop_words: List[str] = (),
        skip_employers: List[str] = (),
        skip_personal: bool = True,
    ):
        self._keywords = _compile(keywords)
        self._stop_words = _compile(stop_words)
        self._skip_employers = {e.strip().lower() for e in skip_employers if e.strip()}
        self._skip_personal = skip_personal

    def decide(self, project: Project) -> Decision:
        if self._skip_personal and project.is_personal:
            return Decision(False, "персональний проєкт")
        if {project.employer.lower(), project.employer_login.lower()} & self._skip_employers:
            return Decision(False, f"замовник у чорному списку: {project.employer}")

        text = " ".join([project.title, project.description, " ".join(project.skills)])
        if self._stop_words:
            stop = self._stop_words.search(text)
            if stop:
                return Decision(False, f"стоп-слово «{stop.group(0)}»")
        keyword = self._keywords.search(text) if self._keywords else None
        if not keyword:
            return Decision(False, "немає ключових слів")
        return Decision(True, f"ключове слово «{keyword.group(0)}»")
