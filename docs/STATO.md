# Stato del progetto

Aggiornato al 24 novembre 2026. Da leggere per primo quando si riprende il lavoro. Branch `roadmap-v0.3`, unito in `main` il 24 novembre 2026 (pull request 2). La cronaca delle modifiche sta in `docs/wiki/log.md` e nella storia git; qui c'è solo com'è adesso.

## Cos'è

BZD raccoglie dati gratuiti su cripto, azioni, bond, materie prime e forex. Li mostra in un'app per PC e manda alert su Telegram. Serve soprattutto a chi compra bene i minimi ma fatica a vendere i massimi. Gli ordini li manda solo il bot Deribit, per ora sul testnet con soldi finti: vende lo strangle BTC da maker e lo copre sul perpetuo (`docs/BOT_DERIBIT.md`).

## Cosa gira

**Dal 24 novembre 2026 alle 16:39 UTC tutti i servizi girano sul server Hetzner** (`bzd-server`, `docs/SERVER.md`) come servizi systemd con utente `bzd` in `/opt/bzd`. Ripartono da soli se cadono o se il server si riavvia. Il Codespace serve solo per lo sviluppo: con `.sul-server` presente non accende niente e apre solo il tunnel per l'app sulla porta 8787. Il codice si aggiorna con `bash scripts/server-update.sh bzd-server`, che Claude lancia senza chiedere. Lo stato si controlla con `ssh bzd-server 'systemctl is-active bzd-recorder bzd-wallets bzd-alerts bzd-vol-bot bzd-app'`; i log sono in `/opt/bzd/data/*.log`. Il backup gira ogni notte alle 03:30 UTC in `/home/bzd/bzd-backups`, sullo stesso disco: una copia fuori dal server manca ancora. Dopo una riaccensione del Codespace, `su codespace -c 'bash scripts/ensure-services.sh'` riapre solo il tunnel. Nella tabella sotto ci sono i comandi che i servizi eseguono. **Buco nei dati dal 7 al 23 novembre 2026:** i servizi si sono fermati il 7 verso le 14 e nessuno li ha riaccesi per 16 giorni. Quello che si scarica di nuovo (prezzi giornalieri, COT) si recupera; le fotografie dal vivo (opzioni in prova, posizioni Hyperliquid, Telegram) no. Il 23 novembre i servizi erano di nuovo fermi da circa 4 ore, riaccesi alle 16 UTC circa.

| Servizio | Comando | Note |
|---|---|---|
| Recorder | `python3 -u -m bzd.recorder run` | 150 lavori di raccolta |
| Storico Telegram | `python3 -u -m bzd.telegram backfill` | canali pubblici |
| Alert e bot | `.venv/bin/python -u -m bzd.alerts run` | invio attivo, risponde a `/piano` |
| Portafogli HL | `python3 -u -m bzd.wallets run` | classifica ogni giorno, posizioni ogni ora |
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |
| Bot Deribit | `.venv/bin/python -u -m bzd.vol_bot run` | parte solo con `DERIBIT_CLIENT_ID` in `.env`; testnet. Dal 24 novembre 2026 solo lo strangle coperto (v2); la prima versione a put spread è chiusa e archiviata in `data/vol_bot_v1_archivio/` |

