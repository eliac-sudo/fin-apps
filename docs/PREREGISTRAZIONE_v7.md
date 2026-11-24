# Pre-registrazione v7: tutte le coppie di letture, con la storia divisa in tre

Scritta il 24 novembre 2026, prima di calcolare qualunque rendimento. Configurazione `config/setups_v7.json`, SHA-256 `08b7f9a0db5588d033926f8c9db40a9f319e2b91dfb54b035eeaab1e3c13ec03`. Codice `bzd/v7.py`. Ricerca e controllo si fanno una volta (`python -m bzd.v7 cerca`), l'esame una volta (`python -m bzd.v7 esame --confirm`): entrambi rifiutano di ripartire.

## Perché

Da v3 a v6 nessuna lettura da sola ha dato un vantaggio netto che regge. Resta una domanda: due letture insieme (per esempio momentum alto e liquidità della Fed in aumento) fanno meglio? Provarle tutte sulla stessa storia troverebbe sempre dei «vincitori» per caso. Per questo la storia si divide in tre parti e la terza si guarda una volta sola, alla fine.

## Le tre parti

| Parte | Periodo | Cosa si fa |
|---|---|---|
| Ricerca | 2008–2018 | tutte le 484 regole; si tengono le 30 con il t più alto, con almeno 40 cluster |
| Controllo | 2019–2022 | delle 30 passano quelle con eccesso positivo, t ≥ 1,65 e almeno 15 cluster |
| Esame | 2023 – 20 novembre 2026 | solo le sopravvissute, con il metodo completo di v3–v6 e Holm al 5% |

Un evento conta in una parte solo se la sua uscita cade dentro la stessa parte: nessun rendimento di ricerca o controllo usa prezzi degli anni dell'esame.

## Letture e regole

Undici letture, ognuna in due stati, basso e alto, calcolati ogni giorno solo sui dati prima: slancio, RSI, estensione dalla media a 200 sedute, punteggio del momentum dell'app, posizione nell'anno, COT, volatilità implicita del mercato, volumi, impatto (Amihud), liquidità netta della Fed e dollaro (questi due datati quando erano pubblici). Le soglie sono in `config/setups_v7.json`.

Regole: ogni stato da solo (22) e ogni coppia di stati di due letture diverse (4 × 55 = 220), sia long sia short: 484 regole, tenute 10 sedute, su 15 futures, 6 cambi e 9 cripto. Una lettura che su un mercato non esiste (COT e volatilità sulle cripto, volumi sui cambi) lì non scatta.

## Confronto

- **Ricerca e controllo:** eccesso sulla media del rendimento a 10 sedute di tutte le sedute dello stesso mercato nello stesso anno, nel verso dell'operazione; eventi entro 3 giorni su mercati diversi uniti in un cluster; t della media per cluster. È una versione veloce del metodo, perché le regole sono tante.
- **Esame:** il metodo completo di v3–v6: 200 ingressi casuali sullo stesso mercato nello stesso anno lontani dagli eventi, t-test a una coda più bootstrap, Holm al 5% sulle sopravvissute, netto con slittamento dello 0,05% per lato.

## Limiti, detti prima

- **Le letture da sole le abbiamo già viste** su tutta la storia (v3–v6): per le regole a una lettura l'esame non è del tutto nuovo. Per le coppie sì.
- **Le cripto partono dal 2019:** nella ricerca non ci sono; entrano solo nel controllo e nell'esame.
- **Il caso:** su 484 regole, nella ricerca ce ne aspettiamo circa 24 con t sopra 1,65 senza nessun vantaggio vero. Il controllo e l'esame servono a scartarle.
- **Mercati e periodi si muovono insieme:** un cluster di 3 giorni unisce gli eventi dello stesso momento, ma i regimi lunghi (liquidità, dollaro) restano pochi casi indipendenti.

## Risultato della ricerca e del controllo

Eseguiti il 2026-11-24. Regole provate: 484; con almeno 40 cluster: 440. Sul periodo di ricerca il t delle regole va da -4.0 a 4.0; per puro caso, su 440 regole, ce ne aspetteremmo circa 22 con t sopra 1,65.

