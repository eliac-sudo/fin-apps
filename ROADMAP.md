# BZD roadmap (4 Nov 2026)

Two tracks run side by side: **A, exits** comes first and **B, signals** runs alongside it. Everything uses free sources. No X API and no paid data. It covers crypto, equities, commodities, FX and bonds.

Not financial advice. Leveraged short-term trading can lose the whole position margin.

## Data problems found and handled

- **Yahoo dates (fixed).** Using Yahoo's current timezone offset moved daylight-saving bars back one day, which created lookahead and made the roll filter remove real crashes. After the fix, futures correlate 0.89–0.98 with their ETFs on the same day and about zero with the next day's ETF move, with no weekend bars.
- **Futures rolls.** Where an ETF exists, it decides whether a move was real. NG, HG, ZC, ZW, ZS, ZT and ZF have no ETF check, so they rely on a weaker gap rule.
- **Inconsistent bars (open).** Up to 13% of bars in grains, gold, silver and copper have a close outside the day's high-low range, concentrated in some older years (58% of corn bars in 2002). Don't rely on highs and lows in those periods until checked.
- **Negative oil (handled).** 20 April 2020 can't be logged, so that return is excluded. It is treated as missing, not as a panic.
- **EVZ ended on 2025-03-11.** FX has no volatility index after that, so FX can score fewer conditions in recent data.
- **COT history is uneven.** Contract names change over time, and EUR, RTY and AUD have long gaps (EUR includes its ECU predecessor). Availability dates use Tuesday + 6 days to avoid lookahead.
- **FRED's high-yield spread** returned history only from 2023-11, so it can't be backtested.

## Free sources, tested 4 Nov 2026

Tested with keyless requests from this environment. A source that responded once may still have rate limits or change later, so raw responses get archived.

**Can be backtested**

| Source | Data | Checked |
|---|---|---|
| Binance `fapi` and `data.binance.vision` | candles, funding, 5-min OI, top-trader and taker ratios | candles and funding from 2019-09; metrics exist on 2020-09-01, not 2019-12-01 |
| Bybit v5 | candles, funding, OI | BTC OI from 2020-07 |
| Hyperliquid `/info` | funding, candles | funding from 2023-05; 4h from 2024-07-24; 1h from 2026-04-10 |
| Deribit | DVOL implied-volatility index | sample from 2021-05; historical skew and option chains not available this way |
| Fear & Greed | daily index | responds; history from 2018 per the provider |
| Reddit via Arctic Shift | posts and comments | samples from 2019, 2020, 2022; latest comment 0.8h old. Third-party service, some comments `[removed]` |
| GDELT GKG raw files | news tone | 2015 file downloads; needs filtering, large volume |
| Wikipedia pageviews | attention proxy, daily | 2018 sample |
| Coin Metrics Community, DefiLlama | on-chain, stablecoins | respond |

**Forward-only or unproven history: must be logged from now on**

| Source | Data | Checked |
|---|---|---|
| Reddit RSS | live posts and comments | works at one request per 60 seconds, 429 at 8 seconds; the `.json` route returned 403 |
| Bluesky public API | author feeds, full reply threads, search | works; search returned 403 on `public.api.bsky.app`, 200 on `api.bsky.app` |
| Telegram `t.me/s/<channel>` | public channels | HTML, paging reached 2015 on one channel; could become backtestable |
| 4chan /biz/ JSON | threads and replies | works; short archive |
| Mastodon, Lemmy, Hacker News, YouTube RSS | posts, stories, videos | respond; crypto coverage not measured |
| CoinDesk, Cointelegraph, Decrypt, The Block, Fed, ECB RSS | news | respond |
| Google News RSS | Reuters headlines | responds; unofficial |
| GDELT DOC API | tone, 3-month window | returned 429 even at one request per 15 seconds from here; GKG raw files are the reliable route |
| OKX | recent liquidations | responds; record forward |

**Not usable**: X API (your decision), X syndication (429), Nitter (410), StockTwits (403 Cloudflare), BitMEX funding (403 from here), Coinalyze (needs a key, though it may be free; not checked).

## Liquidations and whale flows: found on Telegram

Public channels can be paged back to their first post, and each message links to its source at `t.me/<channel>/<id>`.

