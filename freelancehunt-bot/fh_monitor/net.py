"""Small JSON-over-HTTP helper on the standard library with retries.

Errors never contain request URLs, so tokens embedded in URLs (Telegram) cannot leak into logs.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

log = logging.getLogger(__name__)

USER_AGENT = "fh-telegram-monitor/1.0"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class HttpError(Exception):
    def __init__(self, status: Optional[int], message: str, body: Optional[dict] = None):
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status
        self.body = body or {}


def _retry_after_seconds(status: int, headers, body: dict) -> Optional[float]:
    if status != 429:
        return None
    telegram_wait = (body.get("parameters") or {}).get("retry_after")
    if telegram_wait:
        return float(telegram_wait)
    header = headers.get("Retry-After") if headers else None
    if header and header.isdigit():
        return float(header)
    return None


def request_json(
    url: str,
    method: str = "GET",
    payload: Optional[dict] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15,
    attempts: int = 3,
    backoff: float = 2,
    sleep: Callable[[float], None] = time.sleep,
    opener: Callable = urllib.request.urlopen,
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    all_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    all_headers.update(headers or {})

    last_error = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, data=data, headers=all_headers, method=method)
        try:
            with opener(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = _read_json_body(e)
            description = body.get("description") or (body.get("error") or {}).get("title") or e.reason
            last_error = HttpError(e.code, str(description), body)
            if e.code not in RETRYABLE_STATUSES:
                raise last_error
            wait = _retry_after_seconds(e.code, e.headers, body) or backoff * attempt
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            reason = getattr(e, "reason", e)
            last_error = HttpError(None, f"мережева помилка: {type(reason).__name__}")
            wait = backoff * attempt
        except json.JSONDecodeError:
            raise HttpError(None, "відповідь не є JSON")

        if attempt < attempts:
            log.warning("%s, повтор %d/%d через %.0f с", last_error, attempt + 1, attempts, wait)
            sleep(wait)
    raise last_error


def _read_json_body(error: urllib.error.HTTPError) -> dict:
    try:
        return json.loads(error.read().decode("utf-8"))
    except Exception:
        return {}
