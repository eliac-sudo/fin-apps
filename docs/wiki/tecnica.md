---
title: Analisi tecnica
kind: calcolo
status: descrive, non testato
brief: Trend, RSI, reset, supporti e resistenze calcolati dal codice su 4h, 1g, 1s e 1M.
code: bzd/technicals.py#analyze, bzd/technicals.py#trend_of, bzd/technicals.py#pick_levels, bzd/technicals.py#find_reset, bzd/indicators.py#rsi
feeds: zone, alert-telegram, app, piano
tab: tecnica
---
## In breve
- **Trend**: rialzo se il prezzo è sopra la media a 20 e questa sopra quella a 50; ribasso al contrario; altrimenti laterale (`bzd/technicals.py#trend_of`).
- **Reset**: RSI in ipervenduto mentre il trend di fondo sale, o in ipercomprato mentre scende (`bzd/technicals.py#find_reset`). Va su Telegram.
- **Livelli**: massimi e minimi che si ripetono alla stessa quota. Larghezza e ampiezza minima usano l'ATR mediano, così una candela violenta non sposta niente; un livello settimanale resta alla stessa quota sul giornaliero (`bzd/technicals.py#pick_levels`).

## Quanto fidarsi
Nessuna di queste letture è testata come segnale. I livelli servono al [[piano]] per proporre stop e obiettivi.
