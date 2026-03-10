from __future__ import annotations

import argparse
import json
import threading
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
KST = timezone(timedelta(hours=9), name="KST")
CACHE_TTL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

MARKETS = [
    {
        "id": "kospi",
        "label": "KOSPI",
        "symbol": "^KS11",
        "group": "국내 지수",
        "decimals": 2,
        "kind": "equity",
    },
    {
        "id": "kosdaq",
        "label": "KOSDAQ",
        "symbol": "^KQ11",
        "group": "국내 지수",
        "decimals": 2,
        "kind": "equity",
    },
    {
        "id": "sp500",
        "label": "S&P 500",
        "symbol": "^GSPC",
        "group": "해외 지수",
        "decimals": 2,
        "kind": "equity",
    },
    {
        "id": "nasdaq",
        "label": "NASDAQ",
        "symbol": "^IXIC",
        "group": "해외 지수",
        "decimals": 2,
        "kind": "equity",
    },
    {
        "id": "dow",
        "label": "DOW",
        "symbol": "^DJI",
        "group": "해외 지수",
        "decimals": 2,
        "kind": "equity",
    },
    {
        "id": "usdkrw",
        "label": "USD/KRW",
        "symbol": "KRW=X",
        "group": "거시 자산",
        "decimals": 2,
        "kind": "fx",
    },
    {
        "id": "us10y",
        "label": "미국 10Y",
        "symbol": "^TNX",
        "group": "거시 자산",
        "decimals": 3,
        "kind": "yield",
    },
    {
        "id": "wti",
        "label": "WTI",
        "symbol": "CL=F",
        "group": "거시 자산",
        "decimals": 2,
        "kind": "commodity",
    },
    {
        "id": "gold",
        "label": "Gold",
        "symbol": "GC=F",
        "group": "거시 자산",
        "decimals": 2,
        "kind": "commodity",
    },
    {
        "id": "bitcoin",
        "label": "Bitcoin",
        "symbol": "BTC-USD",
        "group": "거시 자산",
        "decimals": 0,
        "kind": "crypto",
    },
]

PRIMARY_CHART_IDS = ["kospi", "kosdaq", "sp500", "nasdaq"]
CARD_GROUPS = ["국내 지수", "해외 지수", "거시 자산"]


class DashboardCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._expires_at = 0.0

    def get(self) -> dict[str, Any] | None:
        now = datetime.now().timestamp()
        with self._lock:
            if self._payload and now < self._expires_at:
                return self._payload
        return None

    def set(self, payload: dict[str, Any]) -> None:
        now = datetime.now().timestamp()
        with self._lock:
            self._payload = payload
            self._expires_at = now + CACHE_TTL_SECONDS


DASHBOARD_CACHE = DashboardCache()


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def last_number(values: list[Any] | None) -> float | None:
    if not values:
        return None
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def format_clock(timestamp: int | None) -> str | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=KST).strftime("%Y-%m-%d %H:%M KST")


def trend_tone(change_percent: float | None) -> str:
    if change_percent is None:
        return "flat"
    if change_percent > 0.15:
        return "up"
    if change_percent < -0.15:
        return "down"
    return "flat"


def direction_text(change_percent: float | None) -> str:
    tone = trend_tone(change_percent)
    if tone == "up":
        return "상승"
    if tone == "down":
        return "하락"
    return "보합"


def signed_text(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}{suffix}"


def to_points(timestamps: list[int] | None, closes: list[Any] | None) -> list[list[float]]:
    if not timestamps or not closes:
        return []

    points: list[list[float]] = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        points.append([timestamp * 1000, round(float(close), 6)])
    return points


def fetch_market_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    symbol = config["symbol"]
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(symbol, safe='')}?interval=5m&range=1d"
    )
    payload = fetch_json(url)
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    indicators = result["indicators"]["quote"][0]
    closes = indicators.get("close") or []
    timestamps = result.get("timestamp") or []

    last_price = meta.get("regularMarketPrice")
    if last_price is None:
        last_price = last_number(closes)
    else:
        last_price = float(last_price)

    prev_close = meta.get("chartPreviousClose")
    if prev_close is None:
        prev_close = meta.get("previousClose")
    if prev_close is not None:
        prev_close = float(prev_close)

    day_change = None
    change_percent = None
    if last_price is not None and prev_close:
        day_change = last_price - prev_close
        change_percent = (day_change / prev_close) * 100

    series = to_points(timestamps, closes)
    market_time = meta.get("regularMarketTime")
    market_state = meta.get("marketState") or "UNKNOWN"

    return {
        "id": config["id"],
        "label": config["label"],
        "symbol": symbol,
        "group": config["group"],
        "kind": config["kind"],
        "decimals": config["decimals"],
        "price": round(last_price, 6) if last_price is not None else None,
        "previousClose": round(prev_close, 6) if prev_close is not None else None,
        "change": round(day_change, 6) if day_change is not None else None,
        "changePercent": round(change_percent, 4) if change_percent is not None else None,
        "tone": trend_tone(change_percent),
        "direction": direction_text(change_percent),
        "series": series,
        "marketState": market_state,
        "marketTime": format_clock(market_time),
        "marketTimestamp": market_time,
    }


