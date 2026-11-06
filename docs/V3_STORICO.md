# Pre-registrazione v3, test storico 2008–2026

Eseguito il 2026-11-06, una sola volta. Configurazione `61dc10ded310…`. Non è consulenza finanziaria.

Ogni riga è un'ipotesi della pre-registrazione. «Eccesso» è quanto l'operazione ha reso in più di ingressi casuali sullo stesso mercato nello stesso anno, nel verso della lettura (per le opzioni, in quota del premio). La soglia di Holm tiene al 5% la probabilità di anche un solo falso «supportata» su tutte e quindici.

| ID | Lettura | Operazione | Esito | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |
|---|---|---|---|---:|---:|---:|---:|---:|:---:|
| O1 | opzioni: care | vendi straddle ATM 30 giorni | **non supportata** | 221 | -6.32% del premio | 0.8595 | 0.0167 | +5.14% | no |
| O2 | opzioni: economiche | compra straddle ATM 30 giorni | **supportata** | 120 | +21.96% del premio | 0.0023 | 0.0033 | -0.95% | no |
| Z1 | zone: BYZ 1d sugli indicatori | long | **non supportata** | 724 | -0.66%  | 0.9991 | 0.0250 | +0.34% | sì |
| Z2 | zone: SZT 1d sugli indicatori | short | **non supportata** | 701 | -0.61%  | 1.0000 | 0.0500 | -0.24% | sì |
| R1 | reset: ipervenduto in trend al rialzo, 1d | long | **non supportata** | 149 | +0.53%  | 0.1482 | 0.0038 | +0.80% | no |
| R2 | reset: ipercomprato in trend al ribasso, 1d | short | **non supportata** | 164 | -1.02%  | 0.8388 | 0.0125 | -1.34% | no |
| T1 | tensione: molto tirato in basso | long | **non supportata** | 442 | -0.05%  | 0.5612 | 0.0050 | +0.62% | no |
| T2 | tensione: molto tirato in alto | short | **non supportata** | 417 | -0.13%  | 0.6262 | 0.0063 | -0.71% | no |
| S1 | sentiment: paura estrema | long | **non supportata** | 472 | -0.31%  | 0.8260 | 0.0083 | -0.16% | no |
| S2 | sentiment: euforia estrema | short | **non supportata** | 522 | -0.22%  | 0.7679 | 0.0071 | -0.67% | no |
| F1 | chi compra: i grossi comprano il dip | long | **non supportata** | 188 | -0.16%  | 0.5980 | 0.0056 | +0.03% | no |
| F2 | chi compra: il retail compra il dip | long | **non supportata** | 232 | -0.55%  | 0.1753 | 0.0042 | -0.35% | no |
| M1 | forti movimenti: movimento forte in un giorno | nel verso del movimento | **non supportata** | 511 | +0.23%  | 0.3953 | 0.0045 | +0.11% | no |
| L1 | livelli: test del supporto | long | **non supportata** | 489 | -0.09%  | 0.8277 | 0.0100 | -0.13% | no |
| L2 | livelli: test della resistenza | short | **non supportata** | 479 | +0.21%  | 0.0098 | 0.0036 | +0.02% | no |

## Opzioni senza condizioni

Vendere ogni giorno uno straddle a 30 giorni, prezzato all'indice di volatilità: quanto resta al venditore, in quota del premio.

| Mercato | Giorni | Medio lordo | Medio netto dello spread | Positivi | Peggiore | Giorni «care» | Giorni «economiche» |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY | 4721 | +20.89% | +18.89% | 71% | -801.85% | 59% | 1% |
| GLD | 4285 | +8.42% | +2.42% | 64% | -416.59% | 27% | 2% |
| USO | 4285 | +10.10% | +4.10% | 64% | -644.61% | 40% | 1% |
| EURUSD=X | 4302 | +10.98% | +2.98% | 64% | -415.23% | 19% | 8% |
| BTC | 2024 | +3.27% | -1.73% | 62% | -520.07% | 16% | 17% |
| ETH | 2024 | -5.48% | -11.48% | 60% | -584.02% | 7% | 28% |

## Per classe (descrittivo)

