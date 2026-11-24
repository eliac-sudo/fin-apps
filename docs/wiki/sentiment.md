---
title: Sentiment
kind: calcolo
status: non validato, in corso
brief: Paura ed euforia: storico da Fear & Greed e COT, più il conteggio di parole sui testi dal 4 novembre 2026.
code: bzd/sentiment.py#market_view, bzd/sentiment.py#gauge, bzd/sentiment.py#count_days, bzd/thermo.py#FEAR, bzd/thermo.py#GREED, bzd/snapshot.py#sentiment_part
data: data/sentiment
feeds: zone, app
tab: sentiment
---
## In breve
Due letture diverse:
- **Storico**: sulle cripto l'indice Fear & Greed; sugli altri mercati le posizioni degli speculatori nel COT e la calma dell'indice di volatilità, ognuno come percentile del proprio passato. Gli estremi si vedono sul grafico del prezzo.
- **Parole**: quante parole di paura (`bzd/thermo.py#FEAR`) e di euforia (`bzd/thermo.py#GREED`) ci sono nei testi delle ultime 24 ore, per tema. Sotto 10 segnali vale «pochi segnali».

## Quanto fidarsi
Il conteggio di parole è grezzo: sui bond «rally» conta come euforia anche quando vuol dire solo rendimenti in calo. Le 100 [[etichette]] servono a misurare se legge i testi come una persona. Nessun test su cosa succede dopo un estremo.
