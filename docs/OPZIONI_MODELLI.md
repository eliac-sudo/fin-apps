# Opzioni: come sono calcolati i prezzi

L'app dice quali contratti sembrano economici o cari. È la lettura di un modello su dati ritardati: **non è testata come strategia e non è un consiglio**.

## Il metodo

1. **Prezzo a termine.** Viene dalla parità tra call e put, usando la mediana di 5 strike vicini al prezzo, così non serve stimare i dividendi. Su Deribit è il future della stessa scadenza.
2. **Volatilità di ogni contratto.** Si ricava con Black-76 dal prezzo medio tra bid e ask. Si usano solo contratti fuori dai soldi: le opzioni USA sono americane, ma lì il valore dell'esercizio anticipato è piccolo.
3. **Curva di mercato.** Una curva SVI per ogni scadenza. Viene scartata se sbaglia in media di oltre 5 punti di volatilità.
4. **Volatilità prevista.** HAR per ogni scadenza, sui rendimenti giornalieri del sottostante. Per l'euro uso il tasso EUR/USD, perché non ho i prezzi storici di FXE.
5. **Valore del modello.** Tiene la forma della curva di mercato e ne sposta il livello su quello previsto da HAR.
6. **Giudizio.** Economica se l'ask è sotto il valore del modello, cara se il bid è sopra. Uno scarto più piccolo dello spread non conta.
7. **Classifica.** Per scarto in punti di volatilità, perché in percentuale esplode sulle opzioni che costano pochissimo.

Le liste mostrano solo contratti con scadenza tra 7 e 75 giorni, delta tra 0,15 e 0,55, spread sotto il 25% e abbastanza contratti aperti (50 su Cboe, 5 su Deribit).

## Perché HAR

Confronto fuori campione del 5 novembre 2026: 36 periodi mensili per mercato, con ogni previsione fatta solo sui dati già noti. Il primo numero è l'errore medio sul logaritmo della volatilità, il secondo la distorsione: positiva vuol dire che il modello prevede troppo.

| Mercato | Ultimi 20 giorni | EWMA | GARCH 750 | GARCH 1500 | HAR | Volatilità implicita |
|---|---|---|---|---|---|---|
| SPY | 0,331 / −0,002 | 0,330 / +0,020 | 0,297 / +0,096 | 0,303 / +0,184 | **0,278 / −0,001** | 0,360 / +0,287 |
| QQQ | 0,311 / −0,010 | 0,315 / +0,009 | 0,285 / +0,064 | 0,296 / +0,120 | **0,284 / −0,021** | – |
| TLT | 0,237 / +0,029 | 0,194 / +0,026 | 0,215 / +0,136 | 0,234 / +0,162 | **0,174 / +0,033** | – |
| GLD | 0,311 / −0,006 | 0,302 / +0,027 | 0,284 / −0,005 | 0,271 / −0,051 | 0,265 / −0,050 | **0,263 / +0,080** |
| USO | 0,258 / −0,013 | 0,236 / +0,003 | 0,255 / +0,070 | 0,286 / +0,151 | **0,212 / −0,022** | 0,310 / +0,227 |
| BTC | 0,337 / −0,041 | 0,295 / +0,010 | 0,252 / +0,155 | 0,317 / +0,262 | 0,262 / +0,142 | **0,248 / +0,124** |
| ETH | 0,330 / −0,034 | 0,278 / +0,020 | 0,242 / +0,102 | 0,251 / +0,119 | 0,240 / +0,045 | **0,226 / +0,029** |

HAR è il migliore tra i modelli sui prezzi in 5 mercati su 7, e nei restanti 2 è secondo o vicino al primo. Su BTC ed ETH la volatilità implicita prevede meglio di ogni modello, quindi lì «economica» va presa con più cautela. I periodi sono pochi, e la scelta non è un test del segnale.

## Limiti

- **Eventi:** il modello vede solo i prezzi passati. Un'opzione può sembrare cara proprio perché è atteso un evento, come una riunione di banca centrale.
- **Le soglie:** sotto 0,9 volte economiche e sopra 1,25 volte care sono una scelta, non un risultato.
- **GEX:** nessuno sa chi detiene cosa. Si assume che i dealer siano lunghi sulle call e corti sulle put: con un'altra ipotesi il segno può cambiare.
- **Prezzi:** Cboe ha circa 15 minuti di ritardo, e le catene salvate hanno fino a 6 ore. Il pulsante «Aggiorna i prezzi» ne scarica di nuove. Controlla sempre il prezzo prima di agire.
- **Vendere opzioni allo scoperto** ha un rischio di perdita molto alto.
