---
title: Piano
kind: calcolo
status: regole, nessun ordine
brief: Quanto comprare, dove mettere stop e obiettivo, prima di entrare. Gli ordini li metti tu a mano.
code: bzd/plan.py#build_plan, bzd/plan.py#parse_request, bzd/plan.py#liquidation, bzd/plan.py#log_plan
docs: docs/A3_REGOLE.md
data: data/alerts
feeds: app, alert-telegram
tab: piano
---
## In breve
Dato capitale, rischio (0,5%, 1% o 2%) e direzione, il piano calcola la dimensione, lo stop (da regola o dai livelli di [[tecnica]]), l'obiettivo a 3R, il margine, la liquidazione e il funding. Su Telegram si chiede con `/piano BTC 5000`.

## Da dove vengono le regole
Stop + 3R viene dal laboratorio delle uscite ([[uscite-a1]]): taglia le perdite peggiori ma rende meno del tenere. Ogni piano chiesto dal bot è registrato in `data/alerts/plans.jsonl`; quelli provati nell'app no.
