---
title: FRED, Fear & Greed, Wikipedia
kind: fonte
status: dato pubblico
brief: Tassi e spread dalla Fed di St. Louis, l'indice Fear & Greed cripto, le visite a Wikipedia come misura di attenzione.
code: bzd/history.py#get_macro, bzd/history.py#get_attention, bzd/history.py#get_macro_fng_and_attention
data: data/hist/macro, data/hist/attention, data/raw/macro_fng
feeds: storico, recorder
---
## In breve
- **FRED**: tassi a 2 e 10 anni, tasso Fed, spread high yield, dollaro, indici di volatilità. In `data/hist/macro`.
- **Fear & Greed** di alternative.me: un numero al giorno per tutto il mercato cripto, base del [[sentiment]] storico cripto.
- **Wikipedia**: visite giornaliere a pagine come «Bitcoin» o «Inflation», in `data/hist/attention`. L'app le mostra come attenzione del pubblico.

## Quanto fidarsi
Fear & Greed è un indice di terzi con una ricetta non del tutto pubblica. Google Trends storico blocca le richieste automatiche e non va forzato: si usa solo il feed delle tendenze del giorno.
