---
title: Hyperliquid
kind: fonte
status: dato pubblico
brief: Prezzi quasi in tempo reale, book, funding e posizioni dei portafogli, da un exchange on-chain.
code: bzd/jobs.py#HL, bzd/jobs.py#hl, bzd/wallets.py#LEADERBOARD
data: data/raw/hl_ctx_main, data/raw/hl_ctx_xyz, data/raw/hl_candles_5m_btc, data/raw/hl_l2_btc
feeds: recorder, portafogli-hl, ricerca-mercati, movimenti
---
## In breve
Hyperliquid è un exchange di future perpetui le cui API sono pubbliche e gratuite. Oltre alle cripto ha il mercato `xyz`, con indici, materie prime, cambi e azioni (S&P 500, oro, petrolio, yen…).

## Cosa prendiamo
- **Contesto dei mercati** (prezzo, funding, posizioni aperte) ogni pochi minuti: `data/raw/hl_ctx_main` e `data/raw/hl_ctx_xyz`. È la base dei [[movimenti]] forti.
- **Candele a 5 minuti e a 1 ora** e **book** dei mercati seguiti.
- **Classifica e posizioni dei portafogli**: le raccoglie [[portafogli-hl]], non il recorder.

## Quanto fidarsi
Il dato è quello dell'exchange, senza ritocchi. Nessuno storico gratuito della classifica: ogni giorno non registrato è perso. BZD non ha chiavi di trading e non manda ordini (vedi [[regole]]).
