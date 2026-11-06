---
title: Tag momentum
kind: calcolo
status: momentum sul giornaliero regge nel test v4, vantaggio relativo e piccolo
brief: Quanto è tirato un mercato su ogni timeframe, e in che verso tende a continuare: MOM↓ e MOM↑, prima BYZ e SZT.
code: bzd/zones.py#market_zones, bzd/zones.py#indicator_score, bzd/zones.py#sentiment_score, bzd/zones.py#tag_of, bzd/zones.py#streak
docs: docs/ZONE_MOMENTUM.md, docs/V4_STORICO.md
feeds: chi-compra, app
tab: oggi
---
## In breve
**MOM↓**: tirato in basso, e tende a continuare a scendere. **MOM↑**: tirato in alto, e tende a continuare a salire. Prima si chiamavano BYZ e SZT, ma i test hanno detto il contrario dei vecchi nomi ([[v3]], [[v4]]). Cinque timeframe: 4h, 1g, 1s, 1M, 12M. «3+» segna il momentum su da almeno 3 sedute di fila.

Gli indicatori (RSI, Bollinger, distanza dalle medie, posizione nel range) pesano 70%, il [[sentiment]] 30%. Con meno di 10 testi contano solo gli indicatori e il tag porta un asterisco.

## Dove si usa
Il «dip» e il «top» di [[chi-compra]] sono le stesse zone, calcolate però sui soli indicatori di prezzo (`bzd/zones.py#indicator_score`): una definizione sola in tutta l'app.

## Quanto fidarsi
Sul giornaliero, su 50 mercati mai usati, il prezzo ha continuato nel verso del tag per 10 sedute, circa 0,6% più del solito. Tolti i costi, lo short dopo MOM↓ ha perso. Gli altri timeframe sono solo descritti, e sul mensile il prezzo torna indietro (`docs/ZONE_MOMENTUM.md`).
