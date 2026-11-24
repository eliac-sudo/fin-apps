---
title: Binance, Bybit, OKX, Deribit
kind: fonte
status: dato pubblico
brief: Candele, funding, leva, quote long e short di retail e top trader, opzioni e liquidazioni cripto.
code: bzd/history.py#get_crypto, bzd/history.py#get_positions, bzd/history.py#refresh_positions, bzd/jobs.py#all_jobs
data: data/hist/crypto, data/hist/positions, data/raw/opt_deribit_btc, data/raw/liq_okx_btc
feeds: storico, recorder
---
## In breve
Gli exchange cripto più grandi pubblicano gratis molto di più delle borse tradizionali: oltre ai prezzi, quanti conti sono long e quanto pesano i conti più grossi.

## Cosa prendiamo
- **Binance**: candele a 4 ore e giornaliere, funding, posizioni aperte (OI), quota di conti long (il «retail») e quota long dei top trader (il 20% dei conti con più margine), acquisti e vendite aggressive. Finiscono in `data/hist/crypto` e `data/hist/positions`.
- **Bybit**: la stessa quota di conti long, per avere il retail di due exchange (`data/hist/positions`, file `_bybit`).
- **Deribit, OKX, Bybit, Binance**: catene di opzioni, salvate dal [[recorder]] in `data/raw/opt_*`.
- **OKX**: liquidazioni, `data/raw/liq_okx_*`.

## Quanto fidarsi
«Retail» qui vuol dire *quanti conti*, non *quanti soldi*: un conto piccolo e uno enorme pesano uguale. È spiegato in `docs/CHI_COMPRA.md`.
