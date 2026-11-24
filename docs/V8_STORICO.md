# Pre-registrazione v8, test storico 2018–2026

Eseguito il 2026-11-24, una sola volta, sulle 9 cripto. Configurazione `036f95706d11…`. Non è consulenza finanziaria.

Due idee del supervisore degli agenti di ricerca, dalla letteratura sulla psicologia dei mercati ([PREREGISTRAZIONE_v8.md](PREREGISTRAZIONE_v8.md)). G1 misura l'ampiezza: quanto si muove il prezzo in valore assoluto, in più di ingressi casuali. G2 è uno short: quanto rende in più di ingressi casuali. Holm al 5% sulle due.

| ID | Lettura | Misura | Esito | Eventi | Cluster | Eccesso medio | p | Soglia Holm |
|---|---|---|---|---:|---:|---:|---:|---:|
| G1 | paura estrema cripto | ampiezza: valore assoluto del rendimento, 3 giorni | **non supportata** | 1203 | 67 | -0.94% | 0.9853 | 0.0500 |
| G2 | euforia estrema cripto | rendimento, 20 giorni | **non informativa** | 131 | 21 | -2.57% | 0.6745 | 0.0250 |

Una lettura supportata qui va comunque provata sui dati futuri (`python -m bzd.v8 futuro`) prima di entrare in un setup.
