"""What the recorder collects. Priority: data with no free history, which is lost if not saved now."""
from dataclasses import dataclass, replace
from urllib.parse import quote

MIN, HOUR, DAY = 60, 3600, 86400
HL = "https://api.hyperliquid.xyz/info"

# Minimum seconds between requests to one host, set from testing on 4 Nov 2026:
# Reddit returned 429 at 8s and worked at 60s; GDELT returned 429 even at 15s, so it gets a wide gap.
HOST_GAP = {
    "t.me": 4, "cdn.cboe.com": 20, "www.reddit.com": 60, "api.gdeltproject.org": 60, "news.google.com": 5,
    "api.stlouisfed.org": 1, "api.hyperliquid.xyz": 0.5,
}
DEFAULT_GAP = 2
SOCIAL_KEEP_DAYS = 35  # covers daily, weekly and monthly analysis, with a margin for late runs


# Public channels checked 4 Nov 2026: active, with a post on or near that date. Size alone doesn't prove a channel is
# official, and lookalikes exist (whale_bot_alerts, walter_bloomberg), so each is a third-party source until checked.
# Liquidation channels poll fastest because a panic can push posts off the 20-post page; backfill can recover them.
TELEGRAM = {
    "BinanceLiquidations": 5 * MIN, "HyperliquidLiquidations": 5 * MIN,
    "whale_alert_io": 15 * MIN, "whalebotalerts": 30 * MIN, "lookonchainchannel": 30 * MIN,
    "cryptoquant_official": 30 * MIN, "glassnode": 30 * MIN,
    "WatcherGuru": 15 * MIN, "wublockchainenglish": 15 * MIN, "cointelegraph": 30 * MIN, "unfolded": 30 * MIN, "bitcoin": 30 * MIN,
    "walterbloomberg": 15 * MIN, "financialjuice": 15 * MIN, "TheKobeissiLetter": 30 * MIN,
    "binance_announcements": 30 * MIN, "bybit_announcements": 30 * MIN, "OKXAnnouncements": 30 * MIN, "hyperliquid_announcements": 30 * MIN,
}


@dataclass(frozen=True)
class Job:
    name: str
    url: str  # may hold {ENV_VAR} placeholders, expanded only at request time and never logged
    every: int
    kind: str = "json"  # json | xml | csv | tg
    body: tuple = ()  # sorted (key, value) pairs of a JSON POST body
    needs: tuple = ()  # env vars required; the job is skipped without them
    keep: int = 0  # days of raw responses to keep; 0 keeps them for good


def hl(name, every, **body):
    return Job(name, HL, every, body=tuple(sorted(body.items())))


