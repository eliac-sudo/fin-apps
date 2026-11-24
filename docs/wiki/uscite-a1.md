---
title: Laboratorio delle uscite (A1)
kind: verifica
status: solo periodo di calibrazione
brief: Quale regola d'uscita usare dopo un setup: stop + 3R taglia il peggio ma rende meno del tenere.
code: bzd/exits.py#simulate, bzd/exits.py#select_rule, bzd/exits.py#cut_to_calibration
docs: docs/A1_USCITE.md
feeds: piano
---
## In breve
Le regole provate sono in `config/exits_v1.json`, quella scelta in `config/exits_selected_v1.json`. Il prezzo viene tagliato alla fine del periodo di calibrazione prima di ogni simulazione (`bzd/exits.py#cut_to_calibration`), così il periodo di test non si vede. Dentro una candela si controlla prima lo stop.

Sul panico cripto, stop + 3R taglia il peggior 10% (−1,11R contro −3,88R) ma rende meno del tenere (−0,02R contro +0,31R).
