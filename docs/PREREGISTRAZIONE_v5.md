# Pre-registrazione v5: BYZ e SZT agli estremi e sul mensile, su singole azioni

Scritta il 6 novembre 2026, prima di calcolare qualunque rendimento su questi titoli. Configurazione `config/setups_v5.json`, SHA-256 `5b63d41eef6d1871ab16b9c571a1ffb38a5221ecace16a5da884a522f434ae83`. Codice `bzd/v5.py`. Il test si fa una volta sola: `python -m bzd.v5 storico --confirm` rifiuta di ripartire.

## Perché

Il v4 ([V4_STORICO.md](V4_STORICO.md)) ha confermato il momentum dopo i tag sul giornaliero, e per questo BYZ e SZT sono diventati MOM↓ e MOM↑. Due osservazioni però, fatte dopo, dicono che il vecchio nome potrebbe valere altrove:

- nel v4, con punteggio sotto −70, il prezzo è andato contro lo short: un rimbalzo (t circa −2,6);
- nella misura descrittiva del 5 novembre ([ZONE_MOMENTUM.md](ZONE_MOMENTUM.md)) i nomi andavano nel verso giusto solo sul mensile.

Qui si provano come dice il nome, su mercati mai usati.

## Ipotesi

| ID | Lettura | Regola | Operazione |
|---|---|---|---|
| E1 | BYZ estremo giornaliero | punteggio 1d ≤ −70 | long, 10 sedute |
| E2 | SZT estremo giornaliero | punteggio 1d ≥ +70 | short, 10 sedute |
| E3 | BYZ mensile | punteggio 1M ≤ −50 a fine mese | long, 3 mesi |
| E4 | SZT mensile | punteggio 1M ≥ +50 a fine mese | short, 3 mesi |

E2 è nella famiglia per simmetria: nel v4 a +70 il prezzo ha continuato un po' a salire, quindi ci si aspetta «non supportata». Punteggio: `bzd/zones.py#indicator_score`, solo indicatori, impostazioni 1d sulle sedute e 1M sui mesi. Il mese si costruisce dalle sedute; il mese in corso non entra.

## Mercati

100 grandi azioni USA della configurazione, da Yahoo: nessuna è mai stata usata dal programma. MMC non si scarica (Yahoo risponde 404), quindi restano 99 titoli. Periodo dal 1° gennaio 2008 al 6 novembre 2026.

## Regole del test

- **Giornaliero:** come v3 e v4. Eventi dello stesso titolo distanti almeno 10 sedute; ingresso all'apertura della seduta dopo; 200 ingressi casuali sullo stesso titolo nello stesso anno, lontani dagli eventi.
- **Mensile:** eventi distanti almeno 3 mesi, ingresso all'apertura del mese dopo. Gli ingressi casuali vengono dallo stesso titolo su tutto il periodo, perché un anno ha solo 12 mesi.
- **Statistica:** eventi entro 3 giorni su titoli diversi uniti in un cluster, quindi un mese in cui molti titoli sono in BYZ conta una volta sola. t-test a una coda più bootstrap, Holm al 5% sulle quattro. «Non supportata» solo con potenza almeno 50% a d = 0,30, altrimenti «non informativa».
- **Descrittivo:** il netto, con uno slittamento dello 0,05% per lato.

## Limiti, detti prima

- **Titoli nuovi, periodi no:** le azioni si muovono con l'S&P 500, che è tra i mercati del programma.
- **I grandi titoli di oggi sono i vincitori di ieri** (survivorship): favoriscono i long in assoluto. Il confronto con ingressi casuali sullo stesso titolo toglie gran parte di questo effetto, non tutto.
- **Sul mensile i cluster sono pochi**, perché i titoli vanno in BYZ negli stessi mesi: la potenza può essere bassa.

## Conteggi prima del test

Solo eventi e cluster, senza rendimenti (`python -m bzd.v5 conta`), su 99 titoli:

| ID | Eventi | Cluster |
|---|---:|---:|
| E1 | 4063 | 564 |
| E2 | 10336 | 455 |
| E3 | 498 | 135 |
| E4 | 3122 | 217 |

Anche il mensile ha più di 100 cluster: a d = 0,30 la potenza resta alta.