- Nel Codespace, prima del server, i servizi giravano come utente `codespace` e Claude come root. Dopo ogni modifica da root: `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio si cerca il PID con `pgrep -f` su un'espressione ancorata, non con `pkill -f` largo. Lo script avvia anche l'app: prima va fermata un'eventuale copia lanciata da root.
- Revisione degli alert con l'LLM **accesa** (`BZD_AGENTS=on`), tetto 1,50 $ al mese (`BZD_LLM_BUDGET_USD`), condiviso con gli agenti di ricerca. Spesa totale 0,36 $ al 5 novembre. Il 23 novembre la chiave API Anthropic era scaduta: le revisioni fallivano e gli alert partivano senza. Sostituita lo stesso giorno; il 24 novembre risponde. Se torna «chiave API non valida» in `data/agents/reviews.jsonl`, va rinnovata in `.env`.
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
- **Esito accanto a ogni lettura:** ogni frase di Oggi e della pagina del ticker ha un'etichetta con l'esito del suo test, presa dai file congelati (`bzd/verdicts.py`). Quelle mai testate da sole dicono «non testato».
- **Reset:** testato solo sul giornaliero; su settimanale e mensile app e alert dicono «non testato».
- **Test:** tutte le ipotesi in un'unica tabella (setup degli alert B3, v2–v5 e ciò che non è testato), con filtri per esito e per test; un clic apre la scheda o il resoconto. Sotto, le strategie sulle opzioni in prova. Le altre schede rimandano qui.
- **Bots:** il bot Deribit con stato, posizioni, delta, margine ed eventi, e i comandi pausa, riprendi, dimensione (solo più bassa) e chiusura d'emergenza (`bzd/bots.py`). L'app scrive solo il file di comandi, il bot lo legge ogni 10 secondi.
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
- **Vendere volatilità, storico su prezzi veri (24 novembre, `docs/BOT_DERIBIT_STORICO.md`):** su Deribit dal 2019 nessuno spread a rischio definito guadagna al netto dei costi; il put spread del bot fa −1% sul rischio su BTC e −2,3% su ETH. Solo la put nuda o molto lontana su BTC è positiva, poco e non significativa. Iron condor e garanzia in moneta peggio. Sull'S&P l'iron condor Cboe fa 0,8% l'anno dal 2007. Seconda prova: l'unica candidata è lo strangle 25Δ su BTC venduto da maker e coperto ogni giorno sul perpetuo (+7,3% l'anno, DD −12%, t 1,9 con il funding), ora in prova sui dati futuri nel bot (giudizio non prima del 24 novembre 2027). Nessun filtro (premio, contango, regime calmo) la migliora. Rifatta ora per ora, la copertura d'emergenza fuori orario la peggiorava (media +0,64% invece di +0,81%, peggiore −15% invece di −11%): tolta dal bot prima della prima entrata.
- **Raddoppi tutto o niente (`docs/RADDOPPI.md`):** sul perpetuo BTC dal 2019 un lancio a 10–20× si vince 47–49 volte su 100 (con i costi di Hyperliquid 43–47), quindi 11 raddoppi di fila riescono circa 1 volta su 2.500–11.000. Il segnale di momentum aggiunge 3–5 punti, non dimostrati. Incassare per strada non alza il valore medio. Nessun bot.
- **Premio sulla volatilità (esplorazione, non test):** dal 2021 l'implicita a 30 giorni ha superato la realizzata nel 72% dei giorni su BTC (+10 punti di mediana), 65% su ETH (+7,6) e 85% sull'S&P (+4,4). Per unità di rischio, venditore di varianza al lordo dei costi: S&P 0,38, BTC 0,26, ETH 0,00.
- **Chi compra:** il retail cripto va contro il prezzo (−0,54 su BTC a 3 giorni), i top trader no. Seguire chi compra il dip non ha aiutato (F1, F2).
- **Segno COT su USD/JPY, USD/CHF e USD/CAD:** i setup congelati lo leggono al contrario. L'esito di B3 non cambia; le conferme dal vivo su quelle coppie sì.
- **Limiti delle fonti:** Google Trends solo dal feed pubblico; nessuno storico FXE ed EVZ fermo a marzo 2025; il sentiment è un conteggio di parole non validato, e Cina, Yuan e metalli rari hanno pochi testi.

## Decisioni dell'utente

- Solo fonti gratuite e leggibili, niente API di X.
- Niente chiamate a pagamento agli agenti senza chiedere.
- Alert su Telegram: brevi, dicono cosa è successo. Direzione («potenziale long») ed esito del test solo dove il test ha retto; i test non superati, le conferme mancanti e le regole mai testate restano nell'app (24 novembre). Entry, stop e target solo nell'app. Il 4h solo nell'app.
- Paura rossa, euforia verde. App per PC, non per telefono, e fuori da AMBRA.
- Le operazioni reali dell'utente (A2) più avanti: non proporle prima che ne riparli.
- Gli agenti possono citare e dare un parere, non cambiare numeri o bloccare un alert.
- L'indirizzo Hyperliquid dell'utente non va chiesto.
- Bot che vende volatilità su Deribit: dal 24 novembre solo la strategia che ha retto nello storico (strangle BTC coperto, da maker), le altre tolte su richiesta dell'utente. Prima sul testnet. Il conto vero solo con una decisione esplicita dell'utente, con la cifra, e dopo il server. Il direzionale con approvazione resta fuori finché un segnale non regge un test.
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
- Segno COT dal vivo su USD/JPY, USD/CHF e USD/CAD: correggerlo ora o nella prossima versione dei setup? Intanto l'alert lo segnala.
- Prezzi di bond non USA, per la forza e la tecnica?
