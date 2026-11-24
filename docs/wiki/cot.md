---
title: Report COT della CFTC
kind: fonte
status: dato ufficiale, settimanale
brief: Chi è long e short sui future USA: piccoli, fondi a leva, managed money. Misurato il martedì, pubblicato il venerdì.
code: bzd/history.py#get_cot, bzd/history.py#cot_positions, bzd/events.py#align_cot
data: data/hist/cot
feeds: storico
---
## In breve
Il Commitments of Traders è il report settimanale dell'ente di vigilanza USA. Divide le posizioni sui future per tipo di operatore. È l'unica fonte gratuita su chi tiene cosa fuori dalle cripto.

## Come lo usiamo
- **Retail** = le posizioni «non segnalabili», sotto la soglia di segnalazione.
- **Grossi** = leveraged funds su indici, bond e cambi; managed money sulle materie prime.
- Il dato del martedì diventa disponibile solo il venerdì: `bzd/events.py#align_cot` lo usa solo da quando era pubblico, così nessun calcolo guarda il futuro.

## Attenzione
Su USD/JPY, USD/CHF e USD/CAD il future è sulla valuta estera, quindi il segno va girato rispetto alla coppia (`bzd/thermo.py#COT_AGAINST_PAIR`). I setup v1 congelati non lo giravano: vedi [[setup-v1]].
