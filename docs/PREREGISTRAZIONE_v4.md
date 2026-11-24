# Pre-registrazione v4: BYZ e SZT come momentum, su mercati nuovi

Scritta il 6 novembre 2026, prima di calcolare qualunque rendimento su questi mercati. Configurazione `config/setups_v4.json`, SHA-256 `7d3130de6eafc7c66ead48f4b43d3edc82c9cfa16cd8adbc499e49530536f88f`. Codice `bzd/v4.py`. Il test si fa una volta sola: `python -m bzd.v4 storico --confirm` rifiuta di ripartire se i risultati esistono o se la configurazione è cambiata.

## Perché

Nel test v3 ([V3_STORICO.md](V3_STORICO.md)) dopo BYZ il prezzo ha continuato a scendere più del solito, e dopo SZT a salire, con t oltre 3. Il test però guardava il verso del nome, quindi il verso opposto è un'osservazione fatta dopo, sui 30 mercati del programma. Ritoccare soglie o ritardi su quegli stessi dati produrrebbe un risultato bello ma falso. Qui la stessa lettura, con la stessa funzione dell'app (`bzd/zones.py#indicator_score`), si prova al contrario su 50 mercati che il programma non ha mai usato.

## Ipotesi

Ingresso all'apertura della seduta dopo il segnale, tenuta 10 sedute, come Z1 e Z2 della v3.

| ID | Lettura | Regola | Operazione |
|---|---|---|---|
| N1 | BYZ | punteggio ≤ −50 | short |
| N2 | SZT | punteggio ≥ +50 | long |
| N3 | BYZ da 3 sedute | terza seduta di fila con punteggio ≤ −50 | short |
| N4 | SZT da 3 sedute | terza seduta di fila con punteggio ≥ +50 | long |
| N5 | BYZ forte | punteggio ≤ −70 | short |
| N6 | SZT forte | punteggio ≥ +70 | long |

N3–N6 rispondono alla domanda «e se fossero meno sensibili?»: due modi decisi prima, non scelti guardando i risultati.

## Mercati

- **Cripto (18):** LTC, BCH, TRX, DOT, ATOM, XLM, ETC, FIL, NEAR, UNI, AAVE, ALGO, XTZ, EOS, NEO, ZEC, DASH, VET. Binance spot, candele giornaliere.
- **Azioni (19):** ETF di settore XLE, XLF, XLK, XLV, XLI, XLP, XLU, XLB, XLY; ETF di paese EWJ, EWG, EWZ, FXI, EWU, EWC, EWA, EWW, EWY, EWT. Yahoo.
- **Materie prime (8):** platino, palladio, caffè, zucchero, cacao, cotone, bovini, suini. Future continui Yahoo.
- **Forex (5):** NZD/USD, EUR/JPY, EUR/GBP, USD/MXN, USD/SEK. Yahoo.

Periodo dal 1° gennaio 2008 al 6 novembre 2026, dove i dati esistono. Un mercato con meno di 400 sedute non entra.

## Regole del test

Le stesse della v3: eventi dello stesso mercato distanti almeno 10 sedute; confronto con 200 ingressi casuali sullo stesso mercato nello stesso anno, lontani dagli eventi; eccesso con il segno dell'operazione; eventi entro 3 giorni su mercati diversi uniti in un cluster; t-test a una coda più bootstrap; correzione di Holm al 5% sulle sei ipotesi. «Non supportata» solo se la potenza a d = 0,30 è almeno 50%, altrimenti «non informativa». Il netto dei costi (cripto 0,15% per lato, altri 0,03%) e le righe per classe sono descrittivi.

## Limiti, detti prima

- **Le cripto nuove si muovono con BTC ed ETH**, che erano nella v3: i loro eventi cadono spesso negli stessi giorni. Sono mercati nuovi, ma non periodi nuovi. Azioni, materie prime e forex sono più indipendenti.
- I future continui Yahoo hanno salti ai rinnovi dei contratti, come nella v3.
- Un risultato «supportata» qui è una lettura che regge su mercati nuovi, non ancora una regola: serve poi la prova sui dati futuri.

## Conteggi prima del test

Solo eventi e cluster, senza rendimenti (`python -m bzd.v4 conta`), su 50 mercati:

| ID | Eventi | Cluster |
|---|---:|---:|
| N1 | 5584 | 646 |
| N2 | 6866 | 535 |
| N3 | 2842 | 621 |
| N4 | 3453 | 656 |
| N5 | 2507 | 583 |
| N6 | 3421 | 618 |

Con più di 500 cluster per ipotesi la potenza a d = 0,30 è vicina al 100%: se l'effetto c'è con quella forza, il test lo vede.