| Channel | Size | Back to | Content |
|---|---:|---|---|
| `BinanceLiquidations` | 177K | 2019-05 | Binance futures liquidations, about 400,000 posts |
| `HyperliquidLiquidations` | 13K | 2024-12 | Hyperliquid liquidations above $50K, including `xyz` markets |
| `whale_alert_io` | 296K | 2019-04 | Large transfers, mints |

Limits to check before using them:

- The channels are third-party bots with minimum sizes, which may have changed over time. Totals are a floor, so compare within a period and don't treat them as complete.
- Outages would look like calm. Check message counts by month, and compare against the recorder's OKX feed and with OI drops.
- Adding these could change the crypto panic score, so that decision belongs in B1c.

Run `python -m bzd.telegram status` to see progress. Other channels recorded going forward are listed in `bzd/jobs.py`, chosen for size and activity. Size doesn't prove a channel is official, and lookalikes exist.

## Scope: all markets, with options signals

The same setups (panic, squeeze, overheating) apply to crypto, equities, commodities, FX and bonds. Tested 4 Nov 2026 with keyless requests.

**What you can trade on Hyperliquid**: `xyz` is the main builder market for indices, commodities, FX and bonds. `io` and `para` also have some volume, mostly in single stocks and pre-IPO names. Other builder markets showed about zero.

| Market | 24h volume | Open interest |
|---|---:|---:|
| `xyz:SP500` | $805M | $390M |
| `xyz:XYZ100` | $658M | $267M |
| `xyz:CL` (oil) | $430M | $224M |
| `xyz:SILVER` | $200M | $228M |
| `xyz:GOLD` | $111M | $320M |
| `xyz:JPY` | $6.6M | $33M |
| `xyz:EUR` | $5.5M | $31M |
| `xyz:COPPER` | $3.7M | $8M |
| `xyz:TLT` (the only bond market found with volume) | $0.6M | $7.7M |
| `xyz:GBP` | $0.08M | $0.4M |

- Single snapshot of one day, so volumes will vary. Single stocks such as NVDA and TSLA also trade there.
- History is short: `xyz:GOLD` candles and funding start around 2025-12-22, so these markets can't be calibrated on their own history.
- FX and bonds may be useful as signals but too thin to trade. Slippage must be measured before any of them goes live.
- These are third-party markets built on Hyperliquid. Oracle rules, hours and deployer risk must be checked before trading them.

**Price and positioning data**

| Source | Data | Checked |
|---|---|---|
| Yahoo chart (unofficial) | ES, CL, GC, ZN, EURUSD, MOVE | `ES=F` daily from 2000-09, 1h from 2024-06 only; no OI field |
| Dukascopy (unofficial) | FX, Bund and US T-bond ticks | EURUSD, Bund, T-bond files for 2020 download; gold, index and oil requests timed out, retest |
| US Treasury CSV | yield curve | 2020 file downloads |
| ECB, Frankfurter | daily FX | Frankfurter reaches 1999 |
| CFTC COT (legacy, financial) | futures positioning, the closest match to crypto funding and OI | legacy from 1986; financial report current to 2026-10-27 |
| FINRA | daily short volume, short interest | responds; relevant to stock squeezes |
| FRED | macro, volatility indices (including EVZ for FX) | works with your free key; keyless CSV timed out |
| Stooq | prices | blocked by a JavaScript check |

**Options data**

| Source | Data | History |
|---|---|---|
| Cboe index files | VIX and SKEW (1990), VVIX (2006), OVX and GVZ (2009) | Backtestable, daily |
| Yahoo `^MOVE` | bond volatility | Responds; start date not checked |
| Deribit history API | every BTC option trade with IV, mark and index price | Sample from 2020-03; lets us rebuild skew and term structure, large job |
| Deribit DVOL | BTC implied-volatility index | From 2021-05 sample |
| Cboe delayed chains | SPY, SPX, GLD, TLT, USO, FXE | **Current snapshot only**: forward recording |
| Deribit, OKX, Bybit, Binance chains | crypto options | Current snapshot: forward recording |

Doesn't work: Cboe total put/call file stops at 2019-10-04, Yahoo options returned 401. DoltHub works when queries filter on date and symbol: it has historical chains and daily IV and realized volatility per underlying.

**Option signals**: IV level and jump, term structure inversion (front IV above back IV, a panic marker), 25-delta skew, put/call, and GEX with both sign conventions. Only the first can be backtested widely today. Skew has SKEW for US equities and Deribit trades for BTC. GEX and put/call by underlying stay forward-only unless a chain history source turns up.

**Rules for non-crypto markets**

