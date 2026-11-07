---
title: BYZ, la capitolazione
kind: calcolo
status: regola nuova del 7 novembre 2026, non testata
brief: Scatta solo quando un asset forte è sceso moltissimo, la volatilità si è spenta e il prezzo va di lato da settimane.
code: bzd/capitulation.py#check, bzd/capitulation.py#of
docs: docs/STATO.md
feeds: app
tab: oggi
---
## In breve
**BYZ** non è più un nome del momentum ([[zone]]): è un segnale a sé, che scatta di rado. Servono tutte e quattro le condizioni, sui prezzi giornalieri:

1. **Asset forte.** È in una lista corta (BTC, ETH, SOL, BNB, S&P 500, Nasdaq, Russell, oro, argento, rame), e il massimo da cui è sceso era il più alto dei 3 anni prima. Cambi, bond, energia e agricoli restano fuori: non salgono per anni.
2. **Capitolazione di prezzo.** Almeno −20% dal massimo degli ultimi 2 anni, e tra il 10% dei cali più profondi della sua storia.
3. **Volatilità spenta.** La volatilità a 20 sedute è al massimo metà di quella del picco del calo, e nel terzo più basso degli ultimi 2 anni.
4. **Capitolazione di tempo.** Nessun nuovo minimo da 40 sedute, e in quelle 40 sedute il prezzo oscilla al massimo per un terzo del calo.

## Dove si usa
Nella scheda Oggi, nel riquadro «BYZ: la capitolazione» e nella colonna BYZ della tabella del momentum. Nella pagina di ogni ticker c'è la lista delle quattro condizioni con i numeri.

## Quanto fidarsi
Non è testata. Le soglie sono state scelte guardando la storia, quindi quegli anni non valgono come prova. In passato è scattata su BTC tra agosto 2022 e gennaio 2023, sull'S&P 500 a giugno 2009, sul Russell nel 2023 e sull'argento nel 2012 e 2013, che poi ha continuato a scendere.
