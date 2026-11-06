# Stato del progetto

Aggiornato al 6 novembre 2026. Da leggere per primo quando si riprende il lavoro. Branch `roadmap-v0.3`: `main` non contiene questo lavoro.

## Cos'è

BZD raccoglie dati gratuiti su cripto, azioni, bond, materie prime e forex. Li mostra in un'app per PC e manda alert su Telegram. Serve soprattutto a chi compra bene i minimi ma fatica a vendere i massimi. Non esegue ordini e non ha chiavi di trading.

## Cosa gira adesso

Tutto nel Codespace: se si spegne si ferma tutto. `scripts/start-services.sh` dovrebbe riavviare i servizi all'accensione, ma alle riaccensioni del 5 novembre delle 12:17 e delle 17:33 UTC non sono ripartiti, con buchi nei dati dalle 02:42 e dalle 14:25. È successo di nuovo il 6 novembre: dati fermi dalle 00:09 alle 11:57 UTC. Il log di creazione della riaccensione delle 17:33 mostra solo il `postStartCommand` della feature Copilot, non il nostro: il comando non è partito, ma il perché non è chiarito. Dopo ogni riaccensione lanciare `bash scripts/ensure-services.sh` come utente `codespace`. L'avvio automatico da `~/.bashrc` è una scelta dell'utente, ancora da prendere.

| Servizio | Comando | Note |
|---|---|---|
| Recorder | `python3 -u -m bzd.recorder run` | 150 lavori di raccolta |
| Storico Telegram | `python3 -u -m bzd.telegram backfill` | canali pubblici |
| Alert e bot | `.venv/bin/python -u -m bzd.alerts run` | invio attivo, risponde a `/piano` |
| Portafogli HL | `python3 -u -m bzd.wallets run` | classifica ogni giorno, posizioni di 329 conti ogni ora |
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |

