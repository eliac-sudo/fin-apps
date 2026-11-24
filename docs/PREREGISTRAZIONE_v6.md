# Pre-registrazione v6: liquidità e proiezioni della Fed

Scritta il 24 novembre 2026, prima di calcolare qualunque rendimento dopo queste letture. Configurazione `config/setups_v6.json`, SHA-256 `5937723c11b1f12b23afea19de00a6a6c1baa7dbfef54225871629e9acb7ea7d`. Codice `bzd/v6.py`. Il test si fa una volta sola: `python -m bzd.v6 storico --confirm` rifiuta di ripartire.

## Perché

Il 24 novembre l'app ha aggiunto la liquidità ([wiki](wiki/liquidita.md)) e le previsioni ([wiki](wiki/previsioni.md)). Sono letture che molti usano per decidere, ma qui nessuna è mai stata confrontata con i prezzi. Si provano quelle che hanno abbastanza storico gratuito e che non usano numeri rivisti dopo.

## Ipotesi

| ID | Lettura | Regola | Mercati | Operazione |
|---|---|---|---|---|
| L1 | Liquidità netta della Fed in forte aumento | variazione a 13 settimane di bilancio − conto del Tesoro − reverse repo nel terzo più alto delle 156 settimane prima | S&P, Nasdaq, Russell, oro, rame, BTC, ETH | long, 20 sedute |
| L2 | Stablecoin in forte aumento | crescita a 30 giorni dell'offerta nel terzo più alto delle 156 settimane prima | le 9 cripto | long, 20 sedute |
| L3 | Dollaro in forte rialzo | variazione a 13 settimane del dollaro ampio (DTWEXBGS) nel terzo più alto delle 156 settimane prima | come L1 | short, 20 sedute |
| L4 | Impatto alto: il mercato si scambia male | Amihud di 20 sedute al 90° percentile o più dei 3 anni prima, sullo stesso mercato | 15 futures con volumi e 9 cripto | long, 10 sedute |
| F1 | Fed più dura nelle proiezioni | mediana del tasso a fine anno dopo salita di almeno 0,25 punti rispetto all'edizione prima | S&P, Nasdaq, Treasury 10 anni | short, 20 sedute |

L4 è la scommessa del premio di liquidità: quando scambiare costa, chi compra viene pagato. L1, L2 e L3 sono il racconto comune «più liquidità, più prezzi». F1 è «una Fed più dura fa scendere azioni e bond». Il verso di ognuna è scelto prima.

## Dati e date

- Ogni lettura macro è datata quando era pubblica: bilancio della Fed e conto del Tesoro il giorno dopo il mercoledì (+2 giorni per sicurezza), stablecoin +1 giorno, dollaro +7 giorni (esce il lunedì della settimana dopo), proiezioni della Fed il giorno della riunione alle 14 di New York. L'ingresso è all'apertura della seduta dopo la prima seduta da quella data.
- Le stablecoin partono a fine 2017; con 3 anni di confronto i primi eventi sono del 2021.
- Le cripto vengono dalle barre a 4 ore di Binance, dal 2019, unite per giorno (solo giorni completi).
- Periodo dal 1° gennaio 2006 al 20 novembre 2026.

## Regole del test

Come v3, v4 e v5. Eventi dello stesso mercato distanti almeno l'orizzonte; 200 ingressi casuali sullo stesso mercato nello stesso anno, lontani dagli eventi; eventi entro 3 giorni su mercati diversi uniti in un cluster, quindi una settimana di liquidità in aumento conta una volta sola anche se tocca 7 mercati. t-test a una coda più bootstrap, Holm al 5% sulle cinque. «Non supportata» solo con potenza almeno 50% a d = 0,30, altrimenti «non informativa». Netto con uno slittamento dello 0,05% per lato.

## Limiti, detti prima

- **Non sono mercati nuovi:** futures e cripto sono quelli che il programma usa da sempre. Una lettura supportata qui va riprovata sui dati futuri.
- **Versioni di oggi:** bilancio, conto del Tesoro, reverse repo e dollaro sono le serie di FRED come sono oggi. Si correggono poco, ma non sono le versioni di allora.
- **Esclusi per questo:** l'indice delle condizioni finanziarie di Chicago, ricalcolato ogni settimana all'indietro; lo spread high yield, che FRED dà gratis solo per 3 anni; Kalshi, Polymarket e OCSE, senza storico gratuito.
- **Pochi cluster:** le letture macro sono le stesse per tutti i mercati, quindi i cluster sono le settimane, e F1 ha solo le edizioni della Fed dal 2015. Per F1 la potenza sarà bassa.
- **Volumi dei futures:** quelli del contratto principale di Yahoo, che saltano nei giorni del cambio di scadenza; per questo l'impatto è una media di 20 sedute.

## Conteggi prima del test

Solo eventi e cluster, senza rendimenti (`python -m bzd.v6 conta`):

| ID | Eventi | Cluster | Primo evento |
|---|---:|---:|---|
| L1 | 572 | 151 | 28 aprile 2006 |
| L2 | 261 | 29 | 14 gennaio 2021 |
| L3 | 503 | 120 | 8 aprile 2009 |
| L4 | 926 | 503 | 27 giugno 2006 |
| F1 | 36 | 12 | 14 dicembre 2016 |

Su 24 mercati. L2 e F1 hanno meno di 30 cluster: con ogni probabilità usciranno «non informative», e va bene così, perché lo si dice prima.
