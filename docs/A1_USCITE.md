# A1 — laboratorio delle uscite (solo periodo di calibrazione)

Riproduzione: `python -m bzd.exits run`. Regole e criterio di scelta sono stati fissati nel commit `b99af4a`, prima di calcolare qualsiasi rendimento. I prezzi vengono tagliati alla fine della calibrazione, quindi il periodo di test resta chiuso. Tabella completa: `data/hist/exits_v1_calibration.csv`. Non è consulenza finanziaria.

> **Aggiornamento dopo B3:** nel periodo di test le uscite selezionate non hanno superato il confronto con «tieni» (`docs/B3_RISULTATI.md`). Nel panico cripto, stop + 3R ha ridotto molto le perdite grandi (peggior 10% −1,11R contro −3,88R), ma ha anche reso meno: −0,02R contro +0,31R per episodio. Quindi la frase qui sotto, «quasi senza costo medio», vale solo per la calibrazione.

## Risultati principali (cripto, panico: 576 eventi)

| Regola | R medio per evento | R medio per episodio | Peggior 10% | Oltre −3R | Profitto restituito |
|---|---:|---:|---:|---:|---:|
| Tieni 7 giorni, senza stop | +0,10 | +0,62 | −3,14 | 11% | 2,15 R |
| Stop + obiettivo 3R | +0,13 | +0,26 | −1,09 | 0% | 1,33 R |
| Stop + tieni | +0,02 | +0,21 | −1,08 | 0% | 1,78 R |
| Terzi + trailing | −0,01 | +0,08 | −1,06 | 0% | 1,77 R |

1. **Nessuna regola batte chiaramente le altre sul rendimento medio.** Per evento, «tieni» e «stop + 3R» sono quasi uguali.
2. **Il criterio fissato sceglie «tieni», ma è una scelta fragile.** Il criterio usa la media per episodio, dove pesano molto gli episodi con una sola moneta. Per evento il vantaggio scompare. Il criterio non è stato cambiato dopo aver visto i dati.
3. **Stop e obiettivo tagliano le perdite grandi quasi senza costo medio.** Il peggior 10% passa da −3,14R a −1,09R e il profitto restituito da 2,15R a 1,33R.
4. **Il panico da solo non mostra vantaggio.** A 7 giorni, gli ingressi dopo il panico fanno −0,3% rispetto a ingressi casuali su stessa moneta e stesso anno. Da solo, l'R positivo può riflettere il rialzo del mercato: nel 2022 «tieni» fa −0,56R.
5. **Gli stop possono essere troppo larghi.** Distanza mediana 5,4%, 90° percentile 15,5%, 99° 39,6%, fino a 53% nel crollo del 19/5/2021. Con leva alta la liquidazione arriva prima dello stop. Serve un limite alla distanza in una v2.

## Altri mercati (R medio per evento)

| Mercato, setup | Tieni | Stop + 3R | Scelta del criterio |
|---|---:|---:|---|
| Cripto squeeze | +0,46 | +0,38 | tieni |
| Azioni panico | −0,08 | −0,23 | tieni |
| Azioni squeeze | +0,11 | +0,07 | tieni |
| Bond panico | −0,15 | 0,00 | tieni |
| Bond squeeze | −0,35 | −0,30 | stop a metà tempo |
| Materie prime panico | 0,00 | +0,09 | tieni |
| Materie prime squeeze | −0,05 | +0,08 | obiettivo 3R |
| Forex panico | −0,47 | −0,13 | terzi + trailing |
| Forex squeeze | +0,15 | +0,11 | tieni |

Nessuna regola d'uscita rende buono un setup che non lo è: i bond squeeze restano negativi con ogni regola. Con 9 regole confrontate, alcune scelte possono essere dovute al caso.

## Limiti
- **Solo calibrazione:** il test non è stato toccato, quindi niente di questo è una conferma.
- **Barre da 4 ore o giornaliere:** quando una barra tocca stop e obiettivo si assume lo stop, un'ipotesi prudente.
- **Dati esclusi:** molti percorsi scartati per barre incoerenti, soprattutto cereali e oro nel 2003–2008 (141 in tutta la classe materie prime).
- **Mercati approssimati:** Binance e futures, non Hyperliquid. Slippage ipotizzato, e con 0,20% per lato il risultato per evento scende di circa 0,07R.
- **Le tue operazioni non ci sono:** il confronto con le tue uscite reali è A2, che può girare solo in locale.
- **Regole non provate in test:** per l'uso reale, «stop + 3R» è una scelta di gestione del rischio, non un vantaggio dimostrato.
