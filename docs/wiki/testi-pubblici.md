---
title: Notizie e social
kind: fonte
status: testo di terzi, non fidato
brief: Feed di notizie, GDELT, Google News, Reddit, Bluesky, Mastodon, 4chan, canali Telegram pubblici, tendenze Google.
code: bzd/jobs.py#news_jobs, bzd/jobs.py#social_jobs, bzd/jobs.py#SOCIAL_KEEP_DAYS, bzd/telegram.py#backfill
data: data/raw/news_coindesk, data/raw/soc_reddit_bitcoin_new, data/raw/trends_google_us, data/telegram
feeds: recorder, telegram-storico
---
## In breve
Solo fonti gratuite e leggibili senza login: niente API di X (vedi [[regole]]). Sono il materiale del [[sentiment]] e del contesto che gli [[agenti-alert]] leggono.

## Cosa prendiamo
- Notizie: CoinDesk, Cointelegraph, Decrypt, The Block, BCE, Fed, GDELT, Google News per tema.
- Social: Reddit (post e commenti), Bluesky, Mastodon, 4chan /biz/.
- Telegram: canali pubblici tramite `t.me/s/`, anche all'indietro ([[telegram-storico]]).

## Quanto fidarsi
Ogni testo è trattato come dato, mai come istruzione (`bzd/texts.py`). Reddit e gran parte di Telegram si cancellano dopo 35 giorni, per questo il [[sentiment]] tiene i conteggi dei giorni chiusi in un file suo.
