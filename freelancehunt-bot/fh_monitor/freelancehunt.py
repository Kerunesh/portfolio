"""Freelancehunt API v2: list of open projects."""

import urllib.parse
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from .net import request_json

API_URL = "https://api.freelancehunt.com/v2/projects"


@dataclass(frozen=True)
class Project:
    id: int
    title: str
    description: str
    url: str
    budget: Optional[str]
    bid_count: int
    skills: List[str]
    employer: str
    employer_login: str
    is_personal: bool
    published_at: str


def parse_project(item: dict) -> Project:
    attrs = item.get("attributes") or {}
    employer = attrs.get("employer") or {}
    budget = attrs.get("budget") or {}
    full_name = " ".join(filter(None, [employer.get("first_name"), employer.get("last_name")]))
    return Project(
        id=int(item["id"]),
        title=(attrs.get("name") or "").strip() or "Без назви",
        description=(attrs.get("description") or "").strip(),
        url=((item.get("links") or {}).get("self") or {}).get("web") or "",
        budget=f"{budget['amount']} {budget.get('currency', '')}".strip() if budget.get("amount") else None,
        bid_count=int(attrs.get("bid_count") or 0),
        skills=[s.get("name", "") for s in attrs.get("skills") or [] if s.get("name")],
        employer=full_name or employer.get("login", ""),
        employer_login=employer.get("login", ""),
        is_personal=bool(attrs.get("is_personal")),
        published_at=attrs.get("published_at") or "",
    )


class FreelancehuntClient:
    def __init__(self, token: Optional[str] = None, request: Callable = request_json):
        self._token = token
        self._request = request

    def page_url(self, page: int, skill_ids: Iterable[int] = ()) -> str:
        params = {"page[number]": page}
        skill_ids = list(skill_ids)
        if skill_ids:
            params["filter[skill_id]"] = ",".join(str(i) for i in skill_ids)
        return f"{API_URL}?{urllib.parse.urlencode(params)}"

    def fetch_new_projects(
        self,
        is_seen: Callable[[int], bool],
        max_pages: int,
        skill_ids: Iterable[int] = (),
    ) -> List[Project]:
        """Newest projects first; stops at the first already processed project or after max_pages.

        The API returns only 10 projects per page, so one page is not enough when many
        projects were published between two checks.
        """
        headers = {"Accept-Language": "uk"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        result = []
        for page in range(1, max_pages + 1):
            body = self._request(self.page_url(page, skill_ids), headers=headers)
            items = body.get("data") or []
            for item in items:
                project = parse_project(item)
                if is_seen(project.id):
                    return result
                result.append(project)
            if not items or not (body.get("links") or {}).get("next"):
                break
        return result
