# Vendere volatilità su BTC, ETH e S&P: lo storico

Eseguito il 24 novembre 2026, una volta sola. È un'esplorazione: le 8 varianti sono state fissate prima di vedere i risultati, ma non c'era una pre-registrazione come per i test v1–v5. Non è consulenza finanziaria.

## Dati e metodo

- **Deribit, BTC ed ETH, gennaio 2019 – ottobre 2026.** Ogni lunedì, gli scambi di opzioni tra le 10 e le 16 UTC dallo storico pubblico di Deribit: per ogni contratto il prezzo di mark dell'ultimo scambio, quindi smile, skew e base veri. Scadenza più vicina a 30 giorni (21–45), tenuta fino a scadenza e regolata sul perpetuo alle 08:00 UTC.
- **Costi:** metà spread pari a max(0,0001 in moneta, 4% del prezzo) per gamba, misurato sulle catene salvate dal recorder (3–9% del prezzo sulle put fuori dal denaro). In più le commissioni Deribit: 0,0003 per gamba, al massimo il 12,5% del prezzo, e 0,00015 alla consegna sulle gambe in the money.
- **Rischio:** per gli spread, la perdita massima. Per le gambe nude, la perdita con un calo del 60% (put) o un rialzo di 2,5 volte (call). Con garanzia in moneta, il caso peggiore anche a metà dello strike dell'ala.
- **Portafoglio:** le regole del bot, cioè 3% del conto a rischio per operazione e 12% in tutto.
- **S&P:** gli indici di strategia di Cboe (PUT, WPUT, CNDR, BFLY, BXM) contro SPY con i dividendi.
- **Script:** `scripts/research/vol_fetch_trades.py`, `scripts/research/vol_fetch_px.py`, `scripts/research/vol_backtest.py` (con `NOCOST=1` senza costi), `scripts/research/vol_cboe.py`, `scripts/research/vol_vrp.py`.

## BTC (circa 275 entrate per variante)

| Variante | Vinte | Medio sul rischio, netto | t | Lordo | Bot USDC /anno | max DD | In moneta /anno |
|---|---|---|---|---|---|---|---|
| A put nuda 20Δ | 85% | +1,7% | 1,4 | +2,0% | +2,0% | −4% | +0,4% |
| **B put spread 20/7 (il bot)** | 84% | **−1,0%** | −0,3 | +0,7% | +0,2% | −14% | −1,1% |
| C put spread 20/10 | 82% | −2,0% | −0,4 | +1,0% | −0,9% | −19% | −1,7% |
| D put spread 30/10 | 77% | −0,1% | 0,0 | +2,2% | +0,2% | −21% | −1,6% |
| E put spread 20, ala 5% | 81% | −3,0% | −0,7 | +1,9% | −2,2% | −25% | −2,3% |
| F iron condor 20/7 | 68% | −7,4% | −1,7 | −5,3% | −5,7% | −39% | −2,8% |
| G strangle 20Δ | 70% | +0,1% | 0,2 | +0,3% | +0,2% | −3% | +0,4% |
| H put spread 10/3 | 92% | +1,1% | 0,7 | +2,1% | +1,7% | −4% | +0,2% |

Il bot (B) anno per anno: 2019 +1%, 2020 +1%, 2021 +1%, 2022 −11%, 2023 +7%, 2024 +10%, 2025 −7%, 2026 −13%.

## ETH (circa 250 entrate per variante)

Nessuna variante sopra lo zero in modo apprezzabile. Il put spread del bot fa −2,3% sul rischio, −2,2% l'anno, drawdown −22%. L'iron condor fa −9,6%.

## S&P, indici Cboe, 2007–2026

| | Rendimento /anno | Volatilità | max DD | Sharpe circa |
|---|---|---|---|---|
| PUT (put ATM mensile, garantita) | 6,8% | 10,8% | −37% | 0,66 |
| WPUT (settimanale) | 4,0% | 10,0% | −29% | 0,44 |
| CNDR (iron condor con ali) | 0,8% | 6,9% | −20% | 0,13 |
| BFLY | −2,2% | 11,4% | −55% | −0,16 |
| BXM (covered call) | 5,5% | 11,1% | −40% | 0,54 |
| SPY | 10,3% | 15,5% | −55% | 0,71 |

## Cosa ne viene

1. **Nessuna variante a rischio definito guadagna al netto dei costi in modo distinguibile dal caso**, né su BTC né su ETH. Il put spread del bot è circa zero su BTC e negativo su ETH.
2. **Il premio c'è, ma lo mangiano l'ala e i costi.** Al lordo gli spread su BTC fanno da +0,7% a +2,2% sul rischio. L'ala comprata costa cara per lo skew, e su prezzi piccoli metà spread e commissioni pesano.
3. **Vendere call su cripto perde:** l'iron condor è il peggiore, su BTC, su ETH e sull'S&P (CNDR).
4. **La garanzia in moneta è peggiore della garanzia in USDC** in ogni variante.
5. **L'unico risultato positivo e coerente è la put venduta, nuda o molto lontana** (A e H su BTC), ed è piccolo e non significativo (t 1,4 e 0,7). Sull'S&P la put venduta ha un rendimento per rischio simile all'indice, non migliore.
6. **Limiti:** prezzi di mark, non esecuzioni vere; tenute a scadenza, mentre il bot esce al 50% o a 7 giorni; 2019–2020 con pochi scambi; un periodo in cui BTC è salito da 3.500 a oltre 100.000 dollari, che favorisce chi vende put.
