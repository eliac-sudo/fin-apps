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

## Seconda prova (24 novembre)

Script: `scripts/research/double_sim2.py`.

**Costi veri di Hyperliquid** (mantenimento 1,25%, maker 0,015% su entrata e obiettivo):

| Leva | Long | Short | Media | 11 di fila |
|---|---|---|---|---|
| 5× | 53,1% | 44,3% | 48,7% | 1 su ~2.700 |
| 10× | 51,5% | 42,4% | 47,0% | 1 su ~4.100 |
| 20× | 44,9% | 40,7% | 42,8% | 1 su ~11.000 |
| 40× | 32,6% | 33,4% | 33,0% | 1 su ~200.000 |

**Solo dopo il segnale di momentum testato** (v4: long il giorno dopo «sale forte», short dopo «scende forte»; Deribit). Ci sono 634 giorni di «sale forte» e 290 di «scende forte», ma molto sovrapposti.

| Leva | Long dopo sale forte | Long ogni giorno | Short dopo scende forte | Short ogni giorno | Insieme, contro ogni giorno |
|---|---|---|---|---|---|
| 5× | 59,8% | 54,2% | 43,7% | 44,9% | 54,9% contro 51,3% |
| 10× | 59,0% | 53,8% | 42,2% | 44,1% | 53,7% contro 50,8% |
| 20× | 55,8% | 50,2% | 48,8% | 45,0% | 53,6% contro 48,5% |

Il segnale aggiunge 3–5 punti per lancio, quasi tutti dal lato long. I giorni di segnale consecutivi sono in pratica lo stesso evento, quindi i casi indipendenti sono forse un centinaio: la differenza non si distingue dal caso. E il long ha avuto il vento a favore di un mercato salito di 30 volte.

**Incassare per strada** (1 milione di tentativi simulati, 11 lanci al massimo, posta iniziale = 1):

| Lancio vinto | Messo da parte a ogni raddoppio | Torni con qualcosa | Almeno la posta | Almeno ×10 | Almeno ×100 | In media |
|---|---|---|---|---|---|---|
| 49% | 0% | 0,04% | 0,04% | 0,04% | 0,04% | 0,83 |
| 49% | 25% | 49% | 24% | 1,4% | 0,04% | 0,93 |
| 49% | 50% | 49% | 49% | 0,08% | 0% | 0,96 |
| 47,6% | 0% | 0,03% | 0,03% | 0,03% | 0,03% | 0,62 |
| 47,6% | 50% | 47,6% | 47,6% | 0,06% | 0% | 0,91 |

Mettere da parte a ogni raddoppio non crea guadagno: il valore medio resta sotto la posta. Cambia solo la forma: si torna più spesso con qualcosa, ma non si arriva mai lontano.
