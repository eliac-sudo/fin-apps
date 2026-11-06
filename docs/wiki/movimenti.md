---
title: Forti movimenti
kind: calcolo
status: dice che si muove, non dove va
brief: Un movimento forte per la volatilità di quel mercato, quasi in tempo reale, dalle istantanee Hyperliquid.
code: bzd/moves.py#find_moves, bzd/moves.py#daily_sigma, bzd/moves.py#apply_cooldown, bzd/moves.py#COOLDOWN_HOURS
data: data/raw/hl_ctx_main, data/raw/hl_ctx_xyz
feeds: alert-telegram
fresh: live
---
## In breve
Confronta il prezzo di adesso con quello di qualche ora e giorno fa, in unità della volatilità giornaliera degli ultimi 90 giorni dello stesso mercato. Soglie scelte per la frequenza (2-3 messaggi a settimana sulle cripto), non per cosa succede dopo. Dopo un avviso, 12 ore di pausa per mercato e direzione.

Negli alert le distanze da supporti e resistenze partono dal prezzo live (vedi [[tecnica]]).
