---
title: Tag BYZ e SZT
kind: calcolo
status: descrive, non testato
brief: Quanto è tirato un mercato su ogni timeframe: 70% indicatori, 30% sentiment, da −100 a +100.
code: bzd/zones.py#market_zones, bzd/zones.py#indicator_score, bzd/zones.py#sentiment_score, bzd/zones.py#tag_of
docs: docs/ZONE_BYZ_SZT.md
feeds: chi-compra, app
tab: oggi
---
## In breve
**BYZ** (Buy Ze dip): tirato in basso e umore di paura. **SZT** (Sell Ze Top): tirato in alto e umore euforico. Cinque timeframe: 4h, 1g, 1s, 1M, 12M.

Gli indicatori (RSI, Bollinger, distanza dalle medie, posizione nel range) pesano 70%, il [[sentiment]] 30%. Con meno di 10 testi contano solo gli indicatori e il tag porta un asterisco.

## Dove si usa
Il «dip» e il «top» di [[chi-compra]] sono le stesse zone, calcolate però sui soli indicatori di prezzo (`bzd/zones.py#indicator_score`): una definizione sola in tutta l'app.

## Quanto fidarsi
Va nella direzione del nome solo sul mensile; sui timeframe brevi SZT ha continuato a salire. Misura descrittiva, non un test (`docs/ZONE_BYZ_SZT.md`).
