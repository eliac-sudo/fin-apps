# Roadmap

Scritta il 24 novembre 2026. Cosa manca, in ordine di urgenza. Lo stato di oggi è in [STATO.md](STATO.md); qui solo cosa resta da fare e perché.

## Cosa ci dicono i test fino a oggi

Su 46 ipotesi pre-registrate (B3, v2–v6) più 484 combinazioni (v7) reggono solo il panico cripto (B3, di poco), le opzioni «economiche» (v3, O2, ma il netto resta negativo) e il momentum (v4, che tolti i costi è in pari). Il v6 e il v7 di oggi ([V6_STORICO.md](V6_STORICO.md), [V7_ESAME.md](V7_ESAME.md)) non ne aggiungono. Nel v7, 484 combinazioni di letture cercate e controllate su periodi separati: all'esame nessuna regge. Nel v6: liquidità della Fed, dollaro forte e impatto alto non reggono alla correzione per test multipli, e stablecoin e proiezioni della Fed hanno troppi pochi casi. Il programma descrive bene i mercati, ma non ha ancora un segnale con un vantaggio netto dimostrato. La roadmap mette prima ciò che protegge i dati, poi ciò che può trovare un vantaggio vero.

## 1. Subito: non perdere dati

| Cosa | Perché | Come |
|---|---|---|
| **Backup fuori dal server** | Il backup di ogni notte sta sullo stesso disco: se il server muore, perdiamo tutto ciò che non ha storico gratuito (opzioni, book, Telegram, Kalshi, Polymarket, previsioni OCSE per edizione). | Una copia cifrata ogni notte su uno spazio esterno (Hetzner Storage Box o Backblaze B2, pochi euro al mese). **Serve una tua decisione e un account.** |
| **Allarme se un servizio si ferma** | Dal 7 al 23 novembre i servizi sono rimasti fermi 16 giorni senza che nessuno se ne accorgesse. | Un controllo ogni ora che manda un solo messaggio Telegram se il recorder è in ritardo o un servizio è giù. Gratis. |
| **Allarme sulla chiave API scaduta** | Il 23 novembre la chiave Anthropic era scaduta e gli alert partivano senza revisione. | Lo stesso controllo legge l'ultimo errore di `data/agents/reviews.jsonl`. |
| **File giornaliero delle cripto fermo al 3 novembre** | `hist/crypto/*_candles_1d` non si aggiorna; oggi lo aggiriamo con le barre a 4 ore, ma altre parti potrebbero leggerlo. | Aggiornarlo nel refresh delle cripto, o toglierlo e usare ovunque le 4 ore. |

## 2. Questo mese: dati che servono ai test

- **Versioni storiche dei dati macro (ALFRED):** con le versioni di allora si possono testare anche l'indice delle condizioni finanziarie di Chicago e altre serie che oggi escludiamo perché ricalcolate all'indietro.
- **Previsioni contro realtà:** per ogni previsione (Fed, previsori USA e BCE, OCSE) affiancare il dato uscito dopo, così l'app mostra chi sbaglia di più e in che direzione. È un controllo, non un segnale, ma dice quanto fidarsi.
- **Calibrazione di Kalshi e Polymarket:** quando una domanda si chiude, salvare l'esito. Fra qualche mese si vede se il 70% diventa davvero 7 volte su 10.
- **Chiave EIA gratuita** (previsioni sull'energia): serve che tu la registri su eia.gov.
- **Il FMI blocca il server:** provare il nuovo portale dati (api.imf.org) o una fonte che ne ripubblica le previsioni.
- **Bond non USA:** fatto in parte il 25 novembre 2026. Bund ogni giorno (Bundesbank e ETF EXX6) e spread BTP–Bund ogni mese (BCE). Manca un BTP giornaliero gratuito con storia lunga.
- **Altre classi, dopo:** curva del VIX come lettura, materie prime agricole e soft con il COT (cacao, caffè, zucchero, bestiame), cambi emergenti (USD/CNH, USD/MXN).

## 3. Prove sui dati futuri, già in corso

| Cosa | Fino a | Cosa si decide alla fine |
|---|---|---|
| Strangle BTC coperto, bot sul testnet | 24 novembre 2027 | Se regge, se passare al conto vero e con quanto (decisione tua) |
| Nove strategie sulle opzioni, sulla carta | 6 novembre 2027 | Quali tenere |
| Trend lungo (v2) | in corso dal 9 novembre 2026 | Probabilmente niente: storico poco promettente |
| AIsetups | ogni proposta seguita fino alla chiusura | Dopo 100 proposte chiuse, se valgono più del caso |
| v8: posizione bassa, dollaro forte, impatto alto, paura ed euforia cripto | 60 cluster ciascuna, o il 24 novembre 2028 | Se una regge, diventa un setup |
| v9: copia sulla carta dei 20 migliori trader Hyperliquid contro 20 a caso | 25 maggio 2027 | Se copiare guadagna dopo i costi: solo allora si parla di un bot vero, con una tua decisione sulla cifra |

## 4. Prossimi test da pre-registrare

Si scrivono prima, si conta, si lancia una volta. Le idee nate guardando i risultati del v6 **non si riprovano sullo stesso storico**: si provano solo sui dati che arrivano da ora.

1. **Fatto con il v8** (prova sui dati futuri partita il 25 novembre 2026): «posizione bassa nell'anno → long 10 sedute» (v7: positiva nei tre periodi, p 0,025 all'esame contro soglia 0,017), dollaro in forte rialzo (L3, p 0,015 contro soglia 0,0125) e impatto alto (L4, p 0,012 contro 0,010). Regole identiche a v6 e v7, giudizio dopo almeno 100 cluster nuovi.
2. **Stablecoin sulle cripto (L2):** stessa regola, sui dati futuri. Serve tempo: oggi i casi sono 29.
3. **BZD, la capitolazione:** pre-registrarla per i dati futuri. È rara, quindi servono anni.
4. **Proiezioni della Fed (F1):** solo 12 edizioni dure dal 2016; si riguarda tra qualche anno.
5. **Segno COT su USD/JPY, USD/CHF, USD/CAD:** correggerlo nella prossima versione dei setup, non in quella congelata.

## 5. L'app

- **Liquidità:** grafico per mercato di volumi e impatto negli ultimi mesi, sulla pagina del ticker.
- **Previsioni:** colonna «cosa è successo davvero» quando il dato esce.
- **Test:** la scheda già mostra tutto; aggiungere una riga di sintesi in alto con «quante ipotesi reggono su quante».

## Cosa non faremo

- Fonti a pagamento o l'API di X.
- Passare il bot al conto vero prima della fine della prova, o senza una tua decisione con la cifra.
- Trasformare in regola una lettura che non ha retto un test.
