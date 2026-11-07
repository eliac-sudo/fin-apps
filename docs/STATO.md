# Stato del progetto

Aggiornato al 7 novembre 2026. Da leggere per primo quando si riprende il lavoro. Branch `roadmap-v0.3`: `main` non contiene questo lavoro. La cronaca delle modifiche sta in `docs/wiki/log.md` e nella storia git; qui c'è solo com'è adesso.

## Cos'è

BZD raccoglie dati gratuiti su cripto, azioni, bond, materie prime e forex. Li mostra in un'app per PC e manda alert su Telegram. Serve soprattutto a chi compra bene i minimi ma fatica a vendere i massimi. Non esegue ordini e non ha chiavi di trading.

## Cosa gira

Tutto nel Codespace: se si spegne si ferma tutto. Alla riaccensione `scripts/start-services.sh` non sempre parte (5 e 6 novembre). **Dopo ogni riaccensione:** `su codespace -c 'bash scripts/ensure-services.sh'`. Lo lancia Claude, senza chiedere.

| Servizio | Comando | Note |
|---|---|---|
| Recorder | `python3 -u -m bzd.recorder run` | 150 lavori di raccolta |
| Storico Telegram | `python3 -u -m bzd.telegram backfill` | canali pubblici |
| Alert e bot | `.venv/bin/python -u -m bzd.alerts run` | invio attivo, risponde a `/piano` |
| Portafogli HL | `python3 -u -m bzd.wallets run` | classifica ogni giorno, posizioni ogni ora |
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |

