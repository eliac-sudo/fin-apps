# Raddoppi tutto o niente sul perpetuo BTC: la simulazione

Eseguita il 24 novembre 2026 sullo storico orario del perpetuo BTC di Deribit, gennaio 2019 – novembre 2026, con il funding vero. Idea dell'utente, non c'è nessun bot. Non è consulenza finanziaria.

## Regole

- Tutto il capitale in garanzia per una posizione da L volte il capitale.
- Vince quando il conto arriva a ×2: l'obiettivo è un ordine limite da maker, senza commissione.
- Perde quando il conto scende al margine di mantenimento e la piattaforma liquida: resta zero. Provati 0,5% del nozionale (circa Deribit) e 1,25% (circa Hyperliquid).
- Entrata all'apertura dell'ora da maker. Se in un'ora il prezzo tocca sia l'obiettivo sia la liquidazione, il lancio è perso.
- Un lancio parte ogni giorno alle 00:00 UTC (2.885 lanci). Le catene di lanci uno dopo l'altro partono ogni lunedì (412 catene).
- Script: `scripts/research/vol_fetch_ohlc.py`, `scripts/research/vol_fetch_funding.py`, `scripts/research/double_sim.py`.

## Risultati

| Leva | Mantenimento | Long | Short | Media* | Durata di un lancio | 11 raddoppi con la media |
|---|---|---|---|---|---|---|
| 5× | 0,5% | 54,2% | 44,9% | 49,6% | ~32 giorni | 1 su ~2.200 |
| 10× | 0,5% | 53,8% | 44,1% | 49,0% | ~10 giorni | 1 su ~2.600 |
| 20× | 0,5% | 50,2% | 45,0% | 47,6% | ~2,7 giorni | 1 su ~3.400 |
| 20× | 1,25% | 45,2% | 41,0% | 43,1% | ~2,2 giorni | 1 su ~10.700 |
| 40× | 0,5% | 44,6% | 44,2% | 44,4% | ~17 ore | 1 su ~7.600 |
| 50× | 0,5% | 42,4% | 42,9% | 42,6% | ~13 ore | 1 su ~11.700 |
| 50× | 1,25% | 26,0% | 27,8% | 26,9% | ~6 ore | 1 su ~2 milioni |

\*La media tra long e short toglie il vantaggio del long, dovuto al fatto che BTC è salito di circa 30 volte nel periodo e che non si può dare per ripetibile.

Nessuna delle 412 catene ha fatto 11 raddoppi. Il massimo è 10, con 5× long; con 20× il massimo è 8–9.

## Cosa ne viene

1. **La leva alta non conviene.** La liquidazione scatta prima che il conto arrivi a zero, a una distanza pari al margine di mantenimento: più alta è la leva, più vicina è rispetto all'obiettivo. A 50× con il mantenimento di Hyperliquid si vince un lancio su quattro.
2. **Il compromesso tra velocità e probabilità è 10–20× su una piattaforma con mantenimento basso:** un lancio dura da 3 a 10 giorni e si vince circa 48–49 volte su 100.
3. **11 raddoppi di fila riescono circa 1 volta su 2.500–3.500** nel caso neutro. Con il long in un mercato che sale come nel 2019–2026, circa 1 su 900–2.000.
4. **Valore atteso:** con 48% per lancio, 100 € giocati valgono in media circa 65 €.
