---
title: Storico
kind: raccolta
status: aggiornato dagli alert
brief: Le serie lunghe e pulite di ogni mercato, una tabella per serie, aggiornate ogni 4 ore sulle cripto e ogni giorno sul resto.
code: bzd/history.py#refresh_crypto, bzd/history.py#refresh_daily, bzd/history.py#save, bzd/alerts.py#cycle
data: data/hist/crypto, data/hist/tradfi, data/hist/cot, data/hist/positions, data/hist/vol, data/hist/macro
feeds: tensione, tecnica, chi-compra, sentiment, setup-v1, opzioni, test-b3, v2, piano
fresh: daily
---
## In breve
Il [[recorder]] salva risposte grezze; lo storico le trasforma in tabelle pulite (`data/hist/<gruppo>/<serie>.csv.gz`) su cui lavorano tutti i calcoli.

## Come funziona
- La prima volta `python -m bzd.history get` scarica anni di dati. Le risposte grezze vanno in `data/hist/raw` con l'impronta in `data/hist/manifest.jsonl`.
- Dopo, il servizio degli alert chiama `bzd/history.py#refresh_crypto` a ogni chiusura di 4 ore e `bzd/history.py#refresh_daily` una volta al giorno (`bzd/alerts.py#cycle`). Il COT si aggiorna una volta a settimana.
- `python -m bzd.history coverage` dice da quando parte ogni serie.

## Quanto fidarsi
Se il servizio degli alert è fermo, lo storico smette di aggiornarsi e tutte le schede mostrano dati vecchi. L'app lo segnala in alto.
