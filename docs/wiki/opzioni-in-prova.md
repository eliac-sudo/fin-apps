---
title: Strategie sulle opzioni in prova
kind: verifica
status: in prova dal 7 novembre 2026, giudizio non prima del 6 novembre 2027
brief: Nove strategie aperte sulla carta ogni giorno, sui prezzi veri di Deribit e Cboe, con regole fissate prima.
code: bzd/option_paper.py#open_entries, bzd/option_paper.py#update, bzd/option_paper.py#settle_price, bzd/option_paper.py#view, bzd/verdicts.py#line
docs: docs/OPZIONI_IN_PROVA.md, config/options_forward_v1.json
data: data/raw/opt_deribit_btc, data/raw/opt_cboe_spy, data/options_paper
feeds: app
tab: opzioni
---
## Come funziona
1. Ogni giorno, per ogni mercato, la prima catena salvata nella finestra di entrata apre le strategie la cui condizione è attiva ([[opzioni]]).
2. Vendi al bid, compri all'ask, tolte le commissioni; si tiene fino alla scadenza vicina ai 30 giorni.
3. A scadenza il risultato si calcola sul prezzo del sottostante; le operazioni aperte si valutano all'ultima catena.
4. Il registro si ricostruisce dai file grezzi, quindi nessuna regola si può ritoccare dopo aver visto un risultato.

## Cosa sappiamo
Ancora niente: è un esperimento sui dati futuri. Lo storico sintetico è nella [[v3]]: vendere ogni giorno ha reso su SPY con perdite rare molto grandi, «economiche» è l'unica lettura che ha retto. Nessun ordine: Deribit e Cboe si leggono solo dai prezzi pubblici.
