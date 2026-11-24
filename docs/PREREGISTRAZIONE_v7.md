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
