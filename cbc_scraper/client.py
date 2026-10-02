"""Read-only site client; browser request text is parsed, never executed."""

import os
import re
import shlex
from http.cookies import SimpleCookie
from pathlib import Path

import requests

BASE_URL = "https://nsa-codebreaker.org"


class ScraperError(Exception):
    pass


def request_headers(text):
    text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    if "PASTE_COOKIE_VALUE_HERE" in text or not text:
        raise ScraperError(
            "Login template is not filled in. Replace PASTE_COOKIE_VALUE_HERE in edit_this_request.txt with your browser Cookie header, then save and retry."
        )
    if text.lower().startswith("cookie:"):
        return {"cookie": text.split(":", 1)[1].strip()}
    tokens = shlex.split(text.replace("\\\n", " "))
    headers = {}
    for token_index, token in enumerate(tokens[:-1]):
        if token in ("-H", "--header"):
            key, separator, value = tokens[token_index + 1].partition(":")
            if separator and key.lower() in ("cookie", "x-csrftoken", "x-csrf-token"):
                headers[key.lower()] = value.strip()
        elif token in ("-b", "--cookie"):
            headers["cookie"] = tokens[token_index + 1]
    if not headers:
        raise ScraperError("Request file contains no supported cookie or CSRF header.")
    return headers


class Client:
    def __init__(self, request_file=None):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "CBC-Scraper/0.2", "X-Requested-With": "XMLHttpRequest"}
        )
        headers = (
            request_headers(Path(request_file).read_text()) if request_file else {}
        )
        cookie = headers.pop("cookie", os.environ.get("CBC_COOKIE", ""))
        cookies = SimpleCookie()
        cookies.load(cookie)
        if cookie and not cookies:
            raise ScraperError(
                "Could not parse Cookie header; supply name=value pairs."
            )
        for name, morsel in cookies.items():
            self.session.cookies.set(
                name, morsel.value, domain="nsa-codebreaker.org", path="/"
            )
        self.session.headers.update(headers)
        if os.environ.get("CBC_CSRF_TOKEN"):
            self.session.headers["X-CSRFToken"] = os.environ["CBC_CSRF_TOKEN"]

    def fetch(self, path, data=None):
        try:
            response = self.session.request(
                "POST" if data is not None else "GET",
                BASE_URL + path,
                data=data,
                timeout=(10, 45),
                allow_redirects=False,
            )
            if response.status_code in (301, 302, 303, 307, 308, 401, 403):
                raise ScraperError(
                    "The website did not accept your saved login (it may have expired). Run cbc-scraper setup to save a fresh browser request, then retry."
                )
            response.raise_for_status()
            return response
        except requests.RequestException:
            raise ScraperError(
                "Site request failed (network error or HTTP failure); cached data was preserved."
            ) from None

    def bootstrap(self):
        html = self.fetch("/leaderboard").text
        patterns = [
            r"""setRequestHeader\(["']X-CSRFToken["']\s*,\s*["']([^"']+)""",
            r"""name=["']csrf_token["'][^>]*value=["']([^"']+)""",
            r"""name=["']csrf-token["'][^>]*content=["']([^"']+)""",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                self.session.headers["X-CSRFToken"] = match.group(1)
                break
        self.session.headers["Referer"] = BASE_URL + "/leaderboard"
        return html

    def json(self, path, data=None):
        try:
            value = self.fetch(path, data).json()
        except ValueError:
            raise ScraperError(
                "Expected JSON but received a page; refresh authentication or check the site API."
            ) from None
        if not isinstance(value, dict):
            raise ScraperError("Unexpected API response shape.")
        return value

    def board(self, board_column, board_row, year=None):
        path = (
            f"/data/histboard/{year}/{board_column}/{board_row}"
            if year
            else f"/data/board/{board_column}/{board_row}"
        )
        rows, start = [], 0
        while True:
            result = self.json(path, {"draw": 1, "start": start, "length": -1})
            batch = result.get("data")
            if not isinstance(batch, list):
                raise ScraperError("Leaderboard response has no data array.")
            total = result.get("recordsFiltered", result.get("recordsTotal"))
            if total is None:
                return rows + batch  # Client-side tables return everything.
            rows.extend(batch)
            if len(rows) >= int(total):
                return rows
            if not batch or start > 100000:
                raise ScraperError(
                    "Leaderboard pagination stopped before all rows were received."
                )
            start += len(batch)

    def submissions(self):
        rows = []
        for page in range(1, 10001):
            result = self.json("/my-submissions" + (f"/{page}" if page > 1 else "/"))
            batch = result.get("submissions")
            if not isinstance(batch, list):
                raise ScraperError("Submission response has no submissions array.")
            rows.extend(batch)
            if not result.get("next"):
                if "total_count" in result and len(rows) != int(result["total_count"]):
                    raise ScraperError(
                        "Submission count changed or pagination is incomplete; retry."
                    )
                return rows
            if not batch:
                break
        raise ScraperError("Submission pagination did not finish.")
