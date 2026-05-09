from __future__ import annotations

import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


SC_TOKEN_FILE = str(Path.home() / ".oternos_soundcloud.json")
_SSL = ssl.create_default_context()


def _sc_fetch_client_id() -> str | None:
    """Fetch SoundCloud's rotating web client_id without importing desktop UI code."""
    try:
        req = urllib.request.Request(
            "https://soundcloud.com",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=12, context=_SSL) as response:
            html = response.read().decode("utf-8", errors="replace")
        scripts = re.findall(
            r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"',
            html,
        )
        for script_url in reversed(scripts):
            try:
                jreq = urllib.request.Request(script_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(jreq, timeout=10, context=_SSL) as js_response:
                    js = js_response.read().decode("utf-8", errors="replace")
                match = re.search(r'client_id\s*:\s*"([a-zA-Z0-9]{20,})"', js)
                if match:
                    return match.group(1)
            except Exception:
                continue
    except Exception:
        return None
    return None


class SoundCloudAPI:
    BASE = "https://api-v2.soundcloud.com"
    _cached_cid: str | None = None

    def __init__(self):
        self.oauth_token = None
        self._load_token()
        if not SoundCloudAPI._cached_cid:
            SoundCloudAPI._cached_cid = _sc_fetch_client_id() or ""
        self.client_id = SoundCloudAPI._cached_cid

    def _load_token(self) -> None:
        try:
            data = json.loads(Path(SC_TOKEN_FILE).read_text(encoding="utf-8"))
            self.oauth_token = data.get("oauth_token")
        except Exception:
            pass

    def refresh_client_id(self) -> bool:
        SoundCloudAPI._cached_cid = _sc_fetch_client_id() or ""
        self.client_id = SoundCloudAPI._cached_cid
        return bool(self.client_id)

    @property
    def ready(self) -> bool:
        return bool(self.client_id)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json; charset=utf-8",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if self.oauth_token:
            headers["Authorization"] = f"OAuth {self.oauth_token}"
        return headers

    def _get(self, endpoint: str, params: dict | None = None):
        if not self.client_id:
            return None
        query = dict(params or {})
        query["client_id"] = self.client_id
        url = f"{self.BASE}{endpoint}?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=10, context=_SSL) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                SoundCloudAPI._cached_cid = None
            return None
        except Exception:
            return None

    def search(self, q: str, limit: int = 40, offset: int = 0) -> list[dict]:
        data = self._get("/search/tracks", {"q": q, "limit": limit, "offset": offset})
        return self._rank_results((data or {}).get("collection", []), q)

    def _rank_results(self, items, query: str) -> list[dict]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return list(items or [])
        ranked = []
        for index, item in enumerate(items or []):
            if not isinstance(item, dict):
                continue
            ranked.append((self._relevance_score(item, query_tokens, query), index, item))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [item for _score, _index, item in ranked]

    def _tokens(self, value: str) -> list[str]:
        return [part for part in re.split(r"[^a-z0-9]+", str(value or "").lower()) if part]

    def _relevance_score(self, item: dict, query_tokens: list[str], raw_query: str) -> float:
        title = str(item.get("title") or "").lower()
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        artist = str(user.get("username") or item.get("user_name") or "").lower()
        genre = str(item.get("genre") or "").lower()
        tag_list = str(item.get("tag_list") or "").lower()
        haystack = " ".join((title, artist, genre, tag_list))
        hay_tokens = set(self._tokens(haystack))
        query = str(raw_query or "").strip().lower()
        score = 0.0
        if query and title == query:
            score += 120.0
        if query and artist == query:
            score += 80.0
        if query and title.startswith(query):
            score += 55.0
        if query and artist.startswith(query):
            score += 42.0
        for token in query_tokens:
            if token in hay_tokens:
                score += 18.0
            elif token and token in haystack:
                score += 7.0
        try:
            score += min(int(item.get("likes_count") or item.get("favoritings_count") or 0), 250000) / 25000.0
        except Exception:
            pass
        try:
            score += min(int(item.get("playback_count") or 0), 5000000) / 1000000.0
        except Exception:
            pass
        return score
