---
title: Testi
kind: calcolo
status: preparazione
brief: Trasforma le risposte grezze di notizie e social in testi datati, senza doppioni, ognuno collegato al suo file.
code: bzd/texts.py#load_items, bzd/texts.py#parse_job, bzd/texts.py#select_for, bzd/texts.py#TOPICS
feeds: sentiment, agenti-alert, etichette
---
## In breve
Ogni fonte ha il suo formato (RSS, JSON di Reddit, pagine Telegram…). `bzd/texts.py#parse_job` li riporta a una forma sola: testo, ora, fonte, indirizzo. Al massimo 600 caratteri per testo, così un post lungo non domina.

## Temi
`bzd/texts.py#TOPICS` assegna ogni testo a un tema (Cripto, Azioni, Oro, Yen…) con parole chiave. Le stesse divisioni le usano il [[sentiment]] e le [[zone]].
