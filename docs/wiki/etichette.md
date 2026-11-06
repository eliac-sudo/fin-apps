---
title: Etichette di sentiment (B4)
kind: calcolo
status: aspetta le tue etichette
brief: 100 testi da etichettare a mano per misurare se il conteggio di parole legge come una persona.
code: bzd/labels.py#prepare, bzd/labels.py#next_text, bzd/labels.py#save_label, bzd/labels.py#kappa
data: data/sentiment
feeds: sentiment
tab: sentiment
---
## In breve
I 100 testi sono stati scelti una volta sola il 6 novembre con un seme fisso: 25 che le parole leggono come paura, 25 come euforia, 50 senza. Si etichettano nella scheda Sentiment. `python -m bzd.labels confronta` calcola l'accordo (kappa di Cohen): sotto 0,6 il conteggio di parole non è affidabile.
