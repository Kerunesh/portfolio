import io
import json
import logging
import os
import tempfile
import unittest
import urllib.error

from bot import RedactSecrets
from fh_monitor.config import ConfigError, load_config
from fh_monitor.filters import ProjectFilter
from fh_monitor.freelancehunt import FreelancehuntClient, parse_project
from fh_monitor.monitor import Monitor
from fh_monitor.net import HttpError, request_json
from fh_monitor.storage import SeenStorage
from fh_monitor.telegram import TelegramClient, TelegramError, format_message


def api_item(project_id, name="Налаштувати Google Ads", description="", personal=False, budget=1000):
    return {
        "id": project_id,
        "type": "project",
        "attributes": {
            "name": name,
            "description": description,
            "skills": [{"id": 1, "name": "Контекстна реклама"}],
            "budget": {"amount": budget, "currency": "UAH"} if budget else None,
            "bid_count": 4,
            "is_personal": personal,
            "employer": {"login": "client1", "first_name": "Іван", "last_name": "Петренко"},
            "published_at": "2026-10-01T12:00:00+03:00",
        },
        "links": {"self": {"web": f"https://freelancehunt.com/project/x/{project_id}.html"}},
    }


def project(project_id=1, **kwargs):
    return parse_project(api_item(project_id, **kwargs))


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.filter = ProjectFilter(
            keywords=["бот", "seo", "google ads", "парсер"],
            stop_words=["дизайн", "казино"],
            skip_employers=["Bad Client"],
        )

    def check(self, title, description=""):
        return self.filter.decide(project(name=title, description=description, budget=None)).send

    def test_keyword_matches_word_start_with_endings(self):
        self.assertTrue(self.check("Потрібен телеграм-бот"))
        self.assertTrue(self.check("Доробка бота для магазину"))
        self.assertTrue(self.check("Написати парсера цін"))

    def test_keyword_inside_another_word_is_ignored(self):
        self.assertFalse(self.check("Робота на складі"))
        self.assertFalse(self.check("Monteseo studio"))

    def test_keyword_found_in_skills(self):
        p = parse_project(api_item(1, name="Задача", description=""))
        self.assertFalse(self.filter.decide(p).send)
        custom = ProjectFilter(keywords=["контекстна реклама"])
        self.assertTrue(custom.decide(p).send)

    def test_stop_word_wins_over_keyword(self):
        decision = self.filter.decide(project(name="SEO для казино"))
        self.assertFalse(decision.send)
        self.assertIn("казино", decision.reason)

    def test_personal_and_blacklisted_employers_are_skipped(self):
        self.assertFalse(self.filter.decide(project(name="SEO аудит", personal=True)).send)
        bad = api_item(2, name="SEO аудит")
        bad["attributes"]["employer"] = {"login": "x", "first_name": "Bad", "last_name": "Client"}
        self.assertFalse(self.filter.decide(parse_project(bad)).send)


class ParseAndFormatTest(unittest.TestCase):
    def test_parse_real_api_shape(self):
        p = project(1656479)
        self.assertEqual("https://freelancehunt.com/project/x/1656479.html", p.url)
        self.assertEqual("1000 UAH", p.budget)
        self.assertEqual("Іван Петренко", p.employer)

    def test_missing_budget(self):
        self.assertIsNone(project(budget=None).budget)
        self.assertIn("не вказано", format_message(project(budget=None)))

    def test_html_is_escaped(self):
        text = format_message(project(name='Сайт <script> & "лапки"', description="a < b"))
        self.assertIn("Сайт &lt;script&gt; &amp; &quot;лапки&quot;", text)
        self.assertIn("a &lt; b", text)
        self.assertNotIn("<script>", text)

    def test_long_description_is_shortened(self):
        text = format_message(project(description="слово " * 200))
        self.assertLess(len(text), 700)
        self.assertIn("…", text)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def http_error(status, body, headers=None):
    return urllib.error.HTTPError(
        "https://api.telegram.org/botSECRET/sendMessage", status, "err", headers or {},
        io.BytesIO(json.dumps(body).encode()),
    )


