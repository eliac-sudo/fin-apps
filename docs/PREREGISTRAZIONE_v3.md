# BZD — pre-registrazione v3: ogni lettura dell'app mai testata, sulla storia

Stato: **congelata, valida quando è committata in git** (la data del commit fa da prova). Scritta il 6 novembre 2026, prima di calcolare qualunque rendimento. Non è consulenza finanziaria.

Configurazione: `config/setups_v3.json`
SHA-256: `61dc10ded31083b128e27b88fb7c8befa90a1f76b9e1d5e8233f8709b344517e`

Codice: `bzd/v3.py`. `python -m bzd.v3 conta` conta eventi e cluster senza calcolare rendimenti. `python -m bzd.v3 storico --confirm` fa il test una volta sola, e rifiuta di ripartire o di partire se la configurazione non coincide con questo hash.

## Perché
L'utente ha chiesto di testare tutto ciò che l'app mostra senza un test, soprattutto le opzioni. Finora erano testati solo i setup v1 (B3), le uscite (A1) e il trend lungo (v2). Tutto il resto porta la scritta «descrive, non testato».

## Le ipotesi
Quindici, una per lettura. Ognuna dice: quando l'app mostra questa lettura, l'operazione nel suo verso rende più di un ingresso a caso sullo stesso mercato nello stesso anno.

| ID | Strumento | Lettura | Regola, come nell'app | Operazione | Orizzonte | Verso del test |
|---|---|---|---|---|---|---|
| O1 | Opzioni | care | IV a 30 giorni / previsione HAR > 1,25 | vendi straddle ATM | 30 giorni, a scadenza | maggiore |
| O2 | Opzioni | economiche | IV a 30 giorni / previsione HAR < 0,9 | compra straddle ATM | 30 giorni, a scadenza | maggiore |
| Z1 | Tag | BYZ giornaliero | punteggio degli indicatori ≤ −50 | long | 10 sedute | maggiore |
| Z2 | Tag | SZT giornaliero | punteggio degli indicatori ≥ +50 | short | 10 sedute | maggiore |
| R1 | Tecnica | reset in rialzo | trend lento al rialzo, RSI scende sotto 30 | long | 10 sedute | maggiore |
| R2 | Tecnica | reset in ribasso | trend lento al ribasso, RSI sale sopra 70 | short | 10 sedute | maggiore |
| T1 | Tensione | molto tirato in basso | tensione < 20 | long | 10 sedute | maggiore |
| T2 | Tensione | molto tirato in alto | tensione ≥ 80 | short | 10 sedute | maggiore |
| S1 | Sentiment | paura estrema | Fear & Greed ≤ 25 sulle cripto, umore ≤ 15 altrove | long | 10 sedute | maggiore |
| S2 | Sentiment | euforia estrema | Fear & Greed ≥ 75 sulle cripto, umore ≥ 85 altrove | short | 10 sedute | maggiore |
| F1 | Chi compra | i grossi comprano il dip | dip e pressione dei grossi ≥ 50 | long | 10 sedute | maggiore, contro altri giorni di dip |
| F2 | Chi compra | il retail compra il dip | dip e pressione del retail ≥ 50 | long | 10 sedute | **minore**, contro altri giorni di dip |
| M1 | Forti movimenti | movimento forte | rendimento di una seduta ≥ 3 deviazioni standard delle 90 prima | nel verso del movimento | 5 sedute | a due code |
| L1 | Livelli | test del supporto | il minimo tocca il supporto più vicino (± mezza larghezza) e la chiusura resta sopra | long | 5 sedute | maggiore |
| L2 | Livelli | test della resistenza | il massimo tocca la resistenza più vicina e la chiusura resta sotto | short | 5 sedute | maggiore |

