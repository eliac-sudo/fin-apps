---
title: Yahoo e Cboe
kind: fonte
status: dato pubblico, in ritardo
brief: Prezzi di future, indici, cambi e azioni; indici di volatilità e opzioni sugli ETF USA.
code: bzd/history.py#get_tradfi, bzd/history.py#parse_yahoo, bzd/history.py#get_vol, bzd/history.py#WATCH, bzd/technicals.py#app_markets
data: data/hist/tradfi, data/hist/vol, data/raw/opt_cboe_spy
feeds: storico, recorder, ricerca-mercati
---
## In breve
Per tutto ciò che non è cripto i prezzi giornalieri vengono da Yahoo Finance (future su indici, bond, materie prime, cambi). Cboe dà gli indici di volatilità (VIX, OVX, GVZ…) e le catene di opzioni degli ETF (SPY, QQQ, GLD, TLT…).

## Cosa prendiamo
- Chiusure giornaliere in `data/hist/tradfi`, una per mercato.
- Indici di volatilità in `data/hist/vol`: servono alla [[tensione]] e al [[sentiment]] fuori dalle cripto.
- Opzioni Cboe, ritardate di circa 15 minuti, in `data/raw/opt_cboe_*`, lette da [[opzioni]].

## Mercati osservati
Dal 25 novembre 2026 l'app segue anche nove mercati solo per guardarli (`bzd/history.py#WATCH`): credito USA (HYG, LQD), azioni nel mondo (Euro Stoxx 50, DAX, FTSE MIB, Nikkei 225, emergenti EEM, Cina FXI) e i Bund lunghi tedeschi (ETF EXX6). Hanno prezzi, tensione, tecnica, posizione nell'anno e liquidità come gli altri, ma restano fuori dai setup, dagli alert, dal termometro su Telegram e dai test congelati: una lettura su questi mercati si giudica solo sui dati che arrivano da ora. Il COT non c'è, perché la CFTC non copre questi mercati. Indici ed ETF non hanno il problema del cambio di contratto.

## Quanto fidarsi
Yahoo non è una fonte ufficiale e a volte ha buchi o salti al cambio di contratto: `bzd/events.py#roll_artefact` scarta quei salti.
