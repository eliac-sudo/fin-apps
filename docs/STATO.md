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
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |

Revisione degli alert con l'LLM **accesa**: `.env` ha `BZD_AGENTS=on` dalle 12:39 UTC del 5 novembre, con un tetto di 0,80 $ al mese (`BZD_LLM_BUDGET_USD`). Spesa totale 0,36 $ al 5 novembre: l'ultima è la revisione del panico cripto delle 17:45. Gli agenti di ricerca usano lo stesso tetto. I servizi girano come utente `codespace`, Claude come root: dopo ogni modifica da root servono `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio, trovare il PID con `pgrep -f` su un'espressione ancorata, non usare `pkill -f`.

## Cosa esiste

- **App** (`bzd/app.py`, `app.html`, `snapshot.py`): Oggi, Opzioni, Analisi tecnica, Sentiment, Chi compra, Alert, Piano, Test. Ricerca unica, tabelle ordinabili, tasto Layout con 4 stili (BZD Neon, Arasaka, Militech, Kang Tao).
- **Tensione** (`bzd/thermo.py`): il vecchio «calore», da 0 a 100 con 50 come norma del mercato. Parole: tirato in basso, in equilibrio, tirato in alto, anche su Telegram.
- **Sentiment storico** (`bzd/sentiment.py`): estremi sul grafico del prezzo. Cripto da Fear & Greed; gli altri da speculatori COT e indice di volatilità. Soglie non testate, nessun test su cosa succede dopo. I conteggi di parole partono dal 4 novembre e i giorni chiusi restano in `data/sentiment/days.json`.
- **Chi compra** (`bzd/flows.py`, `docs/CHI_COMPRA.md`): chi compra il dip e chi vende il top, con l'intensità, se è oltre il riflesso, e se apre o chiude. Cripto da Binance e Bybit più il denaro; gli altri dal COT (piccoli contro leveraged funds o managed money). Non testato, solo nell'app.
- **Catalogo** (`bzd/literature.py`, `docs/CATALOGO.md`): 334 lavori da OpenAlex e arXiv su 12 temi, nessuno letto. `check` dice se un titolo esiste davvero.
- **Report Gemini** (`docs/letteratura/REPORT_GEMINI.md`): la letteratura caricata dall'utente il 5 novembre. Tutti i 17 lavori citati esistono (`VERIFICA_REPORT_GEMINI.md`). Il report è quasi tutto su azioni USA, poco utile per cripto e posizionamento.
- **Agenti di ricerca** (`bzd/research.py`): il lettore scrive note sugli abstract e controlla le affermazioni di Gemini, il suggeritore scrive bozze di setup v2 «non testate». Il codice scarta citazioni e numeri senza fonte. Costruiti e provati senza spendere: il primo uso a pagamento aspetta il via dell'utente.
- **Backup e server** (`scripts/backup.sh`, `scripts/server-*.sh`, `deploy/`, `docs/SERVER.md`): backup provato. Il kit per il server è pronto ma mai provato su un server vero.
- **Tag BYZ e SZT** (`bzd/zones.py`, `docs/ZONE_BYZ_SZT.md`): 70% indicatori, 30% sentiment, su 4h, 1d, 1w, 1M, 12M.
- **Opzioni** (`bzd/option_models.py`, `option_lab.py`, `docs/OPZIONI_MODELLI.md`): Black-76, SVI, previsione HAR, GEX, contratti economici e cari. Nell'app: il modello passo per passo su un contratto vero e un glossario con i numeri del mercato scelto.
- **Tecnica** (`bzd/technicals.py`): indicatori, reset RSI, supporti e resistenze calcolati dal codice. Un livello di un timeframe lento resta alla stessa quota su quelli veloci, e larghezza e ampiezza minima usano l'ATR mediano.
- **Alert su Telegram:** forti movimenti (`bzd/moves.py`), setup, reset, termometro e opzioni ogni giorno.
- **Piano** (`bzd/plan.py`, `docs/A3_REGOLE.md`): `/piano` sul bot e sezione nell'app.
- **Test** (`bzd/b3.py`, `docs/B3_RISULTATI.md`): eseguito una sola volta, non si rifà.
- **Archivio** (`docs/archivio/`): l'idea iniziale, il primo progetto degli agenti con le sue fonti e il calcolo di potenza. Superati, non guidano il codice.

- **Livelli negli alert (6 novembre):** nei «forte movimento» le distanze da supporto e resistenza partivano dalla chiusura di ieri, non dal prezzo live. Dopo un calo forte un supporto poteva risultare sotto il prezzo quando era già rotto (Nasdaq il 5 novembre). Ora partono dal prezzo live. Se il prezzo live è di un altro strumento (TLT per il future sui bond), i livelli restano quelli del future, e il messaggio lo dice.
- **Alert più chiari (6 novembre):** ogni mercato dice quante conferme ha su quante («Conferme: 0 su 3») e quali mancano. Il risultato del test compare una volta sola. Se la direzione e il prezzo si contraddicono (un long su un mercato già caro, una presa di profitto su uno economico), l'alert lo segnala con «⚠️ In contrasto». Quale dei due pesi di più non è stato testato.

## Cosa sappiamo

- **B3:** su 15 test passa solo il panico cripto (+0,75%), di poco, e non alla soglia più severa.
- **Uscite:** stop + 3R taglia le perdite peggiori ma rende meno del tenere.
- **Tag:** va nella direzione del nome solo sul mensile. Sui timeframe brevi SZT ha continuato a salire. Misura descrittiva, non un test.
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

1. **Agenti di ricerca:** `python -m bzd.research stima`, poi `leggi --paga` e `idee --paga` quando l'utente dà il via. Circa 1,40 $ con il modello predefinito, più del tetto attuale di 0,80 $: senza alzarlo il lettore si ferma a metà e toglie spazio alle revisioni degli alert.
2. **App e alert:** rivedere che ogni indicazione sia chiara e coerente con i test.
3. **Server, poi backup fuori dal Codespace:** il kit è pronto (`docs/SERVER.md`). `data/` e `.env` non sono su GitHub.

## Domande aperte

- Portare l'avvio automatico anche in `~/.bashrc` e in `postAttachCommand`? Senza server è l'unica protezione se il Codespace non lancia il `postStartCommand`.
- Tag BYZ e SZT anche sul bot? Consiglio: aspettare qualche settimana di osservazione.
- Sui timeframe brevi, tag con filtro del trend? Va misurato con una nuova pre-registrazione su dati futuri.
- Rimettere l'ordinamento per variazione degli indicatori? L'utente ha tolto le colonne Δ.
- Prezzi di bond non USA, per calore e tecnica? Oggi quella divisione esiste solo nel sentiment.
- Segno COT dal vivo: oggi le conferme e la soglia per la revisione dell'agente su quelle tre coppie restano sbagliate. Correggerle ora o solo nella v2? Finora nessun alert su queste coppie.
- Portare il lavoro su `main` con una pull request.

## Per dopo

Agente letteratura e suggeritore di setup, solo con il via libera dell'utente: un'idea nuova resta «non testata» finché non passa una pre-registrazione v2 su dati nuovi. Poi 100 etichette di sentiment, e il collegamento a Hyperliquid (fasi C della `ROADMAP.md`).
