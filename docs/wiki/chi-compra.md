---
title: Chi compra
kind: calcolo
status: descrive, non testato
brief: Quando il prezzo è a un dip o a un top, il retail e i grossi comprano o vendono? E quanto forte rispetto al loro solito?
code: bzd/flows.py#market_view, bzd/flows.py#overview, bzd/flows.py#pressure_of, bzd/flows.py#action, bzd/flows.py#beyond_move, bzd/flows.py#how_from_oi, bzd/flows.py#habit
docs: docs/CHI_COMPRA.md
data: data/hist/positions, data/hist/cot
feeds: app
tab: chi
---
## Le due domande
1. **Il prezzo è a un estremo?** Dip e top sono le [[zone]] calcolate sui soli indicatori di prezzo.
2. **Chi si muove?** Due gruppi per mercato, il retail e i grossi.
   - Cripto: retail = quota di conti long su Binance e Bybit; grossi = quota long dei top trader Binance ([[exchange-cripto]]). In più il **denaro**: dollari comprati meno venduti da chi attraversa lo spread.
   - Altri mercati: retail = posizioni piccole del [[cot]]; grossi = fondi a leva o managed money. Settimanale e in ritardo.

## Come si misura
- **Pressione** (`bzd/flows.py#pressure_of`): dove sta la variazione di posizione di oggi tra quelle passate dello stesso gruppo, da −100 a +100. +90 = più acquisti del 95% delle volte.
- **Compra o vende** (`bzd/flows.py#action`): solo da 50 in su (`bzd/flows.py#INTENSITY_MIN`); sotto è rumore normale, «fermo».
- **Oltre il riflesso** (`bzd/flows.py#beyond_move`): il retail compra quasi sempre quando il prezzo scende. Si toglie la parte che il solo movimento del prezzo prevede e si guarda cosa resta.
- **Apre o chiude** (`bzd/flows.py#how_from_oi`): sul COT è un fatto, sulle cripto si deduce dalle posizioni aperte di tutto il mercato, e sotto lo 0,5% non si può dire.

## Cosa sappiamo
Il retail cripto si muove contro il prezzo (−0,54 su BTC a 3 giorni), i top trader no. Sui dip di BTC il retail compra oltre la soglia nel 24% delle barre, oltre il riflesso solo nel 2%. Dopo non si vede una differenza utile. Misura descrittiva (`docs/CHI_COMPRA.md`). Accanto, nell'app, ci sono i [[portafogli-hl]].