- **Use daily bars for non-crypto calibration.** Free hourly history starts in 2024, far too short.
- **Replace funding and OI per market**: COT, short data, and volatility indices. Equal scores across markets are not equal evidence, so results are reported per market class.
- **Respect publication dates.** COT is measured on Tuesday and usually published Friday. Using the Tuesday date would leak future data.
- **Handle futures rolls.** A continuous front-month series can jump at a roll and fake a panic, and session gaps need separate handling.
- **Plan for multiple testing.** 3 setups × 3 horizons × 5 market classes is 45 tests. Pre-register each class as its own family with one primary horizon, and report the rest as descriptive.
- **Report per market class.** Crypto counts don't transfer to other markets.

## Track A: exits

| Phase | Deliverable | Gate |
|---|---|---|
| **A1. Exit lab (calibration done, see `docs/A1_USCITE.md`)** | Simulate exit rules (fixed target, scale-out in thirds, ATR trailing, time stop) on historical dip entries, after fees, funding and slippage | H3 pre-registered, using the calibration period to choose rules |
| **A2. Your fills** | `bzd fills` runs **locally**: your address stays in `.env` and I never need to see it. Replays your real trades against the rules | A rule beats your actual exits, or your exits turn out not to be the problem. Depends on trade count |
| **A3. Exit plan** | Written rules, plus a position-size, stop and target calculator. You place brackets by hand | Used on every trade and journaled |

A1 doesn't need your address. A2 waits until you choose to run it.

## Track B: signals

| Phase | Deliverable | Gate |
|---|---|---|
| **B1a. Recorder (running)** | Start archiving what has no free history: option chains, liquidations, social, L2 books, Hyperliquid candles. Raw responses with timestamps and hashes | Runs unattended with gap alerts. **Every day of delay is data lost for good** |
| **B1b. Historical store (done, except quality items above)** | Download and clean all backtestable data for every market class, with publication dates and futures rolls handled | Coverage report per source and market, plus event counts per class |
| **B1c. Detector (frozen v1, liquidations excluded)** | No-lookahead features and setups: panic, squeeze, **overheating** (trim or tighten stops, not short), with option conditions and per-market substitutes | Definitions and thresholds frozen on data to 2023, pre-registered |
| **B2. Experimental alerts (running on Telegram)** | Terminal or Telegram alert with score, data and links, **labelled unvalidated**. Every signal paper-logged | Runs reliably. You get signals from here, before the tests finish |
| **B3. Event study (run once, see `docs/B3_RISULTATI.md`)** | P1, Q1 and overheating tests against random entries on the same asset, plus stop and target results in R, with clustered errors | Each setup supported, not supported or inconclusive; label updated |
| **B4. Sentiment** | Reddit first, because it can be backtested, then news tone, attention and forward-only sources. LLM labels validated on 100 of your labels | Kappa ≥ 0.6. Backtest whether sentiment adds anything beyond the price, leverage and funding score |
| **B5. Setup card** | Past similar cases with honest intervals, pro and con case, sources with evidence IDs | Every number traces to an evidence ID. Intervals use clusters, not raw cases |

## Rule for the agents (agreed 4 Nov 2026)

Alerts go out on their own, and paid reviews are off (`BZD_AGENTS`). When reviews run:

- **Agents may** read and cite sources, flag inconsistencies, and give a reasoned view for or against.
- **Agents may not** change numbers, scores or stops, or silently block an alert. An alert they reject is still logged with their view.
- **"Confirmed" means** data is fresh, sources were checked and the agent's view is in the message. Only B3 can say whether a setup works.
- **Later:** if logged rejections turn out to avoid losses, agents may filter alerts, but only under a new pre-registered rule.

## Shared final phases

| Phase | Deliverable | Gate |
|---|---|---|
| **C1. Manual app** | Interface, order preparation, risk limits, decision journal with your own probability estimate (Brier score) | Enough journaled trades to review U1 |
| **C2. Testnet** | Exit automation first, then entries only for supported setups. Kill switch and limits in code | Clean runs, including crash and API outage drills. Test that `scheduleCancel` cannot remove stops |
| **C3. Small mainnet** | Capped subaccount and API wallet, Italian tax position checked | Live slippage and results match paper |

## Order

The current state and next steps are in `docs/STATO.md`. Any new setup needs a v2 pre-registration and fresh data.

## Deferred

Reimplementing AMBRA, DRUCK and `quant_crew` comes after this project.
