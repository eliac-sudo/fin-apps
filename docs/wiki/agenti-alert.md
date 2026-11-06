---
title: Revisione degli alert con l'LLM
kind: calcolo
status: accesa, con tetto di spesa
brief: Un modello legge i testi intorno a un alert e dà un parere citato. Non può cambiare numeri né bloccare l'alert.
code: bzd/agents.py#review_alerts, bzd/agents.py#facts_for, bzd/agents.py#check_review, bzd/agents.py#numbers_in, bzd/agents.py#spent_this_month
data: data/agents
feeds: alert-telegram
---
## Come funziona
1. `bzd/agents.py#facts_for` prepara i fatti già calcolati dal codice e i [[testi]] recenti.
2. Il modello (Opus 5.5) risponde in un formato fisso, con citazioni.
3. `bzd/agents.py#check_review` scarta la risposta se cita un testo che non esiste o usa un numero che non sta nei fatti (`bzd/agents.py#numbers_in`).

## Limiti
Tetto di spesa mensile da `.env` (`BZD_LLM_BUDGET_USD`, oggi 1,50 $); oltre, gli alert partono senza revisione. Spese in `data/agents/usage.jsonl`. La regola è in [[regole]].
