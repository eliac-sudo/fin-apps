---
title: Liquidità
kind: calcolo
status: descrive, non prevede; non testato
brief: Quanta moneta gira (Fed, M2, stablecoin, credito, dollaro) e quanto facilmente si scambia ogni mercato (volumi, impatto, book).
code: bzd/liquidity.py#macro, bzd/liquidity.py#net_liquidity, bzd/liquidity.py#markets, bzd/liquidity.py#volume_liquidity, bzd/liquidity.py#refresh_books, bzd/history.py#get_stablecoins, bzd/liquidity.py#credit_ratio, bzd/liquidity.py#btp_bund, bzd/history.py#get_eu_rates
data: data/hist/macro, data/hist/liquidity, data/raw/hl_l2_btc
feeds: app
---
## In breve
Dal 25 novembre 2026 tre letture in più, non testate: il credito come HYG diviso IEF con le cedole (dal 2007, mentre lo spread high yield di FRED è gratis solo per 3 anni), lo spread BTP–Bund a 10 anni (media del mese, BCE) e il Bund a 10 anni ogni giorno (Bundesbank).

Nella scheda Oggi c'è il riquadro **Liquidità**; sulla pagina di ogni ticker una riga 💧.

**Quanta moneta gira** (`bzd/liquidity.py#macro`), ogni indicatore confrontato con 13 settimane prima (le stablecoin con 30 giorni):
- **Liquidità netta della Fed**: bilancio (WALCL) meno il conto del Tesoro (WTREGEN) meno il reverse repo (RRPONTSYD), in miliardi di dollari. Sale: più soldi nel sistema.
- **M2 USA**, crescita annua.
- **Stablecoin in circolazione** (DefiLlama, dal 2017): i dollari pronti a comprare cripto.
- **Condizioni finanziarie** della Chicago Fed (NFCI): sotto zero più facili della media.
- **Spread high yield** e **dollaro**: se scendono, il credito gira e la liquidità nel mondo si allarga.

**Quanto si scambia ogni mercato** (`bzd/liquidity.py#markets`):
- **Volumi**: media delle ultime 20 sedute, percentile sugli ultimi 3 anni. Per i futures in contratti, perché prezzo per contratti cresce con il prezzo; per le cripto in dollari, dalle barre a 4 ore. Le coppie forex non hanno volumi su Yahoo.
- **Impatto** (Amihud): movimento del prezzo per dollaro scambiato, media di 20 sedute, percentile su 3 anni. Alto vuol dire meno liquido.
- **Liquidità 0–100**: la media tra volumi e il contrario dell'impatto. Fasce: scarsa sotto 20, sotto la norma, nella norma, sopra la norma, abbondante sopra 80.
- **Book di Hyperliquid** per gli 11 mercati registrati: spread in punti base e profondità entro ±0,5% dal prezzo medio, confrontati con la mediana di quanto registrato. Un'istantanea all'ora finisce in `data/hist/liquidity/books.csv.gz`.

## Quanto fidarsi
- Nessuna lettura della liquidità è stata confrontata con i prezzi: descrive e non prevede.
- I volumi dei futures di Yahoo sono quelli del contratto principale: nei giorni del cambio di scadenza saltano.
- Il book di Hyperliquid si registra dal 4 novembre 2026, con un buco dal 7 al 23: la mediana è di pochi giorni.
- Volumi alti con impatto alto non sono liquidità abbondante: di solito vuol dire stress, molti scambi e prezzi che si muovono molto.
