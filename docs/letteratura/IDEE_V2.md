# Bozze di setup v2

Scritte dal supervisore (`python -m bzd.research supervisore`) a partire da `NOTE.md`, dopo aver ricontrollato ogni nota sul suo abstract. **Nessuna è testata.** Non entrano negli alert né nei setup congelati: ognuna diventa un setup solo se passa una pre-registrazione v2 su dati raccolti dopo la sua data.

Generate il 2026-11-06 con claude-opus-5-5.

## Revisione delle note

Il supervisore ha riletto 13 note sul loro abstract: 10 reggono.
- **almgren-chriss-2000**, forzata: L'abstract è un modello teorico di esecuzione, senza dati né mercati indicati. L'idea di stimare i costi di uscita su cripto e forex con dati di volume va oltre l'abstract. Inoltre BZD non ha dati di volume nel suo elenco. Anche il limite «riguarda principalmente i mercati azionari» non è nell'abstract. Abstract: «The authors consider the execution of portfolio transactions with the aim of minimizing a combination of volatility risk and transaction costs arising from permanent and temporary market impact.».
- **baker-wurgler-2006**, forzata: Il risultato riguarda categorie di singole azioni e proxy di sentiment che l'abstract non definisce. L'idea usa il posizionamento di retail o fondi come proxy di sentiment, cosa che l'abstract non sostiene. Presuppone anche panieri di titoli che BZD non ha. Abstract: «we find that when beginning‐of‐period proxies for sentiment are low, subsequent returns are relatively high for small stocks, young stocks, high volatility stocks, unprofitable stocks, non‐dividend‐paying stocks, extreme growth stocks, and distressed stocks.».
- **gu-kelly-xiu-2020**, forzata: La pertinenza dice che il confronto è tutto out-of-sample, ma l'abstract non lo dice. L'idea estende il risultato a cripto e a un orizzonte mensile, mentre l'abstract non indica né asset né orizzonte. BZD inoltre non ha una variabile di liquidità. Abstract: «We perform a comparative analysis of machine learning methods for the canonical problem of empirical asset pricing: measuring asset risk premiums.».

## 1. Trend lungo su cambi e materie prime, con azioni come controllo

Secondo la rassegna, le regole tecniche hanno reso nei cambi e nei futures ma non nelle azioni. Ipotesi: quando trend_lungo è +1, il rendimento a 4 settimane in fx e commodities supera quello di ingressi casuali, e lo stesso non vale per le equities. Il test su dati futuri risponde al problema del data snooping segnalato dalla rassegna.

- **Da:** park-irwin-2007, harvey-liu-zhu-2016, bailey-lopez-de-prado-2014
- **Mercati:** fx, commodities
- **Regola:** trend_lungo >= 1
- **Orizzonte:** 4 settimane
- **Confronto:** Ingressi casuali sullo stesso mercato e nello stesso periodo, con lo stesso orizzonte. Stessa regola applicata alle equities come controllo negativo.
- **La smentisce:** Smentita se, su dati futuri, il rendimento a 4 settimane dopo il segnale in fx e commodities non supera gli ingressi casuali con una t-statistic sopra 3.0. È smentita anche se l'effetto è uguale o più forte nelle equities.
- **Dati che mancano:** Costi di transazione per ogni mercato; Definizione esatta della media lunga usata da trend_lungo, da fissare prima del test
- **Rischi:** La rassegna trova profitti solo fino ai primi anni '90: l'effetto potrebbe essere svanito; Il segnale resta attivo a lungo: gli ingressi si sovrappongono e le osservazioni indipendenti sono poche; Molti mercati e varianti aumentano i falsi positivi: niente varianti aggiunte dopo la pre-registrazione