- **F2 va al contrario** perché è la lettura che l'app suggerisce: il retail che compra il dip è il gruppo che sbaglia. M1 è a due code perché l'app dice solo che il prezzo si muove, non dove va.
- **F1 e F2** si confrontano con altri giorni di dip dello stesso mercato e anno, non con giorni qualsiasi: la domanda è se sapere chi compra aggiunge qualcosa al solo fatto di essere a un dip.

## Come si ricostruisce ogni lettura
Con le stesse funzioni dell'app, barra per barra, usando solo i dati noti a quella barra.
- **Opzioni**: il rapporto è quello dell'app (`bzd/options_report.py`), con la previsione HAR di `bzd/option_models.py` rifatta ogni giorno solo sui dati già noti. La volatilità implicita è l'indice del mercato: VIX su SPY, GVZ su GLD, OVX su USO, EVZ su EUR/USD (fino a marzo 2025), DVOL su BTC ed ETH (dal 2021). Lo straddle si apre alla chiusura del giorno dopo la lettura, prezzato con Black-Scholes al livello dell'indice, e si chiude a scadenza, dopo 21 sedute o 30 giorni sulle cripto. Il risultato è in quota del premio.
- **Tag, reset, tensione, sentiment, chi compra**: `zones.indicator_score`, `technicals.long_trend` e `RESET_RSI` con la stessa memoria (un reset alla volta finché l'RSI torna a 50), `thermo.crypto_series` e `thermo.daily_series`, `sentiment.gauge`, `flows.pressures`. Sul COT un report conta dal primo giorno in cui è pubblico.
- **Movimenti**: l'app li misura in tempo reale su 4 e 24 ore. Sulla storia ci sono solo chiusure giornaliere, quindi si usa il movimento di una seduta con la soglia a 24 ore (3 deviazioni standard).
- **Livelli**: supporti e resistenze dell'app (`technicals.swing_pool`, `shared_levels`, `pick_levels`) ricalcolati ogni 5 sedute sui dati fino a quel giorno e usati nelle 5 sedute dopo. L'app li ricalcola a ogni barra: qui un livello può arrivare con qualche seduta di ritardo.
- **Solo il giornaliero.** Il 4h, il settimanale e il mensile restano fuori, per non moltiplicare i test.

## Test
- **Periodo:** segnali dal 1° gennaio 2008 al 6 novembre 2026, o dall'inizio dei dati se dopo (cripto, DVOL, posizioni dal 2021).
- **Ingresso:** apertura della seduta dopo il segnale; opzioni alla chiusura del giorno dopo. Su uno stesso mercato due eventi della stessa ipotesi distano almeno un orizzonte, così le tenute non si sovrappongono.
- **Confronto:** per ogni evento, 200 ingressi casuali con seme fisso, stesso mercato, stesso anno, dentro il periodo, lontani dagli eventi almeno un orizzonte. Un evento con meno di 20 ingressi casuali resta fuori.
- **Cluster:** eventi di mercati diversi a 3 giorni o meno fanno un solo cluster.
- **Statistica:** test t sulla media dei cluster, nel verso indicato, con bootstrap (5.000 repliche) come controllo.
- **Correzione per 15 test: Holm**, con α di famiglia 0,05. Si riporta anche se |t| ≥ 3.
- **Tre esiti:** *supportata* se Holm la accetta. *Non supportata* solo se non lo è e la potenza a d = 0,30 è almeno del 50% (alla soglia α/15). Altrimenti *non informativa*.
- **Descrittivo, non decide nulla:** netto dei costi (0,045% di commissione e 0,02% di slippage per lato; per le opzioni uno spread ipotetico in quota del premio, scritto nella configurazione), righe per classe, e quanto avrebbe reso vendere uno straddle ogni giorno senza condizioni.

## Conteggi, prima del test
Da `python -m bzd.v3 conta`, il 6 novembre 2026: solo eventi e cluster, nessun rendimento.

| ID | Eventi | Cluster | | ID | Eventi | Cluster |
|---|---:|---:|---|---|---:|---:|
| O1 | 585 | 439 | | S1 | 1.618 | 549 |
| O2 | 161 | 137 | | S2 | 1.539 | 555 |
| Z1 | 3.335 | 723 | | F1 | 514 | 280 |
| Z2 | 3.734 | 703 | | F2 | 507 | 333 |
| R1 | 223 | 151 | | M1 | 1.413 | 512 |
| R2 | 223 | 164 | | L1 | 6.289 | 489 |
| T1 | 1.018 | 443 | | L2 | 6.332 | 479 |
| T2 | 711 | 418 | | | | |

Con almeno 137 cluster ogni ipotesi ha potenza alta a d = 0,30 anche alla soglia α/15, quindi «non supportata» si potrà dire dove serve. Molti eventi finiscono in pochi cluster perché tanti mercati toccano la stessa lettura negli stessi giorni.

## Che cosa è già stato visto
Il test non è cieco. Lo dico qui perché un risultato positivo va letto con questo in mente.
- **Tutti questi prezzi** sono già serviti a B3, alla tecnica, ai tag e alla v2.
- **Tag:** i rendimenti medi dopo BYZ e SZT su tutti i timeframe sono già stati calcolati, in modo descrittivo e con barre sovrapposte (`docs/ZONE_BYZ_SZT.md`): sul giornaliero a 5 sedute +0,02% dopo BYZ e +0,36% dopo SZT. Qui l'orizzonte è 10 sedute, ma i numeri sono legati.
- **Chi compra:** misurato su BTC che il retail si muove contro il prezzo e che dopo i dip non si vede una differenza utile (`docs/CHI_COMPRA.md`).
- **Opzioni:** è stato visto che HAR batte GARCH ed EWMA, e che su BTC ed ETH la volatilità implicita prevede meglio di HAR. Che vendere opzioni renda in media è noto in letteratura (premio per il rischio di varianza). Le soglie 0,9 e 1,25 sono scelte a giudizio, senza guardare rendimenti.
- **Reset e movimenti:** soglie scelte per la frequenza dei messaggi, non per cosa succede dopo.
- **Tensione, sentiment estremo, livelli:** nessun rendimento mai calcolato.

## Limiti
- **Opzioni sintetiche.** Gli indici di volatilità misurano tutta la curva, non solo lo strike ai soldi: il VIX sta di solito qualche punto sopra la volatilità ATM, quindi il guadagno assoluto del venditore è sovrastimato. O1 e O2 confrontano giorni con giorni dello stesso mercato, quindi questo errore conta molto meno. Niente copertura in delta, niente esercizio anticipato, niente dividendi né carry. L'app oggi legge la volatilità dalle catene vere: la storia usa l'indice, che è vicino ma non identico.
- **Mercati diversi da quelli negoziati:** future, ETF e cambi di Yahoo e Binance approssimano i mercati di Hyperliquid.
- **Tensione sui cambi:** l'app esclude la calma della volatilità dove l'indice non è più aggiornato (EVZ da marzo 2025). Il test usa la definizione di oggi anche per gli anni prima.
- **Cluster ancora dipendenti** su mercati legati, come nella v2.
- **Uno storico positivo non basta:** per diventare una regola, una lettura supportata deve poi passare un test su dati futuri.

## Che cosa non si può testare, e perché
- **Portafogli Hyperliquid:** registrati dal 6 novembre 2026, nessuno storico gratuito.
- **Conteggio di parole del sentiment e tag con il sentiment:** i testi partono dal 4 novembre 2026. Il test dei tag usa solo gli indicatori.
- **Etichette B4:** aspettano le etichette dell'utente.
- **Opzioni economiche e care contratto per contratto, GEX, max pain:** serve lo storico delle catene di opzioni, che non è gratuito.
- **Avviso «in contrasto» degli alert:** riguarda i setup v1, troppo pochi eventi per un test a parte.
