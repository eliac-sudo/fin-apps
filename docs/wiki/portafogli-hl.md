---
title: Portafogli Hyperliquid
kind: raccolta
status: non testato, si accumula da ora
brief: Classifica ogni giorno e posizioni ogni ora dei conti più e meno profittevoli, esclusi market maker e vault.
code: bzd/wallets.py#take_leaderboard, bzd/wallets.py#choose, bzd/wallets.py#take_positions, bzd/wallets.py#view
docs: docs/CHI_COMPRA.md
data: data/hl_wallets
feeds: chi-compra, ricerca-mercati
fresh: live
---
## In breve
Quattro gruppi: i 150 vincenti e i 150 perdenti di sempre, i 50 vincenti e i 50 perdenti del mese. Per ognuno si somma, mercato per mercato, quanto è long o short in dollari.

## Come si scelgono i conti
`bzd/wallets.py#choose` tiene solo conti con almeno 100.000 $ (`bzd/wallets.py#MIN_CAPITAL`) e un volume mensile tra 0,5 e 100 volte il capitale (`bzd/wallets.py#TURNOVER`): fuori restano i conti fermi e i market maker.

## Quanto fidarsi
Il profitto passato non prova bravura: un vincente può essere fortunato, una copertura o una gamba di un'operazione fatta altrove. Dopo un calo i vincenti del mese sono soprattutto chi era short. Descrive, non è un segnale.
