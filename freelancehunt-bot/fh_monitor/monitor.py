"""One monitoring pass: fetch new projects, filter, notify, remember."""

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .filters import ProjectFilter
from .freelancehunt import FreelancehuntClient, Project
from .net import HttpError
from .storage import SeenStorage
from .telegram import TelegramClient, TelegramError, format_message

log = logging.getLogger(__name__)


@dataclass
class CheckResult:
    fetched: int = 0
    sent: List[int] = field(default_factory=list)
    skipped: int = 0
    failed: List[int] = field(default_factory=list)


class Monitor:
    def __init__(
        self,
        freelancehunt: FreelancehuntClient,
        project_filter: ProjectFilter,
        storage: SeenStorage,
        telegram: Optional[TelegramClient],
        max_pages: int,
        first_run_limit: int,
        skill_ids: List[int] = (),
        output: Callable[[str], None] = print,
    ):
        self._fh = freelancehunt
        self._filter = project_filter
        self._storage = storage
        self._telegram = telegram  # None = dry run: print instead of sending
        self._max_pages = max_pages
        self._first_run_limit = first_run_limit
        self._skill_ids = list(skill_ids)
        self._output = output

    def check(self) -> CheckResult:
        result = CheckResult()
        first_run = not self._storage.initialized
        try:
            projects = self._fh.fetch_new_projects(
                self._storage.is_seen,
                max_pages=1 if first_run else self._max_pages,
                skill_ids=self._skill_ids,
            )
        except HttpError as e:
            log.error("Freelancehunt API недоступний: %s. Наступна спроба за розкладом.", e)
            return result

        result.fetched = len(projects)
        matched = []
        processed = []
        for project in projects:
            decision = self._filter.decide(project)
            if decision.send:
                matched.append((project, decision.reason))
            else:
                result.skipped += 1
                processed.append(project.id)
                log.debug("#%d пропущено: %s", project.id, decision.reason)

        if first_run and len(matched) > self._first_run_limit:
            # Do not flood the chat with the whole feed on the very first start.
            log.info("Перший запуск: надсилаю %d найновіших із %d", self._first_run_limit, len(matched))
            processed += [p.id for p, _ in matched[self._first_run_limit:]]
            matched = matched[: self._first_run_limit]

        # Oldest first, so the chat reads in publication order.
        for project, reason in reversed(matched):
            if self._notify(project, reason):
                result.sent.append(project.id)
                processed.append(project.id)
            else:
                result.failed.append(project.id)

        self._storage.mark(processed)
        log.info(
            "Перевірка: нових %d, надіслано %d, відфільтровано %d, помилок %d",
            result.fetched, len(result.sent), result.skipped, len(result.failed),
        )
        return result

    def _notify(self, project: Project, reason: str) -> bool:
        text = format_message(project, reason)
        if self._telegram is None:
            self._output(f"[dry-run] #{project.id}\n{text}\n")
            return True
        try:
            self._telegram.send(text)
            log.info("#%d надіслано: %s", project.id, project.title)
            return True
        except TelegramError as e:
            if e.permanent:
                log.error("#%d не надіслано (%s), більше не пробуватиму.", project.id, e)
                return True
            log.warning("#%d не надіслано (%s), повторю на наступній перевірці.", project.id, e)
            return False