class NetTest(unittest.TestCase):
    def test_retries_429_using_retry_after_and_hides_url(self):
        calls, sleeps = [], []
        responses = [
            http_error(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 7}}),
            FakeResponse(b'{"ok": true}'),
        ]

        def opener(req, timeout):
            calls.append(req.full_url)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        body = request_json("https://api.telegram.org/botSECRET/sendMessage", method="POST", payload={},
                            opener=opener, sleep=sleeps.append)
        self.assertEqual({"ok": True}, body)
        self.assertEqual([7.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_client_error_is_not_retried_and_message_has_no_token(self):
        attempts = []

        def opener(req, timeout):
            attempts.append(1)
            raise http_error(401, {"ok": False, "description": "Unauthorized"})

        with self.assertRaises(HttpError) as ctx:
            request_json("https://api.telegram.org/botSECRET/sendMessage", opener=opener, sleep=lambda s: None)
        self.assertEqual(1, len(attempts))
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_network_errors_give_up_after_attempts(self):
        def opener(req, timeout):
            raise urllib.error.URLError(ConnectionResetError())

        with self.assertRaises(HttpError):
            request_json("https://example.com", opener=opener, sleep=lambda s: None, attempts=3)


class StorageTest(unittest.TestCase):
    def test_ids_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data", "state.json")
            storage = SeenStorage(path)
            self.assertFalse(storage.initialized)
            storage.mark([1, 2])
            restarted = SeenStorage(path)
            self.assertTrue(restarted.initialized)
            self.assertTrue(restarted.is_seen(2))
            self.assertFalse(restarted.is_seen(3))

    def test_memory_storage_writes_nothing(self):
        storage = SeenStorage(None)
        storage.mark([1])
        self.assertTrue(storage.is_seen(1))


class FakeFreelancehunt:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def __call__(self, url, headers=None, **kwargs):
        page = int(url.split("%5Bnumber%5D=")[1].split("&")[0])
        self.requested.append(page)
        data = self.pages[page - 1] if page <= len(self.pages) else []
        return {"data": data, "links": {"next": "x"} if page < len(self.pages) else {}}


class FakeTelegram:
    def __init__(self, fail_ids=(), permanent=False):
        self.sent = []
        self.fail_ids = set(fail_ids)
        self.permanent = permanent

    def send(self, text):
        for project_id in self.fail_ids:
            if f"/{project_id}.html" in text:
                raise TelegramError("Telegram: HTTP 502", permanent=self.permanent)
        self.sent.append(text)


class MonitorTest(unittest.TestCase):
    def make(self, pages, storage, telegram, first_run_limit=3):
        api = FakeFreelancehunt(pages)
        monitor = Monitor(
            freelancehunt=FreelancehuntClient(request=api),
            project_filter=ProjectFilter(keywords=["seo"], stop_words=["казино"]),
            storage=storage,
            telegram=telegram,
            max_pages=3,
            first_run_limit=first_run_limit,
        )
        return monitor, api

    def seeded_storage(self, ids=(1,)):
        storage = SeenStorage(None)
        storage.mark(ids)
        return storage

    def test_walks_pages_until_known_project_and_sends_oldest_first(self):
        storage = self.seeded_storage([100])
        pages = [
            [api_item(i, name=f"SEO {i}") for i in range(130, 120, -1)],
            [api_item(i, name=f"SEO {i}") for i in range(120, 110, -1)],
            [api_item(i, name=f"SEO {i}") for i in range(110, 99, -1)],
        ]
        telegram = FakeTelegram()
        monitor, api = self.make(pages, storage, telegram)

        result = monitor.check()

        self.assertEqual([1, 2, 3], api.requested)
        self.assertEqual(30, len(result.sent))
        self.assertIn("/101.html", telegram.sent[0])
        self.assertIn("/130.html", telegram.sent[-1])

    def test_no_duplicates_on_next_check(self):
        storage = self.seeded_storage()
        pages = [[api_item(5, name="SEO аудит"), api_item(4, name="Логотип"), api_item(1)]]
        telegram = FakeTelegram()
        monitor, _ = self.make(pages, storage, telegram)

        first = monitor.check()
        second = monitor.check()

        self.assertEqual([5], first.sent)
        self.assertEqual(1, first.skipped)
        self.assertEqual(0, second.fetched)
        self.assertEqual(1, len(telegram.sent))

    def test_temporary_telegram_error_is_retried_next_check(self):
        storage = self.seeded_storage()
        pages = [[api_item(5, name="SEO аудит"), api_item(1)]]
        telegram = FakeTelegram(fail_ids=[5])
        monitor, _ = self.make(pages, storage, telegram)

        self.assertEqual([5], monitor.check().failed)
        telegram.fail_ids.clear()
        self.assertEqual([5], monitor.check().sent)

    def test_permanent_telegram_error_is_not_retried_forever(self):
        storage = self.seeded_storage()
        pages = [[api_item(5, name="SEO аудит"), api_item(1)]]
        monitor, _ = self.make(pages, storage, FakeTelegram(fail_ids=[5], permanent=True))

        monitor.check()
        self.assertTrue(storage.is_seen(5))

    def test_first_run_sends_only_newest_few_and_remembers_the_rest(self):
        storage = SeenStorage(None)
        pages = [[api_item(i, name=f"SEO {i}") for i in range(20, 10, -1)]]
        telegram = FakeTelegram()
        monitor, api = self.make(pages, storage, telegram, first_run_limit=3)

        result = monitor.check()

        self.assertEqual([1], api.requested)
        self.assertEqual([18, 19, 20], result.sent)
        self.assertTrue(all(storage.is_seen(i) for i in range(11, 21)))

    def test_api_failure_does_not_crash_or_mark_anything(self):
        storage = self.seeded_storage()

        def broken(url, headers=None, **kwargs):
            raise HttpError(503, "Service Unavailable")

        monitor = Monitor(FreelancehuntClient(request=broken), ProjectFilter(["seo"]), storage,
                          FakeTelegram(), max_pages=3, first_run_limit=3)
        self.assertEqual(0, monitor.check().fetched)

    def test_dry_run_prints_instead_of_sending(self):
        printed = []
        storage = self.seeded_storage()
        monitor = Monitor(FreelancehuntClient(request=FakeFreelancehunt([[api_item(5, name="SEO"), api_item(1)]])),
                          ProjectFilter(["seo"]), storage, None, 3, 3, output=printed.append)
        monitor.check()
        self.assertEqual(1, len(printed))
        self.assertIn("[dry-run] #5", printed[0])


class ConfigTest(unittest.TestCase):
    def write(self, data):
        handle, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(os.remove, path)
        return path

    def test_example_config_with_placeholders_is_rejected_for_real_run(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example = os.path.join(root, "config.example.json")
        with self.assertRaises(ConfigError):
            load_config(example)
        config = load_config(example, require_telegram=False)
        self.assertIsNone(config.freelancehunt_token)

    def test_environment_overrides_tokens(self):
        path = self.write({"telegram_bot_token": "YOUR_X", "telegram_chat_id": "YOUR_Y", "keywords": ["seo"]})
        os.environ.update({"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "42"})
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")])
        config = load_config(path)
        self.assertEqual("123:abc", config.telegram_bot_token)
        self.assertEqual("42", config.telegram_chat_id)

    def test_unknown_key_is_reported(self):
        path = self.write({"telegram_bot_token": "1", "telegram_chat_id": "2", "keywords": ["seo"], "kewords": []})
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("kewords", str(ctx.exception))


class RedactionTest(unittest.TestCase):
    def test_tokens_are_removed_from_log_lines(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(RedactSecrets(["123:SECRET"]))
        logger = logging.getLogger("redaction-test")
        logger.addHandler(handler)
        logger.propagate = False
        logger.error("url https://api.telegram.org/bot%s/sendMessage", "123:SECRET")
        self.assertNotIn("SECRET", stream.getvalue())
        self.assertIn("bot***", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
