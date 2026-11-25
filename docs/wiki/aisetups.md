---
title: AIsetups
kind: calcolo
status: due volte al giorno sul server, a pagamento entro il tetto
brief: Haiku legge ciò che mostra l'app e scrive 15 candidati; il codice tiene i 5 migliori (2 breve, 2 medio, 1 lungo), li cambia solo se ha senso e li segue nel tempo.
code: bzd/aisetups.py#context, bzd/aisetups.py#screen, bzd/aisetups.py#score, bzd/aisetups.py#pick, bzd/aisetups.py#ask, bzd/aisetups.py#run, bzd/aisetups.py#follow, bzd/aisetups.py#view
fresh: 12 ore
---
## Come funziona
Il timer `bzd-aisetups` sul server lancia `python -m bzd.aisetups run --paga` alle 06:30 e alle 13:30 UTC.
1. `bzd/aisetups.py#context` prende i dati dell'[[app]] dal suo indirizzo locale e li riduce a ciò che serve: prezzi, forza, momentum, trend, RSI, supporti e resistenze, [[chi-compra]], [[opzioni]], [[sentiment]], alert recenti e l'esito dei test.
2. Dal 25 novembre 2026 Haiku scrive 15 candidati: 6 di breve (1–10 giorni), 6 di medio (2–8 settimane), 3 di lungo (3–12 mesi), ognuno con tesi, fatti, invalidazione, obiettivo, rischi, il test che lo sostiene e una convinzione da 1 a 5. Giudica anche le idee già in bacheca: «valida» o «superata», con il motivo.
3. `bzd/aisetups.py#screen` scarta un candidato, non tutto il giro, se il mercato non è dell'app, se invalidazione o obiettivo stanno dalla parte sbagliata del prezzo, se l'obiettivo è più vicino dell'invalidazione, se cita un test che non ha retto o un numero che l'app non mostra. Il giro fallisce solo se restano meno di 2-2-1 candidati validi; allora c'è un secondo tentativo con i problemi elencati.
4. `bzd/aisetups.py#score` dà a ogni candidato valido un punteggio: convinzione + rapporto tra guadagno e rischio (al massimo 3) + 2 se lo sostiene un test che ha retto.
5. `bzd/aisetups.py#pick` decide la bacheca: 5 idee, 2-2-1, un mercato ciascuna. Un'idea resta finché tocca obiettivo o invalidazione o finisce il suo orizzonte. Si cambia prima solo se il modello la dice superata e c'è un candidato per sostituirla, o se un candidato dello stesso orizzonte ha almeno 2 punti in più (`REPLACE_MARGIN`). Un candidato sullo stesso mercato e lato di un'idea in bacheca la conferma, non la duplica. La bacheca sta in `attivi.json`.
6. `bzd/aisetups.py#follow` segue ogni idea una volta sola, dal giro in cui è entrata: si chiude quando il prezzo letto tocca invalidazione o obiettivo, alla fine dell'orizzonte, o quando viene sostituita (al prezzo di quel momento). Gli esiti chiusi restano fermi e non si riaprono (file `outcomes.json` nella cartella dei dati di AIsetups, sul server).

## Limiti
Sono idee, non segnali: quasi nessuna lettura dell'app ha retto ai test ([[test-b3]], [[v3]], [[v4]], [[v5]]), e un modello che sceglie tra quelle letture non ha un vantaggio dimostrato. La tabella «Come sono andate» è l'unico modo per capire se valgono qualcosa. Il prezzo è controllato a ogni lettura, non a ogni tick. Costo: circa 0,01 $ a giro con 15 candidati, dentro il tetto condiviso degli agenti. Non manda ordini.
