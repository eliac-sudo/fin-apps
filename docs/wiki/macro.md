---
title: FRED, Fear & Greed, Wikipedia
kind: fonte
status: dato pubblico
brief: 58 serie FRED (tassi, attese d'inflazione, credito, liquidità, economia, materie prime), l'indice Fear & Greed cripto, le visite a Wikipedia.
code: bzd/history.py#get_macro, bzd/history.py#refresh_macro, bzd/jobs.py#macro_jobs, bzd/history.py#get_attention, bzd/history.py#get_macro_fng_and_attention
data: data/hist/macro, data/hist/attention, data/raw/macro_fng
feeds: storico, recorder
---
## In breve
- **FRED**: 58 serie in `data/hist/macro`, divise per tema in `bzd/jobs.py` (`FRED_SERIES`): curva dei Treasury da 3 mesi a 30 anni, tasso reale, premio a termine, SOFR, mutui; attese d'inflazione dai mercati, dall'Università del Michigan e dalla Fed di Cleveland; spread di credito USA ed europei, condizioni finanziarie e stress; bilancio della Fed, reverse repo, conto del Tesoro, M2; richieste di sussidio, disoccupazione, occupati, inflazione, produzione, vendite, fiducia, case, PIL, regola di Sahm e probabilità di recessione; dollaro e indici di volatilità; petrolio, gas, rame; tasso BCE e bond a 10 anni di Germania, Italia, Regno Unito e Giappone. Ogni giorno si riscaricano gli ultimi 400 giorni, così entrano anche le revisioni. Le previsioni della Fed stanno in [[previsioni]].
- **Altro ogni giorno nel recorder**: debito pubblico USA (Tesoro), tassi di riferimento della Fed di New York, offerta di stablecoin e valore bloccato nella DeFi (DefiLlama).
- **Fear & Greed** di alternative.me: un numero al giorno per tutto il mercato cripto, base del [[sentiment]] storico cripto.
- **Wikipedia**: visite giornaliere a pagine come «Bitcoin» o «Inflation», in `data/hist/attention`. L'app le mostra come attenzione del pubblico.

## Quanto fidarsi
Fear & Greed è un indice di terzi con una ricetta non del tutto pubblica. Google Trends storico blocca le richieste automatiche e non va forzato: si usa solo il feed delle tendenze del giorno.
