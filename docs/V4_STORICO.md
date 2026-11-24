# Pre-registrazione v4, test storico 2008–2026

Eseguito il 2026-11-06, una sola volta, su 50 mercati mai usati dal programma. Configurazione `7d3130de6eaf…`. Non è consulenza finanziaria.

BYZ e SZT letti al contrario del nome: dopo BYZ short, dopo SZT long, per 10 sedute. «Eccesso» è quanto l'operazione ha reso in più di ingressi casuali sullo stesso mercato nello stesso anno, nel verso dell'operazione. La soglia di Holm tiene al 5% la probabilità di anche un solo falso «supportata» su tutte e sei.

| ID | Lettura | Operazione | Esito | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |
|---|---|---|---|---:|---:|---:|---:|---:|:---:|
| N1 | BYZ, soglia -50 | short | **supportata** | 646 | +0.68% | 0.0001 | 0.0100 | -0.77% | sì |
| N2 | SZT, soglia +50 | long | **supportata** | 539 | +0.63% | 0.0001 | 0.0083 | -0.04% | sì |
| N3 | BYZ da 3 sedute di fila | short | **non supportata** | 621 | +0.11% | 0.3304 | 0.0250 | -0.80% | no |
| N4 | SZT da 3 sedute di fila | long | **supportata** | 655 | +0.54% | 0.0066 | 0.0125 | +0.28% | no |
| N5 | BYZ forte, soglia -70 | short | **non supportata** | 583 | -0.70% | 0.9956 | 0.0500 | -1.45% | no |
| N6 | SZT forte, soglia +70 | long | **non supportata** | 616 | +0.25% | 0.1145 | 0.0167 | +0.18% | no |

## Per classe (descrittivo)

- **N1**: commodities 1150 eventi, eccesso +1.07%, netto -0.37%; crypto 1631 eventi, eccesso +3.89%, netto -0.84%; equities 2070 eventi, eccesso +0.50%, netto -0.42%; fx 678 eventi, eccesso +0.17%, netto -0.21%
- **N2**: commodities 1346 eventi, eccesso +0.99%, netto +0.12%; crypto 1030 eventi, eccesso +6.79%, netto +4.14%; equities 3707 eventi, eccesso +0.49%, netto +0.14%; fx 674 eventi, eccesso +0.09%, netto -0.15%
- **N3**: commodities 609 eventi, eccesso +0.43%, netto -0.47%; crypto 847 eventi, eccesso +1.74%, netto -1.11%; equities 1044 eventi, eccesso -0.06%, netto -0.60%; fx 328 eventi, eccesso +0.00%, netto -0.17%
- **N4**: commodities 701 eventi, eccesso +0.42%, netto +0.08%; crypto 527 eventi, eccesso +4.91%, netto +4.00%; equities 1889 eventi, eccesso +0.21%, netto +0.21%; fx 330 eventi, eccesso +0.21%, netto +0.08%
- **N5**: commodities 591 eventi, eccesso -0.12%, netto -0.74%; crypto 697 eventi, eccesso -0.07%, netto -2.35%; equities 932 eventi, eccesso +0.04%, netto -0.40%; fx 266 eventi, eccesso +0.03%, netto -0.17%
- **N6**: commodities 744 eventi, eccesso +0.44%, netto +0.15%; crypto 445 eventi, eccesso +6.57%, netto +5.94%; equities 1937 eventi, eccesso -0.02%, netto +0.12%; fx 284 eventi, eccesso +0.04%, netto -0.02%

Le righe per classe sono descrittive, come stabilito nella pre-registrazione. Una lettura supportata qui diventa una regola solo dopo i dati futuri.