def all_jobs():
    j = []
    # Option chains: no free history found
    for t in ("SPY", "_SPX", "GLD", "TLT", "USO", "FXE"):
        j.append(Job(f"opt_cboe_{t.strip('_').lower()}", f"https://cdn.cboe.com/api/global/delayed_quotes/options/{t}.json", 6 * HOUR))
    for c in ("BTC", "ETH"):
        j.append(Job(f"opt_deribit_{c.lower()}", f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={c}&kind=option", HOUR))
        j.append(Job(f"opt_okx_{c.lower()}", f"https://www.okx.com/api/v5/public/opt-summary?uly={c}-USD", 6 * HOUR))
        j.append(Job(f"opt_bybit_{c.lower()}", f"https://api.bybit.com/v5/market/tickers?category=option&baseCoin={c}", 6 * HOUR))
    j.append(Job("opt_binance", "https://eapi.binance.com/eapi/v1/ticker", 6 * HOUR))

    # Liquidations: no free history found
    for c in ("BTC", "ETH", "SOL"):
        j.append(Job(f"liq_okx_{c.lower()}", f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly={c}-USDT&state=filled&limit=100", 5 * MIN))

    # Hyperliquid: OI is current-only and candles keep a rolling window
    j.append(hl("hl_ctx_main", 15 * MIN, type="metaAndAssetCtxs"))
    j.append(hl("hl_ctx_xyz", 15 * MIN, type="metaAndAssetCtxs", dex="xyz"))
    coins = ("BTC", "ETH", "SOL", "xyz:SP500", "xyz:XYZ100", "xyz:CL", "xyz:GOLD", "xyz:SILVER", "xyz:EUR", "xyz:JPY", "xyz:TLT")
    for c in coins:
        slug = c.replace(":", "_").lower()
        j.append(hl(f"hl_l2_{slug}", 5 * MIN, type="l2Book", coin=c))
    return j + social_jobs() + news_jobs() + macro_jobs()


def candle_jobs():
    """Rolling-window candles: 5,000 bars is ~208 days at 1h and ~17 days at 5m, so weekly pulls lose nothing.

    The range is deliberately wider than any window: the API returns the latest 5,000 bars inside it.
    """
    out = []
    for c in ("BTC", "ETH", "SOL", "xyz:SP500", "xyz:XYZ100", "xyz:CL", "xyz:GOLD", "xyz:SILVER", "xyz:EUR", "xyz:JPY", "xyz:TLT"):
        slug = c.replace(":", "_").lower()
        for iv in ("1h", "5m"):
            req = {"coin": c, "interval": iv, "startTime": 1577836800000, "endTime": 4102444800000}
            out.append(Job(f"hl_candles_{iv}_{slug}", HL, 7 * DAY, body=(("req", req), ("type", "candleSnapshot"))))
    return out


def refetchable(name):
    return name.startswith("soc_reddit_") or (name.startswith("soc_tg_") and "liquidations" not in name)


def social_jobs():
    j = []
    for s in ("CryptoCurrency", "Bitcoin", "ethtrader", "wallstreetbets", "stocks", "investing", "Gold", "Forex", "Commodities", "bonds"):
        j.append(Job(f"soc_reddit_{s.lower()}_new", f"https://www.reddit.com/r/{s}/new/.rss", HOUR, "xml"))
        j.append(Job(f"soc_reddit_{s.lower()}_comments", f"https://www.reddit.com/r/{s}/comments/.rss", HOUR, "xml"))
    for q in ("bitcoin", "crypto", "stocks", "gold", "oil", "forex", "treasury yields"):
        j.append(Job(f"soc_bluesky_{q.replace(' ', '_')}", f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote(q)}&limit=100&sort=latest", HOUR))
    for t in ("bitcoin", "crypto", "stocks"):
        j.append(Job(f"soc_mastodon_{t}", f"https://mastodon.social/api/v1/timelines/tag/{t}?limit=40", HOUR))
    j.append(Job("soc_4chan_biz", "https://a.4cdn.org/biz/catalog.json", HOUR))
    for c, every in TELEGRAM.items():
        j.append(Job(f"soc_tg_{c.lower()}", f"https://t.me/s/{c}", every, "tg"))
    # Only sources that can be fetched again are limited: Reddit via Arctic Shift, Telegram by paging back.
    # Bluesky, Mastodon and 4chan have no other free history here, and liquidation channels are market data.
    return [replace(x, keep=SOCIAL_KEEP_DAYS) if refetchable(x.name) else x for x in j]


def news_jobs():
    j = []
    feeds = {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "decrypt": "https://decrypt.co/feed",
        "theblock": "https://www.theblock.co/rss.xml",
        "fed": "https://www.federalreserve.gov/feeds/press_all.xml",
        "ecb": "https://www.ecb.europa.eu/rss/press.html",
    }
    for n, u in feeds.items():
        j.append(Job(f"news_{n}", u, 30 * MIN, "xml"))
    topics = ("bitcoin", "stock market", "gold price", "oil price", "treasury yields", "forex dollar")
    for q in topics:
        slug = q.replace(" ", "_")
        j.append(Job(f"news_gnews_{slug}", "https://news.google.com/rss/search?q=" + quote(f"site:reuters.com {q}") + "&hl=en-US&gl=US&ceid=US:en", HOUR, "xml"))
        gq = quote(f'"{q}"')
        j.append(Job(f"news_gdelt_tone_{slug}", f"https://api.gdeltproject.org/api/v2/doc/doc?query={gq}&mode=timelinetone&format=json&timespan=1d", HOUR))
        j.append(Job(f"news_gdelt_art_{slug}", f"https://api.gdeltproject.org/api/v2/doc/doc?query={gq}&mode=artlist&format=json&maxrecords=100&timespan=1d&sort=datedesc", HOUR))
    return j


def macro_jobs():
    j = [Job("macro_fng", "https://api.alternative.me/fng/?limit=2", DAY)]
    # Rates, credit, dollar and volatility across markets. Saving daily also records what was known when.
    for s in ("DFF", "DGS2", "DGS10", "T10Y2Y", "BAMLH0A0HYM2", "DTWEXBGS", "VIXCLS", "OVXCLS", "GVZCLS", "EVZCLS"):
        j.append(Job(
            f"macro_fred_{s.lower()}",
            f"https://api.stlouisfed.org/fred/series/observations?series_id={s}&api_key={{FRED_API_KEY}}&file_type=json&sort_order=desc&limit=30",
            DAY, needs=("FRED_API_KEY",),
        ))
    for geo in ("US", "IT"):
        j.append(Job(f"trends_google_{geo.lower()}", f"https://trends.google.com/trending/rss?geo={geo}", 2 * HOUR, kind="xml"))
    return j
