# BZD — pre-registrazione dei setup, v1

Stato: **bozza congelata, valida quando è committata in git** (la data del commit fa da prova). Non è consulenza finanziaria.

Configurazione: `config/setups_v1.json`
SHA-256: `1bde3cb8910446bc3597ab4d159da50171dc7d2650d6e8912bb5a5a0717e2828`

Un test controlla che l'hash coincida. Se la configurazione cambia, serve una v2 con una nuova pre-registrazione, e i risultati della v1 restano pubblici qui.

## Che cosa è già stato visto
Va dichiarato, perché limita il valore della pre-registrazione:

- **Rendimenti successivi agli eventi: mai calcolati**, in nessun periodo. Il codice legge il futuro in un solo punto, il volume della barra di conferma, e un test lo verifica.
- **Periodo di test: visti solo i conteggi** degli eventi, non i rendimenti.
- **Soglie:** i valori di partenza sono scelte a giudizio. È stato permesso un solo aggiustamento, guardando la selettività delle condizioni nel periodo di calibrazione.
- **Letteratura:** l'evidenza citata nella scheda ha ispirato i setup, quindi la calibrazione non è del tutto ignara di come si sono comportati questi mercati.

## Regola di selettività
Una condizione entra nel punteggio solo se scatta tra il 5% e il 60% degli eventi del periodo di calibrazione, contando solo quelli con dati disponibili. Il punteggio conta le condizioni con pesi uguali.

| Classe | Setup | Condizioni nel punteggio |
|---|---|---|
| crypto | panic | oi_flush, funding_nonpositive, volume_spike_fading |
| crypto | squeeze | shorts_building, funding_mostly_negative, volume_high |
| crypto | overheating | funding_high, volume_high |
| equities | panic | spec_low, vol_index_high, volume_spike_fading |
| equities | squeeze | spec_low, vol_index_drop, volume_high |
| equities | overheating | spec_high, vol_index_low, volume_high |
| bonds | panic | spec_low, vol_index_high |
| bonds | squeeze | spec_low, vol_index_drop, volume_high |
| bonds | overheating | spec_high, vol_index_low, volume_high |
| commodities | panic | spec_low, vol_index_high, volume_spike_fading |
| commodities | squeeze | spec_low, vol_index_drop, volume_high |
| commodities | overheating | spec_high, vol_index_low, volume_high |
| fx | panic | spec_low, vol_index_high |
| fx | squeeze | spec_low, vol_index_drop |
| fx | overheating | spec_high, vol_index_low |

## Eventi e ingresso
- **Trigger, cool-off e fusione in cluster:** come da configurazione. Un cluster è un gruppo di eventi vicini nel tempo.
- **Ingresso:** apertura della prima barra dopo che tutta l'informazione è nota. Per il panico si attende la barra di conferma del volume, quindi l'ingresso è a t+2. Per gli altri setup è a t+1.
- **Date:** COT usabile dal lunedì dopo il martedì di riferimento. Percentili e soglie usano solo il passato.
- **Periodi:** cripto, calibrazione fino al 2023 e test dal 2024. Altri mercati, calibrazione fino al 2014 e test dal 2015.

## Ipotesi primarie
Per ogni classe di mercato, nel solo periodo di test e su tutti gli eventi del setup:

| ID | Ipotesi | Direzione |
|---|---|---|
| **P1** | Dopo un PANICO il rendimento netto batte quello di ingressi casuali | maggiore |
| **Q1** | Dopo uno SQUEEZE il rendimento netto batte quello di ingressi casuali | maggiore |
| **O1** | Dopo un SURRISCALDAMENTO il rendimento è inferiore a quello di ingressi casuali | minore |