def fetch_headlines() -> list[dict[str, str | None]]:
    query = quote("한국 증시 OR 미국 증시 OR 환율 OR 금리 when:1d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    headlines: list[dict[str, str | None]] = []

    for item in items[:8]:
        raw_title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip() or None
        title = raw_title
        if source and raw_title.endswith(f" - {source}"):
            title = raw_title[: -(len(source) + 3)].strip()

        headlines.append(
            {
                "title": title,
                "source": source,
                "link": (item.findtext("link") or "").strip() or None,
                "publishedAt": (item.findtext("pubDate") or "").strip() or None,
            }
        )
    return headlines


def build_summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    card_map = {card["id"]: card for card in cards}

    equities = [
        card_map[key]["changePercent"]
        for key in ("kospi", "kosdaq", "sp500", "nasdaq")
        if card_map.get(key, {}).get("changePercent") is not None
    ]
    risk_assets = [
        card_map[key]["changePercent"]
        for key in ("wti", "bitcoin")
        if card_map.get(key, {}).get("changePercent") is not None
    ]
    defensive_assets = [
        card_map[key]["changePercent"]
        for key in ("usdkrw", "gold")
        if card_map.get(key, {}).get("changePercent") is not None
    ]

    risk_score = 0.0
    if equities:
        risk_score += mean(equities)
    if risk_assets:
        risk_score += mean(risk_assets) * 0.4
    if defensive_assets:
        risk_score -= mean(defensive_assets) * 0.5

    if risk_score > 0.6:
        signal = {
            "label": "Risk-On",
            "tone": "up",
            "message": "주식과 위험자산 강세가 우세합니다.",
        }
    elif risk_score < -0.6:
        signal = {
            "label": "Defensive",
            "tone": "down",
            "message": "환율·안전자산 쏠림이 강해 방어적 흐름입니다.",
        }
    else:
        signal = {
            "label": "Mixed",
            "tone": "flat",
            "message": "국내외 자산이 같은 방향으로 움직이지 않는 혼조장입니다.",
        }

    kospi = card_map.get("kospi")
    kosdaq = card_map.get("kosdaq")
    sp500 = card_map.get("sp500")
    nasdaq = card_map.get("nasdaq")
    usdkrw = card_map.get("usdkrw")
    us10y = card_map.get("us10y")

    checkpoints = []
    if kospi:
        checkpoints.append(
            f"KOSPI {signed_text(kospi['changePercent'], 2, '%')} {kospi['direction']}"
        )
    if kosdaq:
        checkpoints.append(
            f"KOSDAQ {signed_text(kosdaq['changePercent'], 2, '%')} {kosdaq['direction']}"
        )
    if sp500 and nasdaq:
        checkpoints.append(
            f"미국 증시 {sp500['direction']} / 나스닥 {signed_text(nasdaq['changePercent'], 2, '%')}"
        )
    if usdkrw:
        checkpoints.append(
            f"원달러 {signed_text(usdkrw['changePercent'], 2, '%')} ({signed_text(usdkrw['change'], 2)})"
        )
    if us10y:
        checkpoints.append(
            f"미 10년물 {signed_text(us10y['change'], 3)}p ({signed_text(us10y['changePercent'], 2, '%')})"
        )

    overview = []
    if kospi and kosdaq:
        overview.append(
            f"국내장은 KOSPI {direction_text(kospi['changePercent'])}, "
            f"KOSDAQ {direction_text(kosdaq['changePercent'])} 흐름입니다."
        )
    if sp500 and nasdaq:
        overview.append(
            f"해외는 S&P 500 {signed_text(sp500['changePercent'], 2, '%')}, "
            f"NASDAQ {signed_text(nasdaq['changePercent'], 2, '%')}로 확인됩니다."
        )
    if usdkrw and us10y:
        overview.append(
            f"매크로 변수는 USD/KRW {signed_text(usdkrw['changePercent'], 2, '%')}, "
            f"미 10년물 {signed_text(us10y['changePercent'], 2, '%')}입니다."
        )

    movers_pool = [card for card in cards if card["id"] != "us10y" and card["changePercent"] is not None]
    leaders = sorted(movers_pool, key=lambda card: card["changePercent"], reverse=True)[:3]
    laggards = sorted(movers_pool, key=lambda card: card["changePercent"])[:3]

    return {
        "signal": signal,
        "overview": overview,
        "checkpoints": checkpoints,
        "leaders": [
            {
                "label": card["label"],
                "changePercent": card["changePercent"],
                "direction": card["direction"],
            }
            for card in leaders
        ],
        "laggards": [
            {
                "label": card["label"],
                "changePercent": card["changePercent"],
                "direction": card["direction"],
            }
            for card in laggards
        ],
    }


def assemble_dashboard() -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=min(8, len(MARKETS) + 1)) as executor:
        futures = {executor.submit(fetch_market_snapshot, config): config for config in MARKETS}
        headlines_future = executor.submit(fetch_headlines)

        for future in as_completed(futures):
            config = futures[future]
            try:
                cards.append(future.result())
            except (HTTPError, URLError, KeyError, IndexError, ValueError) as exc:
                errors.append(f"{config['label']}: {exc}")

        headlines: list[dict[str, str | None]]
        try:
            headlines = headlines_future.result()
        except (HTTPError, URLError, ET.ParseError) as exc:
            headlines = []
            errors.append(f"뉴스: {exc}")

    cards.sort(key=lambda card: [item["id"] for item in MARKETS].index(card["id"]))
    summary = build_summary(cards)
    main_charts = [card for card in cards if card["id"] in PRIMARY_CHART_IDS]

    updated_at = datetime.now(tz=KST)
    return {
        "updatedAt": updated_at.isoformat(),
        "updatedLabel": updated_at.strftime("%Y-%m-%d %H:%M:%S KST"),
        "groups": CARD_GROUPS,
        "cards": cards,
        "mainCharts": main_charts,
        "headlines": headlines,
        "summary": summary,
        "errors": errors,
    }


