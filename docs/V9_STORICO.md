# Pre-registrazione v9, chi vinceva il 06 novembre ha continuato a vincere?

Eseguito il 2026-11-25, una sola volta. Configurazione `26777a85afa7…`. Non è consulenza finanziaria.

Gruppo di partenza: i 5353 conti della classifica Hyperliquid del 2026-11-06 con almeno $100.000 e un giro d'affari da trader (né fermi né market maker). Rendimento dopo: profitto dal 2026-11-06 al 2026-11-25 diviso il capitale del 2026-11-06. 919 conti sono usciti dalla classifica e non hanno un profitto affidabile: il test si fa escludendoli e mettendoli all'ultimo posto, e regge solo se regge in entrambi i modi. Rendimento mediano dei conti rimasti: -9.1%. Holm al 5% sulle tre.

| ID | Domanda | Esito | p (esclusi / ultimi) | Cosa si vede |
|---|---|---|---:|---|
| P1 | chi rendeva di più nel mese rende di più dopo | **supportata** | 0.0000 / 0.0000 | correlazione di rango +0.432 su 4434 conti |
| P2 | i 50 con più profitti del mese battono gli altri | **supportata** | 0.0000 / 0.0000 | mediana +19.5% contro -9.4%; in utile 86% contro 27% (50 contro 4384 conti; usciti dalla classifica 3 contro 916) |
| P3 | i 150 con più profitti di sempre battono gli altri | **supportata** | 0.0003 / 0.0000 | mediana -3.9% contro -9.2%; in utile 44% contro 27% (150 contro 4284 conti; usciti dalla classifica 9 contro 910) |

Sono 19 giorni e un solo momento di mercato: se tutti i vincenti erano long e il mercato è salito, vincono insieme per lo stesso motivo. Dice se la classifica ha qualche memoria, non che copiarla renda. Quello lo dice la copia sulla carta (`python -m bzd.v9 futuro`).