| # | Regola | Cluster ricerca | Eccesso ricerca | t ricerca | Cluster controllo | Eccesso controllo | t controllo | Passa |
|---:|---|---:|---:|---:|---:|---:|---:|:---:|
| 1 | posizione basso → long | 447 | +0.50% | 4.00 | 120 | +0.67% | 1.92 | sì |
| 2 | momentum basso + posizione basso → long | 405 | +0.67% | 3.88 | 128 | +1.02% | 2.54 | sì |
| 3 | estensione basso + posizione basso → long | 419 | +0.53% | 3.11 | 101 | +1.19% | 1.67 | sì |
| 4 | estensione basso → long | 444 | +0.46% | 3.04 | 94 | +0.53% | 0.99 | no |
| 5 | slancio alto + impatto alto → short | 147 | +1.42% | 2.98 | 78 | -0.65% | -0.89 | no |
| 6 | estensione alto + cot alto → short | 309 | +0.67% | 2.83 | 93 | +0.82% | 1.56 | no |
| 7 | slancio basso + estensione basso → long | 363 | +0.53% | 2.67 | 100 | +0.19% | 0.19 | no |
| 8 | slancio alto → short | 441 | +0.36% | 2.63 | 134 | -0.50% | -0.96 | no |
| 9 | rsi alto + impatto alto → short | 43 | +1.46% | 2.62 | 28 | -1.04% | -0.77 | no |
| 10 | slancio basso + posizione basso → long | 374 | +0.48% | 2.60 | 109 | +1.67% | 2.15 | sì |
| 11 | momentum basso + volatilita alto → long | 112 | +1.21% | 2.43 | 46 | +0.18% | 0.28 | no |
| 12 | momentum alto + impatto alto → short | 130 | +0.80% | 2.41 | 70 | +0.18% | 0.31 | no |
| 13 | estensione basso + momentum basso → long | 382 | +0.52% | 2.41 | 117 | +0.58% | 0.63 | no |
| 14 | momentum alto + liquidita_fed alto → short | 175 | +0.48% | 2.39 | 58 | +0.57% | 0.85 | no |
| 15 | estensione alto + posizione alto → short | 409 | +0.45% | 2.34 | 140 | +0.63% | 1.45 | no |
| 16 | posizione basso + cot basso → long | 431 | +0.34% | 2.34 | 129 | +0.26% | 1.23 | no |
| 17 | estensione basso + dollaro alto → long | 159 | +0.61% | 2.32 | 47 | +0.80% | 0.59 | no |
| 18 | slancio alto + cot alto → short | 279 | +0.55% | 2.22 | 93 | -0.23% | -0.37 | no |
| 19 | estensione alto + volumi alto → short | 176 | +1.09% | 2.21 | 74 | -0.68% | -0.45 | no |
| 20 | slancio alto + momentum alto → short | 415 | +0.36% | 2.21 | 138 | +0.37% | 0.67 | no |
| 21 | slancio alto + estensione alto → short | 323 | +0.46% | 2.20 | 119 | -0.45% | -0.59 | no |
| 22 | cot basso + dollaro basso → long | 116 | +0.52% | 2.20 | 46 | +0.20% | 0.88 | no |
| 23 | estensione alto → short | 433 | +0.35% | 2.04 | 140 | +0.58% | 1.19 | no |
| 24 | estensione basso + volumi alto → long | 255 | +0.71% | 2.03 | 88 | +1.67% | 1.55 | no |
| 25 | slancio basso + momentum basso → long | 426 | +0.37% | 2.02 | 123 | +1.07% | 1.38 | no |
| 26 | momentum alto + volatilita basso → short | 253 | +0.28% | 2.02 | 101 | +0.11% | 0.67 | no |
| 27 | posizione alto + impatto alto → short | 135 | +0.63% | 2.02 | 66 | +0.12% | 0.27 | no |
| 28 | estensione alto + impatto basso → short | 198 | +0.70% | 2.02 | 96 | +0.74% | 0.78 | no |
| 29 | momentum alto + cot alto → short | 319 | +0.39% | 2.01 | 99 | +0.32% | 0.70 | no |
| 30 | volatilita basso + dollaro basso → long | 81 | +0.53% | 1.99 | 34 | -0.05% | -0.72 | no |

Passano il controllo **4** regole su 30. Solo queste vanno all'esame 2023–2026, una volta sola.
