---
title: Portafogli Hyperliquid
kind: raccolta
status: non testato, si accumula da ora
brief: I trader più profittevoli e i vault migliori: posizioni ogni ora, fill ogni giorno, e la loro strategia ricostruita dai fill.
code: bzd/wallets.py#choose, bzd/wallets.py#choose_vaults, bzd/wallets.py#take_positions, bzd/wallets.py#update_fills, bzd/wallets.py#profile, bzd/wallets.py#round_trips, bzd/wallets.py#detail, bzd/wallets.py#view
docs: docs/CHI_COMPRA.md
data: data/hl_wallets
feeds: chi-compra, ricerca-mercati
fresh: live
---
## In breve
1. Ogni giorno la classifica pubblica e la lista dei vault di Hyperliquid. Si seguono i 150 trader con più profitti di sempre e i 50 del mese, esclusi market maker e conti fermi, e fino a 40 vault aperti con almeno $100.000, 90 giorni di vita e un profitto. I vault del protocollo (HLP) restano fuori: sono il market making della borsa.
2. Ogni ora le posizioni di tutti; ogni giorno i fill nuovi, che si accumulano. Hyperliquid dà solo gli ultimi 10.000 fill, quindi per i conti più attivi la storia comincia dal giorno in cui li seguiamo.
3. Cliccando un conto nell'app: posizioni con leva e distanza dalla liquidazione, curva del profitto, esposizione nel tempo e un profilo della strategia. Il profilo dice quanto tiene una posizione (da aperta a chiusa, o stimato dal giro d'affari), long o short, su quali mercati, quante chiusure in utile, ordini limite o a mercato, TWAP e orari.

## Cosa sappiamo
Niente di testato: il profitto passato non prova bravura. Un vincente può essere fortunato, coprire una posizione fatta altrove o essere una gamba di un arbitraggio. Il profilo descrive come opera un conto; dire che copiarlo renderebbe richiede mesi di registrazione e una pre-registrazione ([[chi-compra]]).
