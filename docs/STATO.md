# Stato del progetto

Aggiornato al 5 novembre 2026. Da leggere per primo quando si riprende il lavoro. Branch `roadmap-v0.3`: `main` non contiene questo lavoro.

## Cos'è

BZD raccoglie dati gratuiti su cripto, azioni, bond, materie prime e forex. Li mostra in un'app per PC e manda alert su Telegram. Serve soprattutto a chi compra bene i minimi ma fatica a vendere i massimi. Non esegue ordini e non ha chiavi di trading.

## Cosa gira adesso

Tutto nel Codespace: se si spegne si ferma tutto. `scripts/start-services.sh` dovrebbe riavviare i servizi all'accensione, ma alla riaccensione del 5 novembre alle 12:17 UTC non sono ripartiti, con un buco nei dati dalle 02:42. La causa non è stata verificata: controllare `pgrep -f bzd` dopo ogni riaccensione.

| Servizio | Comando | Note |
|---|---|---|
| Recorder | `python3 -u -m bzd.recorder run` | 150 lavori di raccolta |
| Storico Telegram | `python3 -u -m bzd.telegram backfill` | canali pubblici |
| Alert e bot | `.venv/bin/python -u -m bzd.alerts run` | invio attivo, risponde a `/piano` |
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |

Agenti LLM spenti (`BZD_AGENTS`), spesa totale finora 0,24 $. I servizi girano come utente `codespace`, Claude come root: dopo ogni modifica da root servono `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio, trovare il PID con `pgrep -f` su un'espressione ancorata, non usare `pkill -f`.

## Cosa esiste

- **App** (`bzd/app.py`, `app.html`, `snapshot.py`): Oggi, Opzioni, Analisi tecnica, Sentiment, Alert, Piano, Test. Ricerca unica, tabelle ordinabili, tasto Layout con 4 stili (BZD Neon, Arasaka, Militech, Kang Tao).
- **Tensione** (`bzd/thermo.py`): il vecchio «calore», da 0 a 100 con 50 come norma del mercato. Parole: tirato in basso, in equilibrio, tirato in alto, anche su Telegram.
- **Sentiment storico** (`bzd/sentiment.py`): estremi sul grafico del prezzo. Cripto da Fear & Greed; gli altri da speculatori COT e indice di volatilità. Soglie non testate, nessun test su cosa succede dopo. I conteggi di parole partono dal 4 novembre e i giorni chiusi restano in `data/sentiment/days.json`.
- **Tag BYZ e SZT** (`bzd/zones.py`, `docs/ZONE_BYZ_SZT.md`): 70% indicatori, 30% sentiment, su 4h, 1d, 1w, 1M, 12M.
- **Opzioni** (`bzd/option_models.py`, `option_lab.py`, `docs/OPZIONI_MODELLI.md`): Black-76, SVI, previsione HAR, GEX, contratti economici e cari. Nell'app: il modello passo per passo su un contratto vero e un glossario con i numeri del mercato scelto.
- **Tecnica** (`bzd/technicals.py`): indicatori, reset RSI, supporti e resistenze calcolati dal codice. Un livello di un timeframe lento resta alla stessa quota su quelli veloci, e larghezza e ampiezza minima usano l'ATR mediano.
- **Alert su Telegram:** forti movimenti (`bzd/moves.py`), setup, reset, termometro e opzioni ogni giorno.
- **Piano** (`bzd/plan.py`, `docs/A3_REGOLE.md`): `/piano` sul bot e sezione nell'app.
- **Test** (`bzd/b3.py`, `docs/B3_RISULTATI.md`): eseguito una sola volta, non si rifà.
- **Archivio** (`docs/archivio/`): l'idea iniziale, il primo progetto degli agenti con le sue fonti e il calcolo di potenza. Superati, non guidano il codice.

## Cosa sappiamo

- **B3:** su 15 test passa solo il panico cripto (+0,75%), di poco, e non alla soglia più severa.
- **Uscite:** stop + 3R taglia le perdite peggiori ma rende meno del tenere.
- **Tag:** va nella direzione del nome solo sul mensile. Sui timeframe brevi SZT ha continuato a salire. Misura descrittiva, non un test.
- **Previsione di volatilità:** HAR batte GARCH ed EWMA, ma su BTC ed ETH la volatilità implicita prevede meglio.
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

1. **Server:** l'utente è d'accordo a spostare tutto su un server continuando a lavorare dal Codespace. Da fare: l'utente crea un server Ubuntu; poi installazione, avvio automatico, backup di `data/` e aggiornamento con un comando. Il bot deve girare in un posto solo.
2. **Backup:** `data/` e `.env` non sono su GitHub. Le registrazioni dal vivo e i log non si possono riscaricare.
3. **Catalogo della letteratura:** partire dal PDF che l'utente deve ancora caricare in `docs/`, poi OpenAlex e arXiv. I riassunti li fa l'utente su Claude Pro e si verificano sul catalogo.

## Domande aperte

- Tag BYZ e SZT anche sul bot? Consiglio: aspettare qualche settimana di osservazione.
- Sui timeframe brevi, tag con filtro del trend? Va misurato con una nuova pre-registrazione su dati futuri.
- Rimettere l'ordinamento per variazione degli indicatori? L'utente ha tolto le colonne Δ.
- Prezzi di bond non USA, per calore e tecnica? Oggi quella divisione esiste solo nel sentiment.
- Portare il lavoro su `main` con una pull request.

## Per dopo

Agente letteratura e suggeritore di setup, solo con il via libera dell'utente: un'idea nuova resta «non testata» finché non passa una pre-registrazione v2 su dati nuovi. Poi 100 etichette di sentiment, e il collegamento a Hyperliquid (fasi C della `ROADMAP.md`).