- I servizi girano come utente `codespace`, Claude come root. Dopo ogni modifica da root: `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio si cerca il PID con `pgrep -f` su un'espressione ancorata, non con `pkill -f` largo. Lo script avvia anche l'app: prima va fermata un'eventuale copia lanciata da root.
- Revisione degli alert con l'LLM **accesa** (`BZD_AGENTS=on`), tetto 1,50 $ al mese (`BZD_LLM_BUDGET_USD`), condiviso con gli agenti di ricerca. Spesa totale 0,36 $ al 5 novembre.
- Il push su GitHub usa il token copiato con `gl` da un terminale di VS Code: quando scade, il push fallisce finché l'utente non rilancia `gl`.

## L'app, scheda per scheda

Il codice sta in `bzd/app.py` (server), `bzd/app.html` (pagina) e `bzd/snapshot.py` (i dati). Il tasto Layout ha 4 stili. I dati si ricostruiscono in circa 30 secondi all'avvio, poi restano in cache.

- **Oggi:** la frase del giorno, la **forza** per gruppo (0–100 rispetto alla propria storia: ipervenduto, sotto la norma, nella norma, sopra la norma, ipercomprato; `bzd/thermo.py`) e la tabella del momentum («▼ scende forte» e «▲ sale forte» sotto −50 e sopra +50; `bzd/zones.py`). Poi il riquadro **BYZ, la capitolazione** (`bzd/capitulation.py`): scatta solo con un asset forte, un calo profondo, la volatilità spenta e il prezzo di lato da 40 sedute. È una regola nuova e non testata, e oggi non scatta su nessun mercato.
- **Pagina del ticker:** si apre cliccando un asset ovunque o dalla ricerca. Riassume Oggi, Analisi tecnica, Opzioni, Sentiment e Chi compra, con un pulsante per ogni scheda.
- **Opzioni:** costo rispetto al movimento previsto (Black-76, SVI, HAR), contratti economici e cari, gamma (`bzd/option_lab.py`, `docs/OPZIONI_MODELLI.md`).
- **Analisi tecnica:** grafico con livelli disegnati dal codice, RSI, indicatori a confronto, e la ricerca di qualunque perpetuo Hyperliquid o ticker Yahoo (`bzd/technicals.py`, `bzd/lookup.py`).
- **Sentiment:** paura ed euforia per argomento nelle ultime 24 ore e nei 7 giorni, gli estremi sul grafico del prezzo, le 100 etichette B4 da assegnare (`bzd/sentiment.py`, `bzd/labels.py`).
- **Chi compra:** retail e grossi come percentile sui loro ultimi 3 anni, e i portafogli Hyperliquid profittevoli (`bzd/flows.py`, `bzd/wallets.py`, `docs/CHI_COMPRA.md`).
- **Alert e Piano:** gli alert di Telegram con i livelli, e il calcolo di dimensione, stop e obiettivo (`bzd/alerts.py`, `bzd/plan.py`).
- **Test:** tutte le ipotesi e i risultati, letti dai file congelati in `config/`; le strategie sulle opzioni in prova; l'elenco di ciò che non è testato. Le altre schede rimandano qui.
- **Motore:** il wiki del programma in `docs/wiki/`, una pagina per parte. `python -m bzd.wiki lint` controlla che ogni citazione porti a un file vero e che ogni modulo abbia una pagina; lo verifica anche un test.

Fuori dall'app: catalogo di 334 lavori (`docs/CATALOGO.md`), note degli agenti di ricerca (`docs/letteratura/`), backup e kit per il server mai provato su un server vero (`docs/SERVER.md`), vecchi progetti in `docs/archivio/`.

## Cosa sappiamo

Il dettaglio di ogni test è nella scheda Test e nei file `docs/V*_STORICO.md`. Ogni test è stato pre-registrato ed eseguito una volta sola.

- **B3, i setup degli alert:** su 15 passa solo il panico cripto (+0,75%), di poco e non alla soglia più severa.
- **v2, trend lungo:** l'incrocio della media a 200 sedute non dà vantaggio (+0,08%, t = 0,26). La prova sui dati futuri conta eventi dal 9 novembre 2026 ma è poco promettente.
- **v3, le 15 letture dell'app:** regge solo O2: con opzioni «economiche» comprare uno straddle rende 22 punti di premio più del solito, ma il netto resta −1%. Le altre 14 non reggono.
- **v4, momentum su 50 mercati nuovi:** dopo «scende forte» e «sale forte» il prezzo continua per 10 sedute, circa +0,6% rispetto al caso, ma tolti i costi lo short perde e il long è in pari. Regge anche «sale forte da 3 sedute».
- **v5, BYZ e SZT letti come il nome:** nessuna ipotesi regge su 99 azioni USA nuove. Per questo BYZ non è più un nome del momentum.
- **Uscite:** stop + 3R taglia le perdite peggiori ma rende meno del tenere.
- **Volatilità:** HAR batte GARCH ed EWMA, ma su BTC ed ETH la volatilità implicita prevede meglio.
- **Opzioni in prova:** nove strategie sulla carta dal 7 novembre 2026 sui prezzi veri (`docs/OPZIONI_IN_PROVA.md`). Nessun giudizio prima del 6 novembre 2027.
- **Chi compra:** il retail cripto va contro il prezzo (−0,54 su BTC a 3 giorni), i top trader no. Seguire chi compra il dip non ha aiutato (F1, F2).
- **Segno COT su USD/JPY, USD/CHF e USD/CAD:** i setup congelati lo leggono al contrario. L'esito di B3 non cambia; le conferme dal vivo su quelle coppie sì.
- **Limiti delle fonti:** Google Trends solo dal feed pubblico; nessuno storico FXE ed EVZ fermo a marzo 2025; il sentiment è un conteggio di parole non validato, e Cina, Yuan e metalli rari hanno pochi testi.

## Decisioni dell'utente

- Solo fonti gratuite e leggibili, niente API di X.
- Niente chiamate a pagamento agli agenti senza chiedere.
- Alert su Telegram: insight e direzione («potenziale long»), sempre con l'esito del test. Entry, stop e target solo nell'app. Il 4h solo nell'app.
- Paura rossa, euforia verde. App per PC, non per telefono, e fuori da AMBRA.
- Le operazioni reali dell'utente (A2) più avanti: non proporle prima che ne riparli.
- Gli agenti possono citare e dare un parere, non cambiare numeri o bloccare un alert.
- L'indirizzo Hyperliquid dell'utente non va chiesto. Nessuna chiave di trading, nessun ordine.
- Claude ha pieno controllo su script e servizi del progetto (7 novembre).

## Prossimi passi

Deciso il 5 novembre: **prima l'app, gli alert e le indicazioni devono avere senso, poi il server.**

1. **App e alert:** che ogni indicazione sia chiara e coerente con i test.
2. **Agenti di ricerca:** il supervisore (Opus) ricontrolla le note del lettore (Haiku) e scrive bozze solo da quelle che reggono, una volta al mese o ogni 10 note nuove (`python -m bzd.research stima`). Un'idea resta «non testata» finché non passa una pre-registrazione su dati nuovi.
3. **Server, poi backup fuori dal Codespace:** il kit è pronto. `data/` e `.env` non sono su GitHub.

## Domande aperte

- Avvio automatico anche da `~/.bashrc` o `postAttachCommand`, visto che il `postStartCommand` a volte non parte?
- BYZ capitolazione: pre-registrarla per una prova sui dati futuri? È rara, quindi servirebbero anni.
- Momentum anche sul bot? Consiglio: prima la prova sui dati futuri.
- Segno COT dal vivo su USD/JPY, USD/CHF e USD/CAD: correggerlo ora o nella prossima versione dei setup?
- Prezzi di bond non USA, per la forza e la tecnica?
- Portare il lavoro su `main` con una pull request.