Revisione degli alert con l'LLM **accesa**: `.env` ha `BZD_AGENTS=on` dalle 12:39 UTC del 5 novembre, con un tetto di 1,50 $ al mese dal 6 novembre (`BZD_LLM_BUDGET_USD`, prima 0,80 $). Spesa totale 0,36 $ al 5 novembre: l'ultima è la revisione del panico cripto delle 17:45. Gli agenti di ricerca usano lo stesso tetto. I servizi girano come utente `codespace`, Claude come root: dopo ogni modifica da root servono `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio, trovare il PID con `pgrep -f` su un'espressione ancorata, non usare `pkill -f`.

## Cosa esiste

- **App** (`bzd/app.py`, `app.html`, `snapshot.py`): Oggi, Opzioni, Analisi tecnica, Sentiment, Chi compra, Alert, Piano, Test, Motore. Ricerca unica, tabelle ordinabili, tasto Layout con 4 stili (BZD Neon, Arasaka, Militech, Kang Tao). Dal 6 novembre Arasaka è un HUD futuristico (vetro nero, luce cremisi, scansione animata, sezioni numerate) e gli altri tre stili hanno gli stessi tocchi più leggeri. I font (Orbitron, Rajdhani, Share Tech Mono, licenza OFL) stanno in `bzd/fonts/` e li serve l'app stessa. `?tema=arasaka` nell'indirizzo sceglie lo stile. Il sentiment per mercato si apre in meno di mezzo secondo: il conteggio delle parole si rifà in background.
- **Tensione** (`bzd/thermo.py`): il vecchio «calore», da 0 a 100 con 50 come norma del mercato. Parole: tirato in basso, in equilibrio, tirato in alto, anche su Telegram.
- **Sentiment storico** (`bzd/sentiment.py`): estremi sul grafico del prezzo. Cripto da Fear & Greed; gli altri da speculatori COT e indice di volatilità. Soglie non testate, nessun test su cosa succede dopo. I conteggi di parole partono dal 4 novembre e i giorni chiusi restano in `data/sentiment/days.json`.
- **Chi compra** (`bzd/flows.py`, `docs/CHI_COMPRA.md`): chi compra il dip e chi vende il top, con l'intensità, se è oltre il riflesso, e se apre o chiude. Cripto da Binance e Bybit più il denaro; gli altri dal COT (piccoli contro leveraged funds o managed money). Non testato, solo nell'app.
- **Motore, il wiki del programma** (`bzd/wiki.py`, `docs/wiki/`): dal 6 novembre una scheda spiega come lavora tutto, una pagina per parte (7 fonti, 4 raccolte, 14 calcoli, 4 verifiche, 2 uscite), su schema del «LLM Wiki» di Karpathy. Ogni pagina cita codice, cartelle dati e documenti: un clic apre il file alla riga giusta, o la cartella con i file più recenti e le prime righe. Mai `.env` né file di stato. Una mappa neurale in 3D (canvas, nessuna libreria) collega fonti e uscite, con una vista piatta di riserva; un registro tiene le modifiche. `python -m bzd.wiki lint` controlla che ogni citazione e link porti a qualcosa di vero, che ogni modulo di `bzd/` abbia una pagina e che i dati live non siano fermi; lo verifica anche un test. Quando si cambia il motore va aggiornata la pagina, e il lint lo ricorda.
- **Chi compra semplificata (6 novembre):** in alto solo i mercati al dip o al top, con una frase per gruppo («il retail compra forte»). La tabella di tutti i mercati è ridotta a 5 colonne e chiusa. Il grafico non ha più i triangoli; numeri, abitudini e fonti stanno sotto «Dettagli». I portafogli mostrano i 10 mercati più grossi.
- **Portafogli Hyperliquid** (`bzd/wallets.py`, `docs/CHI_COMPRA.md`): dal 6 novembre registra la classifica e le posizioni dei vincenti e perdenti, storici e del mese, esclusi market maker e vault. Nell'app in «Chi compra». Non testato: nessuno storico gratuito, si accumula da ora.
- **Ricerca di altri mercati** (`bzd/lookup.py`): in «Analisi tecnica» si cerca qualunque perpetuo Hyperliquid (tutti gli 11 mercati, `xyz` compreso) o ticker Yahoo. Un nome di azienda trova anche il suo perpetuo («nvidia» dà `xyz:NVDA`). Mostra trend, livelli, se il prezzo è caro, volume, posizioni aperte, funding e cosa tengono i portafogli seguiti. Prezzi scaricati al momento, niente registrazione, niente alert. `python -m bzd.lookup cerca …` nel terminale.
- **Etichette di sentiment, B4** (`bzd/labels.py`): 100 testi scelti una volta il 6 novembre con seme fisso (25 che le parole leggono come paura, 25 come euforia, 50 senza), da etichettare in «Sentiment» nell'app. `python -m bzd.labels confronta` misura l'accordo con il conteggio di parole (kappa, soglia 0,6). Aspetta le etichette dell'utente.
- **Catalogo** (`bzd/literature.py`, `docs/CATALOGO.md`): 334 lavori da OpenAlex e arXiv su 12 temi, nessuno letto. `check` dice se un titolo esiste davvero.
- **Report Gemini** (`docs/letteratura/REPORT_GEMINI.md`): la letteratura caricata dall'utente il 5 novembre. Tutti i 17 lavori citati esistono (`VERIFICA_REPORT_GEMINI.md`). Il report è quasi tutto su azioni USA, poco utile per cripto e posizionamento.
- **Agenti di ricerca** (`bzd/research.py`): il lettore scrive note sugli abstract e controlla le affermazioni di Gemini, il suggeritore scrive bozze di setup v2 «non testate». Il codice scarta citazioni e numeri senza fonte. Il lettore gira su Haiku 5.5 (`BZD_READER_MODEL` per cambiarlo), il suggeritore e le revisioni degli alert restano su Opus 5.5. Primo uso del lettore il 6 novembre, con il via dell'utente: 18 lavori, 13 note e 5 senza abstract, circa 0,01 $. Pertinenza: 1 alta, 6 media, 6 bassa. Le note sono in `docs/letteratura/NOTE.md`. Il supervisore ha fatto il primo giro.
- **Backup e server** (`scripts/backup.sh`, `scripts/server-*.sh`, `deploy/`, `docs/SERVER.md`): backup provato. Il kit per il server è pronto ma mai provato su un server vero.
- **Tag momentum MOM↓ e MOM↑** (ex BYZ e SZT; `bzd/zones.py`, `docs/ZONE_MOMENTUM.md`): 70% indicatori, 30% sentiment, su 4h, 1d, 1w, 1M, 12M. Rinominati il 6 novembre dopo il test v4. «3+» segna il momentum su da almeno 3 sedute di fila, l'unica variante meno sensibile che ha retto.
- **Opzioni** (`bzd/option_models.py`, `option_lab.py`, `docs/OPZIONI_MODELLI.md`): Black-76, SVI, previsione HAR, GEX, contratti economici e cari. Nell'app: il modello passo per passo su un contratto vero e un glossario con i numeri del mercato scelto.
- **Tecnica** (`bzd/technicals.py`): indicatori, reset RSI, supporti e resistenze calcolati dal codice. Un livello di un timeframe lento resta alla stessa quota su quelli veloci, e larghezza e ampiezza minima usano l'ATR mediano.
- **Alert su Telegram:** forti movimenti (`bzd/moves.py`), setup, reset, termometro e opzioni ogni giorno.
- **Piano** (`bzd/plan.py`, `docs/A3_REGOLE.md`): `/piano` sul bot e sezione nell'app.
- **Test** (`bzd/b3.py`, `docs/B3_RISULTATI.md`): eseguito una sola volta, non si rifà.
- **Pre-registrazione v2** (`bzd/v2.py`, `config/setups_v2.json`, `docs/PREREGISTRAZIONE_v2.md`): la bozza del supervisore, congelata il 6 novembre. Long dopo l'incrocio al rialzo della media a 200 sedute, tenuto 20 sedute, su 6 cambi e 8 materie prime, con le azioni come controllo descrittivo. Contano solo eventi dal 9 novembre 2026. Test una volta sola a 100 cluster, circa 3 anni e mezzo, o al 30 novembre 2030. `python -m bzd.v2 stato` conta gli eventi senza calcolare rendimenti.
- **Archivio** (`docs/archivio/`): l'idea iniziale, il primo progetto degli agenti con le sue fonti e il calcolo di potenza. Superati, non guidano il codice.

- **Livelli negli alert (6 novembre):** nei «forte movimento» le distanze da supporto e resistenza partivano dalla chiusura di ieri, non dal prezzo live. Dopo un calo forte un supporto poteva risultare sotto il prezzo quando era già rotto (Nasdaq il 5 novembre). Ora partono dal prezzo live. Se il prezzo live è di un altro strumento (TLT per il future sui bond), i livelli restano quelli del future, e il messaggio lo dice.
- **Alert più chiari (6 novembre):** ogni mercato dice quante conferme ha su quante («Conferme: 0 su 3») e quali mancano. Il risultato del test compare una volta sola. Se la direzione e il prezzo si contraddicono (un long su un mercato già caro, una presa di profitto su uno economico), l'alert lo segnala con «⚠️ In contrasto». Quale dei due pesi di più non è stato testato.

## Cosa sappiamo

- **B3:** su 15 test passa solo il panico cripto (+0,75%), di poco, e non alla soglia più severa.
- **Uscite:** stop + 3R taglia le perdite peggiori ma rende meno del tenere.
- **Tag (misura descrittiva del 5 novembre):** con i vecchi nomi andava nella direzione del nome solo sul mensile; sui timeframe brevi il prezzo continuava nel verso del tag. Da qui il test v4 e il nuovo nome.
- **Trend lungo, v2 storico (6 novembre):** comprare dopo l'incrocio al rialzo della media a 200 sedute e tenere 20 sedute, su cambi e materie prime dal 2008: **non supportata**. Eccesso +0,08% su 489 cluster, t = 0,26, potenza vicina al 100%: l'effetto non c'è. Netto dei costi perde. Il test sui dati futuri resta pre-registrato ma è poco promettente.
- **Test storico v3 (6 novembre):** 15 letture dell'app mai testate, pre-registrate prima di calcolare rendimenti (`docs/PREREGISTRAZIONE_v3.md`, risultati in `docs/V3_STORICO.md`), con la correzione di Holm. **Supportata solo O2:** quando le opzioni sono «economiche», comprare uno straddle rende 22 punti di premio più del solito (p = 0,0023), ma il netto medio resta −1% del premio, e l'effetto sta su EUR/USD, BTC ed ETH, non su SPY, oro e petrolio. **Non supportate, con potenza alta:** opzioni care, BYZ, SZT, reset, tensione, sentiment estremo, chi compra il dip, forti movimenti, supporti e resistenze. BYZ e SZT vanno al contrario con t oltre 3 (dopo BYZ il prezzo ha continuato a scendere), soprattutto sulle cripto. Vendere opzioni senza condizioni ha reso in media (SPY +19% del premio netto), con perdite rare fino a 8 volte il premio; su ETH ha perso. Opzioni sintetiche, prezzate agli indici di volatilità: vedi i limiti nella pre-registrazione.
- **Test storico v4 (6 novembre):** BYZ e SZT letti al contrario, come momentum, su 50 mercati mai usati (`docs/PREREGISTRAZIONE_v4.md`, risultati in `docs/V4_STORICO.md`). **Supportate N1 (BYZ short), N2 (SZT long) e N4 (SZT da 3 sedute, long):** circa +0,6% in 10 sedute rispetto a ingressi casuali. Ma è relativo: tolti i costi lo short dopo BYZ perde (−0,77%) e il long dopo SZT è in pari. Non supportate le versioni più severe (3 sedute per BYZ, soglia ±70); BYZ a −70 va al contrario. Le cripto nuove si muovono con BTC ed ETH, quindi non sono periodi nuovi. Prossimo passo possibile: prova sui dati futuri.
- **Test storico v5 (6 novembre):** BYZ e SZT letti come il vecchio nome, agli estremi (±70, 10 sedute) e sul mensile (±50, 3 mesi), su 99 azioni USA mai usate (`docs/PREREGISTRAZIONE_v5.md`, risultati in `docs/V5_STORICO.md`). **Nessuna supportata.** Agli estremi c'è un piccolo ritorno indietro (+0,4% in 10 sedute, p 0,047 e 0,017), ma non passa Holm; sul mensile niente. Il nome BYZ/SZT non torna.
- **Strategie sulle opzioni in prova (6 novembre):** nove strategie (vendere straddle, strangle, iron condor, put spread, put-write, comprare straddle, e tre condizionate a opzioni economiche o care) si aprono sulla carta ogni giorno dal 7 novembre sui prezzi veri di Deribit e Cboe, con regole fissate prima (`docs/OPZIONI_IN_PROVA.md`). Nessun giudizio prima del 6 novembre 2027. Scheda Opzioni, sezione «Strategie in prova». Nessun ordine.
- **Esito dei test accanto alle letture:** app e alert dicono ora cosa ha detto il test v3 (`bzd/verdicts.py`) al posto di «non testato».
- **Previsione di volatilità:** HAR batte GARCH ed EWMA, ma su BTC ed ETH la volatilità implicita prevede meglio.
- **Segno COT sui setup v1:** su USD/JPY, USD/CHF e USD/CAD il dato COT riguarda la valuta estera, ma i setup congelati lo leggono come se riguardasse la coppia. Su 558 eventi cambierebbe la conferma in 191 (34%). L'esito di B3 non cambia, perché il test usa tutti gli eventi qualunque sia il punteggio. Cambia solo il legame tra punteggio e risultato sul forex, che è secondario. Con il segno giusto le stesse condizioni restano nel punteggio (regola 5-60%). Misura del 5 novembre 2026, senza calcolare rendimenti e senza toccare i file congelati.
- **Chi compra:** il retail cripto si muove contro il prezzo (−0,54 su BTC a 3 giorni) e i top trader no (0,01), ma fuori dalle cripto il riflesso non si vede. Sui dip di BTC il retail supera la soglia nel 24% delle barre, e oltre il riflesso solo nel 2%. Dopo non si vede una differenza utile. Misura descrittiva, non un test.
- **Google Trends:** lo storico per parola blocca le richieste automatiche e non va forzato. Si usa solo il feed pubblico delle tendenze.
- **Storico FXE:** non c'è su DoltHub, e EVZ è fermo a marzo 2025. L'euro ha poche opzioni liquide e oggi non compare tra i mercati delle opzioni.
- **Sentiment:** è un conteggio di parole grezzo e non validato. Cina, Yuan e metalli rari hanno ancora pochi testi.

## Decisioni dell'utente

- Solo fonti gratuite e leggibili, niente API di X.
- Niente chiamate a pagamento agli agenti senza chiedere: gli agenti restano fermi per ora.
- Alert su Telegram: insight e direzione («potenziale long») sempre con l'esito del test. Entry, stop e target solo nell'app.
- 4h solo nell'app, per non riempire il bot. Reset: ipervenduto in uptrend, ipercomprato in downtrend.
- Paura rossa, euforia verde. App per PC, non per telefono, e fuori da AMBRA.
- Le operazioni reali dell'utente (A2) più avanti: non proporle prima che ne riparli.
- Regola sugli agenti: possono citare e dare un parere, non possono cambiare numeri o bloccare un alert.
- L'indirizzo Hyperliquid dell'utente non va chiesto. Nessuna chiave di trading, nessun ordine.

## Prossimi passi

L'utente ha deciso il 5 novembre: **prima l'app, gli alert e le indicazioni devono avere senso, poi il server.**

1. **Agenti di ricerca:** il lettore ha girato. Il suggeritore è diventato il supervisore (deciso il 6 novembre): su Opus ricontrolla ogni nota di Haiku sul suo abstract (regge, da correggere, forzata) e scrive bozze solo dalle note che reggono. Gira di rado, una volta al mese o ogni 10 note nuove: `stima` dice quando. La bozza sul trend lungo è pre-registrata come v2: il test storico 2008-2026 dice «non supportata». Tetto alzato a 1,50 $ il 6 novembre. Primo giro lo stesso giorno, circa 0,18 $: 10 note reggono, 3 forzate (Almgren-Chriss, Baker-Wurgler, Gu-Kelly-Xiu), una bozza in `docs/letteratura/IDEE_V2.md` (trend lungo su cambi e materie prime, azioni come controllo). Non testata: serve una pre-registrazione v2.
2. **App e alert:** rivedere che ogni indicazione sia chiara e coerente con i test.
3. **Server, poi backup fuori dal Codespace:** il kit è pronto (`docs/SERVER.md`). `data/` e `.env` non sono su GitHub.

## Domande aperte

- Portare l'avvio automatico anche in `~/.bashrc` e in `postAttachCommand`? Senza server è l'unica protezione se il Codespace non lancia il `postStartCommand`.
- Tag momentum anche sul bot? Consiglio: prima la prova sui dati futuri.
- Sui timeframe brevi, tag con filtro del trend? Va misurato con una nuova pre-registrazione su dati futuri.
- Rimettere l'ordinamento per variazione degli indicatori? L'utente ha tolto le colonne Δ.
- Prezzi di bond non USA, per calore e tecnica? Oggi quella divisione esiste solo nel sentiment.
- Segno COT dal vivo: oggi le conferme e la soglia per la revisione dell'agente su quelle tre coppie restano sbagliate. Correggerle ora o solo nella v2? Finora nessun alert su queste coppie.
- Portare il lavoro su `main` con una pull request.

## Per dopo

Agente letteratura e suggeritore di setup, solo con il via libera dell'utente: un'idea nuova resta «non testata» finché non passa una pre-registrazione v2 su dati nuovi. Poi 100 etichette di sentiment, e il collegamento a Hyperliquid (fasi C della `ROADMAP.md`).