- **O1**: options 262 eventi, eccesso -5.86%, netto +5.09%
- **O2**: options 138 eventi, eccesso +25.23%, netto +2.38%
- **Z1**: bonds 592 eventi, eccesso -0.17%, netto -0.10%; commodities 1133 eventi, eccesso -1.20%, netto -0.01%; crypto 594 eventi, eccesso -4.07%, netto +0.41%; equities 191 eventi, eccesso -0.21%, netto +0.61%; fx 806 eventi, eccesso -0.23%, netto -0.08%
- **Z2**: bonds 519 eventi, eccesso -0.12%, netto -0.15%; commodities 1216 eventi, eccesso -1.02%, netto -0.34%; crypto 594 eventi, eccesso -9.02%, netto -7.01%; equities 559 eventi, eccesso -0.45%, netto -0.55%; fx 825 eventi, eccesso -0.30%, netto -0.18%
- **R1**: bonds 38 eventi, eccesso -0.02%, netto -0.21%; commodities 71 eventi, eccesso +0.22%, netto +0.40%; crypto 31 eventi, eccesso +2.95%, netto +5.19%; equities 27 eventi, eccesso +0.01%, netto +0.62%; fx 52 eventi, eccesso -0.02%, netto -0.09%
- **R2**: bonds 18 eventi, eccesso -0.46%, netto -0.52%; commodities 65 eventi, eccesso +1.27%, netto +1.16%; crypto 76 eventi, eccesso -6.78%, netto -8.22%; equities 7 eventi, eccesso -1.07%, netto -1.43%; fx 57 eventi, eccesso +0.05%, netto -0.06%
- **T1**: bonds 164 eventi, eccesso +0.05%, netto -0.12%; commodities 286 eventi, eccesso +0.13%, netto +0.27%; crypto 202 eventi, eccesso -3.01%, netto +1.35%; equities 76 eventi, eccesso +1.26%, netto +1.27%; fx 288 eventi, eccesso -0.20%, netto -0.27%
- **T2**: bonds 20 eventi, eccesso +0.70%, netto +0.34%; commodities 274 eventi, eccesso +0.83%, netto +0.48%; crypto 137 eventi, eccesso -11.24%, netto -13.38%; equities 65 eventi, eccesso +0.74%, netto -0.18%; fx 214 eventi, eccesso +0.29%, netto -0.02%
- **S1**: bonds 194 eventi, eccesso +0.06%, netto -0.19%; commodities 338 eventi, eccesso +0.40%, netto -0.12%; crypto 675 eventi, eccesso -5.06%, netto -1.50%; equities 57 eventi, eccesso +1.34%, netto +0.96%; fx 155 eventi, eccesso -0.27%, netto -0.29%
- **S2**: bonds 127 eventi, eccesso +0.15%, netto -0.12%; commodities 481 eventi, eccesso -0.04%, netto -0.21%; crypto 442 eventi, eccesso -9.20%, netto -9.71%; equities 97 eventi, eccesso +0.47%, netto -0.53%; fx 281 eventi, eccesso +0.35%, netto -0.06%
- **F1**: bonds 97 eventi, eccesso +0.02%, netto -0.20%; commodities 61 eventi, eccesso +1.41%, netto +0.35%; crypto 23 eventi, eccesso -4.94%, netto +0.43%; equities 7 eventi, eccesso -3.87%, netto -4.41%; fx 49 eventi, eccesso +0.33%, netto +0.01%
- **F2**: bonds 40 eventi, eccesso +0.28%, netto -0.01%; commodities 136 eventi, eccesso -0.46%, netto -0.48%; crypto 47 eventi, eccesso -2.79%, netto -0.53%; equities 15 eventi, eccesso -1.80%, netto -1.92%; fx 53 eventi, eccesso +0.22%, netto -0.12%
- **M1**: bonds 208 eventi, eccesso -0.08%, netto -0.21%; commodities 447 eventi, eccesso +0.63%, netto +0.34%; crypto 299 eventi, eccesso +3.39%, netto +3.60%; equities 142 eventi, eccesso +0.23%, netto -0.16%; fx 314 eventi, eccesso +0.03%, netto -0.10%
- **L1**: bonds 1118 eventi, eccesso +0.04%, netto -0.11%; commodities 2106 eventi, eccesso -0.10%, netto -0.14%; crypto 963 eventi, eccesso -0.38%, netto +0.25%; equities 460 eventi, eccesso +0.09%, netto +0.17%; fx 1632 eventi, eccesso +0.03%, netto -0.10%
- **L2**: bonds 1087 eventi, eccesso +0.01%, netto -0.13%; commodities 2099 eventi, eccesso +0.29%, netto +0.15%; crypto 1024 eventi, eccesso -0.26%, netto +0.19%; equities 524 eventi, eccesso +0.20%, netto +0.18%; fx 1591 eventi, eccesso +0.06%, netto -0.10%

Le righe per classe e la tabella delle opzioni senza condizioni sono descrittive, come stabilito nella pre-registrazione.