def get_dashboard_payload(force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh:
        cached = DASHBOARD_CACHE.get()
        if cached is not None:
            return cached

    payload = assemble_dashboard()
    DASHBOARD_CACHE.set(payload)
    return payload


def write_dashboard_json(payload: dict[str, Any] | None = None) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    snapshot = payload or get_dashboard_payload(force_refresh=True)
    target = DATA_DIR / "dashboard.json"
    target.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def serve_file(handler: BaseHTTPRequestHandler, base_dir: Path, relative_path: str) -> None:
    target = (base_dir / relative_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())) or not target.exists():
        handler.send_error(HTTPStatus.NOT_FOUND, "File not found")
        return

    content_type = "text/plain; charset=utf-8"
    if target.suffix == ".html":
        content_type = "text/html; charset=utf-8"
    elif target.suffix == ".css":
        content_type = "text/css; charset=utf-8"
    elif target.suffix == ".js":
        content_type = "application/javascript; charset=utf-8"
    elif target.suffix == ".json":
        content_type = "application/json; charset=utf-8"

    data = target.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path in {"/", "/index.html"}:
            serve_file(self, ROOT_DIR, "index.html")
            return

        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            serve_file(self, STATIC_DIR, relative)
            return

        if path.startswith("/data/"):
            relative = path.removeprefix("/data/")
            serve_file(self, DATA_DIR, relative)
            return

        if path == "/api/dashboard":
            self.handle_dashboard()
            return

        relative = path.removeprefix("/")
        candidate = (ROOT_DIR / relative).resolve()
        if str(candidate).startswith(str(ROOT_DIR.resolve())):
            if candidate.is_dir():
                index_file = candidate / "index.html"
                if index_file.exists():
                    serve_file(self, ROOT_DIR, str(index_file.relative_to(ROOT_DIR)))
                    return
            elif candidate.is_file():
                serve_file(self, ROOT_DIR, str(candidate.relative_to(ROOT_DIR)))
                return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def handle_dashboard(self) -> None:
        force_refresh = "refresh=1" in self.path
        try:
            payload = get_dashboard_payload(force_refresh=force_refresh)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001
            error_data = json.dumps(
                {"message": "데이터를 불러오지 못했습니다.", "detail": str(exc)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(error_data)))
            self.end_headers()
            self.wfile.write(error_data)

    def log_message(self, format: str, *args: Any) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock and economy daily dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--open", action="store_true", help="Open browser after startup")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Dashboard running at {url}")
    print("Press Ctrl+C to stop.")

    if args.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
