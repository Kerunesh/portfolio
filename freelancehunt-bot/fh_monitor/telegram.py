"""Telegram Bot API: formatting and sending project notifications."""

import html
from typing import Callable

from .freelancehunt import Project
from .net import HttpError, request_json

DESCRIPTION_PREVIEW = 300


class TelegramError(Exception):
    def __init__(self, message: str, permanent: bool):
        super().__init__(message)
        self.permanent = permanent


def format_message(project: Project, reason: str = "") -> str:
    e = html.escape
    description = " ".join(project.description.split())
    if len(description) > DESCRIPTION_PREVIEW:
        description = description[:DESCRIPTION_PREVIEW].rsplit(" ", 1)[0] + "…"

    lines = [f'🎯 <b><a href="{e(project.url, quote=True)}">{e(project.title)}</a></b>', ""]
    lines.append(f"💰 <b>Бюджет:</b> {e(project.budget) if project.budget else 'не вказано'}")
    lines.append(f"📩 <b>Ставок:</b> {project.bid_count}")
    if project.employer:
        lines.append(f"👤 <b>Замовник:</b> {e(project.employer)}")
    if project.skills:
        lines.append(f"🏷 {e(', '.join(project.skills))}")
    if description:
        lines += ["", e(description)]
    if reason:
        lines += ["", f"<i>{e(reason)}</i>"]
    return "\n".join(lines)


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, request: Callable = request_json):
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._request = request

    def send(self, text: str) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            body = self._request(self._url, method="POST", payload=payload)
        except HttpError as e:
            # 4xx except 429 (bad chat id, revoked token, broken markup) will not fix itself on retry.
            permanent = e.status is not None and 400 <= e.status < 500 and e.status != 429
            raise TelegramError(f"Telegram: {e}", permanent=permanent)
        if not body.get("ok"):
            raise TelegramError(f"Telegram: {body.get('description', 'невідома помилка')}", permanent=True)
