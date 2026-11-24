# Pre-registrazione v8: paura ed euforia cripto, e prova sui dati futuri

Scritta il 24 novembre 2026, prima di calcolare qualunque rendimento dopo queste letture. Configurazione `config/setups_v8.json`, SHA-256 `036f95706d11855b5f7aaa0276b40a41ba69ccca09aad48f958d9693c3845db4`. Codice `bzd/v8.py`.

## Perché

Due parti diverse:

1. **Due idee nuove, sulla storia.** Il supervisore degli agenti di ricerca, dopo aver letto 146 lavori sulla psicologia dei mercati ([IDEE_V2.md](letteratura/IDEE_V2.md)), propone due regole sul Fear & Greed cripto che non abbiamo mai provato in questa forma. B3 aveva misurato il verso del rendimento dopo il panico, sulle 24 ore: qui G1 misura l'ampiezza, G2 il rendimento a 4 settimane.
2. **Tre letture andate vicino, sui dati futuri.** «Posizione bassa nell'anno» (v7), «dollaro in forte rialzo» e «impatto alto» (v6) hanno già usato tutta la storia: rifarle lì troverebbe solo vincitori per caso. Si giudicano solo sui dati che arrivano dal 25 novembre 2026. Anche G1 e G2 entrano nella prova sui dati futuri, qualunque sia il loro esito storico.

## Parte storica: G1 e G2

| ID | Lettura | Regola | Misura | Orizzonte |
|---|---|---|---|---|
| G1 | Paura estrema cripto | Fear & Greed ≤ 20 | ampiezza: valore assoluto del rendimento, in più di ingressi casuali | 3 giorni |
| G2 | Euforia estrema cripto | Fear & Greed ≥ 80 | rendimento di uno short, in più di ingressi casuali | 20 giorni |

Sulle 9 cripto, dal 1° febbraio 2018 al 24 novembre 2026. Il Fear & Greed di un giorno si usa dal giorno dopo; l'ingresso è all'apertura della seduta successiva. Stesso metodo di v3–v6: 200 ingressi casuali sullo stesso mercato nello stesso anno, cluster di 3 giorni, t-test a una coda più bootstrap, Holm al 5% sulle due. Per G1 non si tolgono costi: misura un movimento, non è un'operazione. Si fa una volta sola: `python -m bzd.v8 storico --confirm`.

## Parte sui dati futuri

| ID | Lettura | Regola | Mercati | Operazione |
|---|---|---|---|---|
| P1 | Prezzo basso nell'ultimo anno | posizione ≤ 20 (v7) | 30 mercati di v7 | long, 10 sedute |
| D1 | Dollaro in forte rialzo | come v6 L3 | come v6 | short, 20 sedute |
| A1 | Impatto alto | come v6 L4 | come v6 | long, 10 sedute |
| G1 | Paura estrema cripto | come sopra | 9 cripto | ampiezza, 3 giorni |
| G2 | Euforia estrema cripto | come sopra | 9 cripto | short, 20 giorni |

Solo sedute dal 25 novembre 2026. Ogni ipotesi si giudica **una volta sola**, quando arriva a 60 cluster o il 24 novembre 2028, quello che viene prima, a una soglia di 0,01 (5% diviso per 5, Bonferroni): le ipotesi arrivano ai cluster in momenti diversi, quindi Holm, che le vuole tutte insieme, non si può usare. Prima di allora `python -m bzd.v8 futuro` conta solo gli eventi, senza rendimenti, e si può lanciare ogni giorno.

## Limiti, detti prima

- **Fear & Greed** è un indice di terzi con una ricetta non del tutto pubblica, il sostituto dell'indice usato nei lavori citati.
- **G1 e la volatilità:** la paura estrema arriva spesso dopo giorni già agitati. Se G1 regge, può essere solo la volatilità che continua, cosa nota; non si controlla qui.
- **Euforia rara:** 165 giorni sopra 80 dal 2018, in poche fasi. G2 avrà pochi cluster.
- **Dati futuri lenti:** D1 ha un orizzonte di 20 sedute e un segnale settimanale: arriverà a 60 cluster solo in anni, quindi probabilmente si giudicherà alla data.

## Conteggi prima del test

Solo eventi e cluster della parte storica, senza rendimenti (`python -m bzd.v8 conta`):

| ID | Eventi | Cluster |
|---|---:|---:|
| G1 | 1216 | 67 |
| G2 | 140 | 24 |

G2 ha meno di 30 cluster: con ogni probabilità uscirà «non informativa».
