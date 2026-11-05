# Tag BYZ e SZT

Il tag dice in che stato si trova un mercato su ogni timeframe. **Descrive uno stato: non è testato come segnale e non è un consiglio.**

- **BYZ** (Buy Ze dip): il mercato è molto tirato verso il basso e l'umore è di paura.
- **SZT** (Sell Ze Top): il mercato è molto tirato verso l'alto e l'umore è di euforia.
- **NTR**: nessuno dei due.

## Come si calcola

Punteggio da −100 a +100: **70% indicatori, 30% sentiment**. BYZ da −50 in giù, SZT da +50 in su.

**Indicatori:** media semplice di sei voci, ciascuna da −1 a +1: RSI, bande di Bollinger, distanza dalla media breve, distanza dalla media lunga, posizione nel range e MACD. Timeframe: 4 ore (solo cripto), giorno, settimana, mese e 12 mesi. Il 12 mesi usa le barre mensili lette su un anno.

**Sentiment:** euforia meno paura diviso il totale, sul tema del mercato. Per esempio l'oro usa i metalli preziosi. Sulle cripto fa media con il Fear & Greed. Sulle coppie come USD/JPY il segno è invertito, perché l'euforia sullo yen fa scendere la coppia.

Con meno di 10 segnali il sentiment non conta: il punteggio usa solo gli indicatori e l'app lo segnala con un asterisco. Il sentiment guarda solo le ultime 24 ore, quindi è uguale su tutti i timeframe, e il conteggio delle parole è grezzo e non validato.

## Cosa è successo in passato

Misura del 5 novembre 2026, su tutti i mercati e solo sugli indicatori, perché il sentiment non ha storico. Il numero è il rendimento rispetto alla media di quel mercato, sullo stesso orizzonte.

| Timeframe | Orizzonte | Quota BYZ | Dopo BYZ | Quota SZT | Dopo SZT |
|---|---|---|---|---|---|
| 4 ore | 24 ore | 13% | +0,02% | 14% | +0,47% |
| Giorno | 5 sedute | 15% | +0,02% | 18% | +0,36% |
| Settimana | 4 settimane | 14% | −0,43% | 20% | +1,20% |
| Mese | 3 mesi | 10% | +2,33% | 20% | −0,77% |
| 12 mesi | 3 mesi | 11% | +1,91% | 22% | +0,68% |

**Cosa vuol dire:** se il nome fosse giusto, dopo BYZ il numero sarebbe positivo e dopo SZT negativo. Succede solo sul mensile. Su 4 ore, giorno e settimana, un mercato in SZT ha continuato a salire più della sua media, e BYZ non ha dato vantaggi. Sul 12 mesi BYZ è positivo, ma anche SZT.

Non è un test: le barre si sovrappongono, molti mercati si muovono insieme, e questi dati erano già stati usati. Per dire che il tag funziona servono una pre-registrazione e dati nuovi.
