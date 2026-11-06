---
title: Chi compra
kind: calcolo
status: descrive, non testato
brief: Chi è long e chi è short: retail e grossi rispetto ai loro ultimi 3 anni, da 0 a 100.
code: bzd/flows.py#level_now, bzd/flows.py#crypto_levels, bzd/flows.py#cot_levels, bzd/flows.py#rolling_pct, bzd/flows.py#positioning, bzd/flows.py#pressures
docs: docs/CHI_COMPRA.md
data: data/hist/positions, data/hist/cot
feeds: app
tab: chi
---
## Come funziona
1. Per ogni mercato, due gruppi. Sulle cripto il **retail** è la quota di conti long su Binance e Bybit, i **grossi** la quota long dei top trader Binance; dati giornalieri ([[exchange-cripto]]). Sugli altri il retail sono le posizioni piccole del [[cot]] e i **fondi** i leveraged funds o il managed money, in netto sulle posizioni aperte; dati settimanali.
2. Il livello di oggi si confronta con gli ultimi 3 anni dello stesso gruppo: un percentile da 0, il più short, a 100, il più long. Sul COT è il classico «COT index».
3. Sopra 90 il gruppo è affollato long, sotto 10 affollato short. «Opposti» quando uno sta sopra il 70 e l'altro sotto il 30.

## Cosa sappiamo
Sulle cripto il retail diventa più long quando il prezzo scende, quasi per riflesso. Seguire chi compra sul dip non ha aiutato nel test [[v3]] (F1 e F2, che usano le variazioni in `bzd/flows.py#pressures`). I livelli non sono testati: che un gruppo affollato preceda un'inversione è un'idea diffusa, non verificata qui. I portafogli di Hyperliquid sono nella stessa scheda ([[portafogli-hl]]).
