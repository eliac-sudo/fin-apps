# BZD — pre-registrazione v2: trend lungo su cambi e materie prime

Stato: **congelata, valida quando è committata in git** (la data del commit fa da prova). Non è consulenza finanziaria.

Configurazione: `config/setups_v2.json`
SHA-256: `eeda9626349c8e04f2595259610bb5ac85fa965d2afdb0029e8af4084a90433a`

Codice: `bzd/v2.py`. `python -m bzd.v2 stato` conta gli eventi e dice quando il test è dovuto, senza calcolare rendimenti. `python -m bzd.v2 test --confirm` fa il test una volta sola, e rifiuta di partire prima del tempo, una seconda volta o se la configurazione non coincide con questo hash.

## Da dove viene
È la bozza 1 del supervisore (`docs/letteratura/IDEE_V2.md`, 6 novembre 2026), nata dalla rassegna di Park e Irwin sull'analisi tecnica: le regole di trend hanno reso su cambi e futures, non sulle azioni. Il supervisore stesso segnala che quei profitti si vedono soprattutto fino ai primi anni '90, quindi l'effetto può essere sparito.

## Che cosa è già stato visto
- **Rendimenti dopo gli incroci della media a 200 sedute: mai calcolati in BZD**, in nessun periodo. Ma la letteratura li ha studiati a fondo, ed è da lì che nasce l'idea: non è un'ipotesi ignara.
- **Visti solo i conteggi** degli eventi dal 2015, per stimare la durata del test e scegliere la finestra dei cluster.
- **Tutti i dati di prezzo fino al 6 novembre 2026 sono già stati usati** per altro (B3, tecnica, tag). Per questo il test usa solo eventi dal 9 novembre 2026 in poi.

## Regola
- **Barra:** giornaliera, chiusura dei future o dei cambi su Yahoo, gli stessi dati della v1.
- **Media:** semplice a 200 sedute. La bozza lasciava aperta la lunghezza: 200 è la scelta più comune in letteratura, fissata qui prima di vedere qualunque rendimento.
- **Evento:** la chiusura passa sopra la media dopo una chiusura sotto o uguale. Fra due eventi dello stesso mercato devono passare almeno 20 sedute, così i periodi di tenuta non si sovrappongono.
- **Ingresso:** apertura della seduta dopo l'evento. **Uscita:** chiusura della 20ª seduta dall'ingresso, circa 4 settimane.
- **Solo long**, come nella bozza. Contare anche gli incroci al ribasso aggiungeva solo il 10% di cluster, quindi non vale la deviazione.
- **Mercati primari:** 6 cambi (EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CHF, USD/CAD) e 8 materie prime (petrolio, gas, oro, argento, rame, mais, grano, soia).
- **Controllo:** S&P 500, Nasdaq 100 e Russell 2000.
- **Primo evento valido:** 9 novembre 2026.

## Ipotesi primaria
| ID | Ipotesi | Direzione |
|---|---|---|
| **T1** | Dopo un incrocio al rialzo della media a 200 sedute, il rendimento a 20 sedute su cambi e materie prime batte quello di ingressi casuali | maggiore |

- **Confronto:** per ogni evento, 200 ingressi casuali con seme fisso, sullo stesso mercato, nello stesso anno solare, solo dal 9 novembre 2026 in poi e lontani dagli eventi di almeno 20 sedute. Si usa l'eccesso rispetto alla loro media. Un evento con meno di 20 ingressi casuali disponibili resta fuori.
- **Cluster:** eventi di cambi e materie prime insieme, fusi se distano 3 giorni o meno. Un movimento del dollaro può far scattare insieme diversi cambi e l'oro, e così conta una volta sola.
- **Statistica:** test t unilaterale sulla media dei cluster, con bootstrap dei cluster (5.000 repliche) come controllo.
- **Soglia:** α = 0,01 unilaterale. È un'unica ipotesi, ma nasce da una letteratura che ha provato molte regole, quindi la soglia è più severa di 0,05. Si riporta anche se t ≥ 3, la soglia che la bozza chiedeva sulla scia di Harvey, Liu e Zhu.
- **Tre esiti:** *supportata* se p < 0,01. *Non supportata* solo se non significativa con potenza ≥ 50% a d = 0,30. Altrimenti *non informativa*.

## Quando si fa il test
**Una volta sola**, al primo controllo in cui ci sono almeno **100 cluster** con l'orizzonte di 20 sedute già concluso, oppure il **30 novembre 2030** se i cluster sono meno. Prima di allora nessun rendimento viene calcolato: niente sguardi intermedi, niente stop anticipato se «va bene».

Durata attesa, dai conteggi dal 2015: circa 27 cluster all'anno, quindi i 100 cluster arrivano in circa **3 anni e mezzo**, verso la primavera del 2030.

| Cluster | Potenza a d = 0,2 | Potenza a d = 0,3 | Potenza con t ≥ 3 a d = 0,3 |
|---:|---:|---:|---:|
| 60 | 21% | 48% | 25% |
| 80 | 28% | 62% | 38% |
| 100 | 36% | 74% | 50% |
| 120 | 44% | 82% | 62% |

Con 100 cluster il test può dire «non supportata» per un effetto medio (d = 0,3), ma non vede un effetto piccolo. La soglia severa t ≥ 3 ha potenza del 50% anche a 100 cluster: per questo è riportata ma non decide l'esito.

## Ipotesi secondarie (solo descrittive)
- **Controllo azioni:** stessa regola su S&P 500, Nasdaq 100 e Russell 2000. La bozza voleva che l'idea fosse smentita anche se l'effetto è uguale o più forte sulle azioni. Ma le azioni danno circa 5 eventi all'anno, troppo pochi per un test: il confronto è solo descrittivo.
- **Per classe:** cambi e materie prime separati.
- **Rendimento netto:** con commissioni (0,045% per lato) e slippage (0,02% per lato), e con un funding ipotetico di 0,03% al giorno per 28 giorni di calendario. L'eccesso del test primario non dipende dai costi, perché gli ingressi casuali pagano gli stessi.

## Limiti
- **Mercati diversi da quelli negoziati:** future e cambi di Yahoo approssimano i mercati `xyz` di Hyperliquid, che hanno poca storia, orari e funding propri.
- **Revisioni dei dati:** Yahoo può correggere barre già scaricate. Le barre usate sono quelle presenti al momento del test.
- **Cluster ancora dipendenti:** due eventi a più di 3 giorni di distanza possono avere periodi di tenuta sovrapposti su mercati legati (oro e argento, i cambi con il dollaro), quindi l'errore standard può essere sottostimato.
- **Regime:** 3-4 anni coprono pochi cicli di mercato.
- **Pochi dati di controllo:** il confronto con le azioni non può smentire nulla.
- **Effetto noto:** se il trend sui cambi funzionasse ancora in modo semplice, sarebbe già sfruttato. Un esito negativo è il più probabile, ed è un esito utile.
