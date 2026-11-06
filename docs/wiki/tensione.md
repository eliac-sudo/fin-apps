---
title: Tensione
kind: calcolo
status: descrive, non prevede
brief: Da 0 a 100, quanto un mercato è tirato rispetto al suo passato. 50 è la norma.
code: bzd/thermo.py#heat_from, bzd/thermo.py#reading, bzd/thermo.py#market_position, bzd/thermo.py#BANDS, bzd/snapshot.py#markets_part
feeds: app, alert-telegram
tab: oggi
---
## In breve
Il vecchio «calore» (nel codice si chiama ancora heat). È la media semplice di percentili, ognuno calcolato solo sui dati precedenti: slancio, RSI, distanza dalla media, e sulle cripto funding e leva, altrove il posizionamento COT e la calma della volatilità.

## Parole
Da 0 a 19 molto tirato in basso, poi tirato in basso, in equilibrio (40–59), tirato in alto, molto tirato in alto (`bzd/thermo.py#BANDS`). Va anche su Telegram una volta al giorno.

## Prezzo caro o economico
`bzd/thermo.py#market_position` dice dove sta il prezzo nelle chiusure dell'ultimo anno, da «molto economico» a «molto caro». È una posizione, non una valutazione.
