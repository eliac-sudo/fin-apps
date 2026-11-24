---
title: Yahoo e Cboe
kind: fonte
status: dato pubblico, in ritardo
brief: Prezzi di future, indici, cambi e azioni; indici di volatilità e opzioni sugli ETF USA.
code: bzd/history.py#get_tradfi, bzd/history.py#parse_yahoo, bzd/history.py#get_vol
data: data/hist/tradfi, data/hist/vol, data/raw/opt_cboe_spy
feeds: storico, recorder, ricerca-mercati
---
## In breve
Per tutto ciò che non è cripto i prezzi giornalieri vengono da Yahoo Finance (future su indici, bond, materie prime, cambi). Cboe dà gli indici di volatilità (VIX, OVX, GVZ…) e le catene di opzioni degli ETF (SPY, QQQ, GLD, TLT…).

## Cosa prendiamo
- Chiusure giornaliere in `data/hist/tradfi`, una per mercato.
- Indici di volatilità in `data/hist/vol`: servono alla [[tensione]] e al [[sentiment]] fuori dalle cripto.
- Opzioni Cboe, ritardate di circa 15 minuti, in `data/raw/opt_cboe_*`, lette da [[opzioni]].

## Quanto fidarsi
Yahoo non è una fonte ufficiale e a volte ha buchi o salti al cambio di contratto: `bzd/events.py#roll_artefact` scarta quei salti.
