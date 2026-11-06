---
title: Test B3
kind: verifica
status: eseguito una volta, non si rifà
brief: L'unico test pre-registrato dei setup v1: su 15 test passa solo il panico cripto, di poco.
code: bzd/b3.py#run_all, bzd/b3.py#cluster_test, bzd/b3.py#event_excess, bzd/b3.py#outcome
docs: docs/B3_RISULTATI.md, docs/PREREGISTRAZIONE_v1.md
feeds: app, alert-telegram
tab: test
---
## In breve
Confronta i rendimenti dopo ogni setup con quelli di giorni qualsiasi, raggruppando gli eventi vicini in cluster. Rifiuta di girare una seconda volta: guardare di nuovo non sarebbe più un test pulito.

## Risultato
Solo il panico cripto: +0,75%, e non alla soglia più severa. Gli alert riportano sempre questo esito accanto alla direzione (vedi [[regole]]). Le soglie sono in `config/validation_v1.json`.
