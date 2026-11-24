---
title: AIsetups
kind: calcolo
status: due volte al giorno sul server, a pagamento entro il tetto
brief: Haiku legge ciò che mostra l'app e propone 5 operazioni da approfondire (2 breve, 2 medio, 1 lungo); il codice le controlla e le segue nel tempo.
code: bzd/aisetups.py#context, bzd/aisetups.py#check, bzd/aisetups.py#ask, bzd/aisetups.py#run, bzd/aisetups.py#follow, bzd/aisetups.py#view
fresh: 12 ore
---
## Come funziona
Il timer `bzd-aisetups` sul server lancia `python -m bzd.aisetups run --paga` alle 06:30 e alle 13:30 UTC.
1. `bzd/aisetups.py#context` prende i dati dell'[[app]] dal suo indirizzo locale e li riduce a ciò che serve: prezzi, forza, momentum, trend, RSI, supporti e resistenze, [[chi-compra]], [[opzioni]], [[sentiment]], alert recenti e l'esito dei test.
2. Haiku propone 5 operazioni: 2 di breve (1–10 giorni), 2 di medio (2–8 settimane), 1 di lungo (3–12 mesi), ognuna con tesi, fatti, invalidazione, obiettivo, rischi e il test che la sostiene.
3. `bzd/aisetups.py#check` scarta la risposta se i periodi non sono 2-2-1, se un mercato non è dell'app, se invalidazione o obiettivo stanno dalla parte sbagliata del prezzo, se cita un test che non ha retto o un numero che l'app non mostra. Un solo secondo tentativo, con i problemi elencati.
4. `bzd/aisetups.py#follow` segue ogni proposta: si chiude quando il prezzo letto tocca invalidazione o obiettivo, o alla fine dell'orizzonte. Gli esiti chiusi restano fermi e non si riaprono (file `outcomes.json` nella cartella dei dati di AIsetups, sul server).

## Limiti
Sono idee, non segnali: quasi nessuna lettura dell'app ha retto ai test ([[test-b3]], [[v3]], [[v4]], [[v5]]), e un modello che sceglie tra quelle letture non ha un vantaggio dimostrato. La tabella «Come sono andate» è l'unico modo per capire se valgono qualcosa. Il prezzo è controllato a ogni lettura, non a ogni tick. Costo: circa 0,004 $ a giro, dentro il tetto condiviso degli agenti. Non manda ordini.
