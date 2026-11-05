# A3 — regole di uscita e calcolatore

Il calcolatore ti dice quanto comprare e dove uscire **prima** di entrare. Gli ordini li metti tu: non fa trading e non usa chiavi.

## Come si usa

Scrivi al bot su Telegram, oppure lancia `python -m bzd.plan` con le stesse parole:

```
/piano BTC 5000
/piano oro 5000 0.5 stop 3900 leva 3
```

L'ordine è `MERCATO CAPITALE RISCHIO%`, poi le opzioni `stop PREZZO`, `target R`, `leva X`, `entrata PREZZO`. Il rischio predefinito è 1%. Se lo stop è sopra il prezzo, il piano è uno short. La risposta arriva entro circa 20 secondi, qualche minuto se il sistema sta aggiornando i dati. Le richieste più vecchie di 10 minuti vengono ignorate, perché i prezzi sarebbero vecchi.

## Le regole

1. **Decidi prima quanto puoi perdere.** Predefinito 1% del capitale per trade. Sopra il 2% il piano ti avvisa.
2. **Lo stop decide la dimensione.** Stop largo, posizione piccola. La perdita allo stop resta la stessa.
3. **Stop e obiettivo vanno messi appena entri.** Così l'uscita non dipende da come ti senti in quel momento.
4. **Lo stop non si sposta mai contro di te.**
5. **All'obiettivo (3R) chiudi tutto.** Questa è la regola contro il greed: R è quanto rischi, quindi 3R è tre volte tanto.
6. **Uscita a tempo.** Se non tocchi né stop né obiettivo, esci dopo 14 giorni sulle cripto o 20 sedute sugli altri mercati.
7. **La leva serve solo a far stare la posizione nel margine.** Il piano propone la più bassa possibile, e ti ferma se la liquidazione arriverebbe prima dello stop.

Stop, obiettivo e tempo vengono dal laboratorio delle uscite (`docs/A1_USCITE.md`). Le altre regole sono buon senso di gestione del rischio: non sono state testate.

## Cosa dicono i test

Nel periodo di test sul panico cripto (`docs/B3_RISULTATI.md`, solo descrittivo):

| | Rendimento medio | Peggior 10% dei casi |
|---|---|---|
| Stop + 3R | −0.02R | −1.11R |
| Tieni senza stop | +0.31R | −3.88R |

Queste regole **non aumentano il rendimento**: tagliano le perdite peggiori e ti impediscono di restare dentro per greed, e il prezzo è un guadagno medio più basso. Nessuna delle uscite selezionate ha superato il test contro «tieni».

## Limiti

- **Stop nei gap:** può eseguire peggio del livello, e allora perdi più di quanto calcolato.
- **Costi:** sono stime (commissione 0.045% e slittamento per lato). Sui mercati `xyz` commissioni, oracolo e rischi del gestore non sono verificati.
- **Stop sui mercati non cripto:** è una percentuale calcolata sul future, perché il prezzo Hyperliquid può differire. Ricontrolla il livello sul grafico.
- **Liquidazione:** usa la formula della documentazione Hyperliquid con margine isolato. Con margine incrociato dipende da tutto il conto, e sulle posizioni grandi i livelli di margine possono cambiarla.
- **Short:** lo stop lo scegli tu. La regola di stop è stata studiata solo sui long, e nessun test copre gli short.