- **Orizzonte primario:** 24 ore per le cripto (6 barre), 5 sedute per gli altri mercati. Gli altri orizzonti sono solo descrittivi.
- **Confronto:** per ogni evento, 200 ingressi casuali con seme fisso, stesso mercato, stesso anno solare, stesso orizzonte e stessi costi, lontani dagli eventi di almeno un orizzonte. Si usa l'eccesso rispetto alla loro media.
- **Statistica:** media dei cluster, test t unilaterale sui cluster, con bootstrap dei cluster (almeno 2.000 repliche) come controllo.
- **Soglia:** α = 0,05/3 ≈ 0,0167 per ogni test, una famiglia per classe. Si riporta anche se il risultato regge alla soglia globale 0,05/15 ≈ 0,0033, perché con 5 famiglie la probabilità di almeno un falso positivo arriva a circa il 23%.
- **Tre esiti:** *supportata* se significativa nella direzione attesa. *Non supportata* solo se non significativa con potenza ≥ 50% a d = 0,30. Altrimenti *non informativa*.

## Ipotesi secondarie (solo descrittive)
- **P2/Q2/O2:** punteggio più alto, effetto più forte (Spearman sui cluster).
- Risultati con stop e obiettivo, in multipli del rischio (R), trattati nel laboratorio delle uscite (A1).

## Costi
- **Commissioni:** 0,045% per lato, taker del livello base di Hyperliquid (verificato il 4/11/2026). Alcuni mercati di terzi possono avere commissioni diverse.
- **Slippage (ipotesi, da sostituire con le misure del recorder):** 0,05% per lato sulle cripto, 0,02% sugli altri mercati. Analisi di sensibilità con 0,20% per lato nel panico.
- **Funding:** dato storico Binance per le cripto. Per gli altri mercati si assume zero, perché la storia è troppo breve: è un'ipotesi favorevole.
- **Surriscaldamento:** si tratta di ridurre una posizione, quindi si applica un solo lato di costi.

## Potenza del test primario
Calcolata con t non centrale e cluster indipendenti, usando i conteggi reali del periodo di test.

| Classe | Setup | Cluster calibrazione | Cluster test | d=0,2 | d=0,3 | d=0,5 | Può dire «non supportata»? |
|---|---|---:|---:|---:|---:|---:|---|
| crypto | panic | 174 | 131 | 56% | 90% | 100% | sì |
| crypto | squeeze | 313 | 222 | 80% | 99% | 100% | sì |
| crypto | overheating | 122 | 73 | 33% | 65% | 98% | sì |
| equities | panic | 37 | 45 | 21% | 43% | 87% | no |
| equities | squeeze | 74 | 55 | 25% | 52% | 93% | sì |
| equities | overheating | 14 | 20 | 10% | 19% | 49% | no |
| bonds | panic | 44 | 40 | 18% | 39% | 83% | no |
| bonds | squeeze | 85 | 64 | 29% | 59% | 96% | sì |
| bonds | overheating | 31 | 28 | 13% | 27% | 66% | no |
| commodities | panic | 117 | 97 | 43% | 79% | 100% | sì |
| commodities | squeeze | 210 | 226 | 81% | 99% | 100% | sì |
| commodities | overheating | 142 | 120 | 52% | 87% | 100% | sì |
| fx | panic | 92 | 86 | 38% | 73% | 99% | sì |
| fx | squeeze | 170 | 182 | 71% | 97% | 100% | sì |
| fx | overheating | 72 | 73 | 33% | 65% | 98% | sì |

## Limiti e ipotesi fragili
- **Mercati diversi da quelli negoziati:** futures e Binance sono un'approssimazione di Hyperliquid, con basis e liquidità diverse.
- **Regimi:** il test cripto copre meno di tre anni.
- **Barre incoerenti:** fino al 13% in cereali e metalli in alcuni anni vecchi, il che tocca le condizioni basate su massimi e minimi.
- **Roll:** sette futures non hanno un ETF di controllo e usano una regola più debole.
- **Indice di volatilità FX:** termina il 11/3/2025.
- **Liquidazioni:** escluse dalla v1, perché il backfill non è finito e i canali non sono validati. Potranno entrare solo con una v2 pre-registrata.
- **Sentiment e opzioni complete:** esclusi dai test, salvo gli indici di volatilità.
- **Distribuzioni:** code spesse e cluster sovrapposti possono ridurre la potenza reale.
