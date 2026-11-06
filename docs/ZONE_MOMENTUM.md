# Tag momentum: MOM↓ e MOM↑

Il tag dice quanto è tirato un mercato su ogni timeframe, e in che verso tende a continuare. **Non è un consiglio.**

- **MOM↓** (momentum giù): il mercato è molto tirato verso il basso. Prima si chiamava BYZ, «Buy Ze dip».
- **MOM↑** (momentum su): il mercato è molto tirato verso l'alto. Prima si chiamava SZT, «Sell Ze Top».
- **NTR**: nessuno dei due.
- **3+** accanto a MOM↑: da almeno 3 sedute di fila sul giornaliero.

## Perché il nome è cambiato

I vecchi nomi dicevano di comprare il dip e vendere il top. I test hanno detto il contrario. Nel test v3 ([V3_STORICO.md](V3_STORICO.md)), sui mercati del programma, dopo BYZ il prezzo ha continuato a scendere e dopo SZT a salire. Il test v4 ([PREREGISTRAZIONE_v4.md](PREREGISTRAZIONE_v4.md), [V4_STORICO.md](V4_STORICO.md)), fissato prima e fatto una volta su 50 mercati mai usati, lo ha confermato. In 10 sedute, rispetto a un giorno qualsiasi, dopo MOM↓ il prezzo ha fatto 0,68% peggio e dopo MOM↑ 0,63% meglio.

Quanto fidarsi:

- **È un vantaggio relativo e piccolo.** Tolti i costi, uno short dopo MOM↓ ha perso in media (−0,77%), perché i mercati in media salgono. Un long dopo MOM↑ è rimasto in pari. Serve più come filtro (non comprare in MOM↓, non vendere allo scoperto in MOM↑) che come ingresso.
- **Le versioni meno sensibili.** MOM↑ da 3 sedute di fila ha retto (N4) e l'app lo segna con «3+». MOM↓ da 3 sedute e la soglia ±70 non hanno retto, e non si mostrano.
- **Cosa è stato testato:** solo il giornaliero e solo gli indicatori, senza sentiment. Gli altri timeframe sono misure descrittive, qui sotto.
- **Agli estremi e sul mensile i vecchi nomi non tornano.** Il test v5 ([V5_STORICO.md](V5_STORICO.md)), su 99 azioni mai usate, ha provato BYZ long e SZT short a ±70 sul giornaliero e a ±50 sul mensile: nessuna regge. Agli estremi c'è un piccolo ritorno indietro, ma non supera la correzione per i confronti multipli.
- **La stella ★** (momentum d'accordo con il trend di fondo) non è testata.
- Prima di diventare una regola serve la prova sui dati futuri.

## Come si calcola

Punteggio da −100 a +100: **70% indicatori, 30% sentiment**. MOM↓ da −50 in giù, MOM↑ da +50 in su.

**Indicatori:** media semplice di sei voci, ciascuna da −1 a +1: RSI, bande di Bollinger, distanza dalla media breve, distanza dalla media lunga, posizione nel range e MACD. Timeframe: 4 ore (solo cripto), giorno, settimana, mese e 12 mesi. Il 12 mesi usa le barre mensili lette su un anno.

**Sentiment:** euforia meno paura diviso il totale, sul tema del mercato. Per esempio l'oro usa i metalli preziosi. Sulle cripto fa media con il Fear & Greed. Sulle coppie come USD/JPY il segno è invertito, perché l'euforia sullo yen fa scendere la coppia.

Con meno di 10 segnali il sentiment non conta: il punteggio usa solo gli indicatori e l'app lo segnala con un asterisco. Il sentiment guarda solo le ultime 24 ore, quindi è uguale su tutti i timeframe, e il conteggio delle parole è grezzo e non validato.

## Cosa è successo in passato

Misura del 5 novembre 2026, su tutti i mercati e solo sugli indicatori, perché il sentiment non ha storico. Il numero è il rendimento rispetto alla media di quel mercato, sullo stesso orizzonte.

| Timeframe | Orizzonte | Quota MOM↓ | Dopo MOM↓ | Quota MOM↑ | Dopo MOM↑ |
|---|---|---|---|---|---|
| 4 ore | 24 ore | 13% | +0,02% | 14% | +0,47% |
| Giorno | 5 sedute | 15% | +0,02% | 18% | +0,36% |
| Settimana | 4 settimane | 14% | −0,43% | 20% | +1,20% |
| Mese | 3 mesi | 10% | +2,33% | 20% | −0,77% |
| 12 mesi | 3 mesi | 11% | +1,91% | 22% | +0,68% |

**Cosa vuol dire:** con i vecchi nomi, dopo BYZ il numero doveva essere positivo e dopo SZT negativo, e succedeva solo sul mensile. Su 4 ore, giorno e settimana, dopo MOM↑ il prezzo ha continuato a salire più della sua media. Sul mensile invece il prezzo è tornato indietro: lì il momentum non vale. Sul 12 mesi i due numeri sono positivi tutti e due.

Non è un test: le barre si sovrappongono, molti mercati si muovono insieme, e questi dati erano già stati usati. Il test vero è il v4, sul giornaliero.
