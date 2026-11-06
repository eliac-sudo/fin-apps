---
title: Setup v1 congelati
kind: calcolo
status: congelati, testati in B3
brief: Panico, squeeze e surriscaldamento: le regole fissate prima del test, con condizioni di conferma.
code: bzd/setups.py#crypto_setups, bzd/setups.py#daily_setups, bzd/setups.py#apply_rule, bzd/events.py#first_of_runs, bzd/alerts.py#detect
docs: docs/PREREGISTRAZIONE_v1.md
feeds: alert-telegram, test-b3
---
## In breve
Le regole stanno in `config/setups_v1.json` e non si cambiano: l'impronta del file (`bzd/setups.py#config_hash`) prova che sono quelle del test.
- **Panico**: calo violento per gli standard del mercato.
- **Squeeze**: salita forte, spesso con chi era short costretto a chiudere.
- **Surriscaldamento**: salita con leva e funding già alti.

Ogni setup ha condizioni di conferma (leva ripulita, funding ≤ 0…). Il punteggio le conta con lo stesso peso; negli alert compare come «Conferme: 0 su 3».

## Nota sul COT
Su USD/JPY, USD/CHF e USD/CAD il segno COT è letto al contrario: cambierebbe la conferma in 191 eventi su 558. L'esito di [[test-b3]] non cambia. Vedi [[cot]].
