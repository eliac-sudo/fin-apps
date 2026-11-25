# Stato del progetto

Aggiornato al 24 novembre 2026. Da leggere per primo quando si riprende il lavoro. Branch `roadmap-v0.3`, unito in `main` il 24 novembre 2026 (pull request 2). La cronaca delle modifiche sta in `docs/wiki/log.md` e nella storia git; qui c'è solo com'è adesso.

## Cos'è

BZD raccoglie dati gratuiti su cripto, azioni, bond, materie prime e forex. Li mostra in un'app per PC e manda alert su Telegram. Serve soprattutto a chi compra bene i minimi ma fatica a vendere i massimi. Gli ordini li manda solo il bot Deribit, per ora sul testnet con soldi finti: vende lo strangle BTC da maker e lo copre sul perpetuo (`docs/BOT_DERIBIT.md`).

## Cosa gira

**Dal 24 novembre 2026 alle 16:39 UTC tutti i servizi girano sul server Hetzner** (`bzd-server`, `docs/SERVER.md`) come servizi systemd con utente `bzd` in `/opt/bzd`. Ripartono da soli se cadono o se il server si riavvia. **Dal 24 novembre 2026 si sviluppa sul server**, utente `dev` in `/home/dev/fin-apps` (`ssh dev@bzd` via Tailscale, poi `tmux new -A -s claude` e `claude`; `docs/SERVER.md`), perché le ore gratuite di Codespace sono finite; da lì il codice va ai servizi con `bash scripts/server-update.sh local`. Il Codespace, se lo si riaccende, serve solo per lo sviluppo: con `.sul-server` presente non accende niente e apre solo il tunnel per l'app sulla porta 8787. **L'app da PC e telefono:** `https://bzd.tail5e1e60.ts.net`, solo dentro la rete Tailscale dell'utente; ad altri si dà accesso condividendo il nodo `bzd`. Il codice si aggiorna con `bash scripts/server-update.sh bzd-server`, che Claude lancia senza chiedere. Lo stato si controlla con `ssh bzd-server 'systemctl is-active bzd-recorder bzd-wallets bzd-copia bzd-alerts bzd-vol-bot bzd-app'`; i log sono in `/opt/bzd/data/*.log`. L'agente di ricerca gira il 1° di ogni mese alle 05:00 UTC (`bzd-research.timer`, log in `data/research.log`): cerca lavori nuovi, legge gli abstract, chiama il supervisore se è il momento. Il backup gira ogni notte alle 03:30 UTC in `/home/bzd/bzd-backups`, sullo stesso disco: una copia fuori dal server manca ancora. Dopo una riaccensione del Codespace, `su codespace -c 'bash scripts/ensure-services.sh'` riapre solo il tunnel. Nella tabella sotto ci sono i comandi che i servizi eseguono. **Buco nei dati dal 7 al 23 novembre 2026:** i servizi si sono fermati il 7 verso le 14 e nessuno li ha riaccesi per 16 giorni. Quello che si scarica di nuovo (prezzi giornalieri, COT) si recupera; le fotografie dal vivo (opzioni in prova, posizioni Hyperliquid, Telegram) no. Il 23 novembre i servizi erano di nuovo fermi da circa 4 ore, riaccesi alle 16 UTC circa.

| Servizio | Comando | Note |
|---|---|---|
| Recorder | `python3 -u -m bzd.recorder run` | 218 lavori di raccolta (dal 24 novembre anche 58 serie FRED e le previsioni) |
| Storico Telegram | `python3 -u -m bzd.telegram backfill` | canali pubblici |
| Alert e bot | `.venv/bin/python -u -m bzd.alerts run` | invio attivo, risponde a `/piano` |
| Portafogli HL | `python3 -u -m bzd.wallets run` | classifica ogni giorno, posizioni ogni ora |
| Copia sulla carta (v9) | `python3 -u -m bzd.copia run` | ogni 5 minuti, due portafogli finti |
| App | `.venv/bin/python -u -m bzd.app` | porta 8787, privata |
| Bot Deribit | `.venv/bin/python -u -m bzd.vol_bot run` | parte solo con `DERIBIT_CLIENT_ID` in `.env`; testnet. Dal 24 novembre 2026 solo lo strangle coperto (v2); la prima versione a put spread è chiusa e archiviata in `data/vol_bot_v1_archivio/` |

- Nel Codespace, prima del server, i servizi giravano come utente `codespace` e Claude come root. Dopo ogni modifica da root: `chown -R codespace:codespace /workspaces/fin-apps` e `chmod 600 .env`. Per riavviare un servizio si cerca il PID con `pgrep -f` su un'espressione ancorata, non con `pkill -f` largo. Lo script avvia anche l'app: prima va fermata un'eventuale copia lanciata da root.
- Revisione degli alert con l'LLM **accesa** (`BZD_AGENTS=on`), tetto 3 $ al mese dal 24 novembre (`BZD_LLM_BUDGET_USD`; la ricerca si ferma 0,50 $ prima), condiviso con gli agenti di ricerca. Spesa totale 0,36 $ al 5 novembre. Il 23 novembre la chiave API Anthropic era scaduta: le revisioni fallivano e gli alert partivano senza. Sostituita lo stesso giorno; il 24 novembre risponde. Se torna «chiave API non valida» in `data/agents/reviews.jsonl`, va rinnovata in `.env`.
- Il push su GitHub usa il token copiato con `gl` da un terminale di VS Code: quando scade, il push fallisce finché l'utente non rilancia `gl`.

## L'app, scheda per scheda

Dal 25 novembre 2026 la barra delle schede mostra solo quelle di ogni giorno (Oggi, Analisi tecnica, Opzioni, Sentiment, Chi compra, Previsioni, Alert), poi il menu «Altro ▾» con Test, AIsetups, Piano, Bots e Motore (quando se ne apre una, il menu prende il suo nome). Anche i pulsanti che aprono il Piano da Alert e Analisi tecnica sono discreti.

Il codice sta in `bzd/app.py` (server), `bzd/app.html` (pagina) e `bzd/snapshot.py` (i dati). Il tasto Layout ha 4 stili. I dati si ricostruiscono in circa 30 secondi all'avvio, poi restano in cache.

- **Oggi:** la frase del giorno, la **forza** per gruppo (0–100 rispetto alla propria storia: ipervenduto, sotto la norma, nella norma, sopra la norma, ipercomprato; `bzd/thermo.py`) e la tabella del momentum («▼ scende forte» e «▲ sale forte» sotto −50 e sopra +50; `bzd/zones.py`). Poi la **liquidità** (`bzd/liquidity.py`, `docs/wiki/liquidita.md`): Fed netta, M2, stablecoin, condizioni finanziarie, spread high yield e dollaro rispetto a 13 settimane prima, e per ogni mercato volumi, impatto e book di Hyperliquid; non testata. Poi il riquadro **BZD, la capitolazione** (prima BYZ) (`bzd/capitulation.py`): scatta solo con un asset forte, un calo profondo, la volatilità spenta e il prezzo di lato da 40 sedute. È una regola nuova e non testata, e oggi non scatta su nessun mercato.
- **Pagina del ticker:** si apre cliccando un asset ovunque o dalla ricerca. Riassume Oggi, Analisi tecnica, Opzioni, Sentiment e Chi compra, con un pulsante per ogni scheda.
- **Opzioni:** costo rispetto al movimento previsto (Black-76, SVI, HAR), contratti economici e cari, gamma (`bzd/option_lab.py`, `docs/OPZIONI_MODELLI.md`).
- **Analisi tecnica:** grafico con livelli disegnati dal codice, RSI, indicatori a confronto, e la ricerca di qualunque perpetuo Hyperliquid o ticker Yahoo (`bzd/technicals.py`, `bzd/lookup.py`).
- **Sentiment:** paura ed euforia per argomento nelle ultime 24 ore e nei 7 giorni, gli estremi sul grafico del prezzo, le 100 etichette B4 da assegnare (`bzd/sentiment.py`, `bzd/labels.py`).
- **Chi compra:** retail e grossi come percentile sui loro ultimi 3 anni, e i portafogli Hyperliquid profittevoli (`bzd/flows.py`, `bzd/wallets.py`, `docs/CHI_COMPRA.md`).
- **Alert e Piano:** gli alert di Telegram con i livelli, e il calcolo di dimensione, stop e obiettivo (`bzd/alerts.py`, `bzd/plan.py`).
- **Esito accanto a ogni lettura:** ogni frase di Oggi e della pagina del ticker ha un'etichetta con l'esito del suo test, presa dai file congelati (`bzd/verdicts.py`). Quelle mai testate da sole dicono «non testato».
- **Reset:** testato solo sul giornaliero; su settimanale e mensile app e alert dicono «non testato».
- **Previsioni:** cosa si aspettano la Fed (proiezioni del FOMC, GDPNow), i previsori professionali USA e dell'area euro, l'OCSE, Kalshi e Polymarket, con la differenza dall'edizione prima (`bzd/forecasts.py`, `docs/wiki/previsioni.md`). Nessuna è testata come segnale.
- **Test:** tutte le ipotesi in un'unica tabella (setup degli alert B3, v2–v5 e ciò che non è testato), con filtri per esito e per test; un clic apre la scheda o il resoconto. Sotto, le strategie sulle opzioni in prova. Le altre schede rimandano qui.
- **Bots:** il bot Deribit con stato, posizioni, delta, margine ed eventi, e i comandi pausa, riprendi, dimensione (solo più bassa) e chiusura d'emergenza (`bzd/bots.py`). L'app scrive solo il file di comandi, il bot lo legge ogni 10 secondi.
- **AIsetups:** due volte al giorno (06:30 e 13:30 UTC) Haiku legge ciò che mostra l'app e scrive 15 candidati; il codice scarta quelli che non passano i controlli, dà un punteggio agli altri (convinzione, guadagno/rischio, test) e tiene una bacheca di 5 idee (2 breve, 2 medio, 1 lungo), cambiandole solo quando si chiudono, quando il modello le dice superate o quando arriva un candidato con almeno 2 punti in più. Telegram riceve il messaggio solo se la bacheca cambia (`bzd/aisetups.py`, circa 0,01 $ a giro). Sono idee senza vantaggio dimostrato: la tabella «Come sono andate» dirà se valgono qualcosa.
- **Motore:** il wiki del programma in `docs/wiki/`, una pagina per parte. `python -m bzd.wiki lint` controlla che ogni citazione porti a un file vero e che ogni modulo abbia una pagina; lo verifica anche un test.

**Dati macro e previsioni (24 novembre):** 58 serie FRED in `data/hist/macro`, aggiornate ogni giorno con le revisioni (`docs/wiki/macro.md`). In `data/hist/forecasts` le previsioni con la data in cui sono uscite: proiezioni del FOMC dal 2015, previsori professionali della Fed di Filadelfia dal 1968 e della BCE dal 1999, Economic Outlook dell'OCSE. Il recorder salva anche le probabilità di Kalshi e Polymarket ogni 6 ore e i discorsi di Fed, BoE, BoJ e BIS (`docs/wiki/previsioni.md`). Il FMI blocca il server. Nessuna previsione è testata come segnale.

Fuori dall'app: catalogo di 334 lavori (`docs/CATALOGO.md`), note degli agenti di ricerca (`docs/letteratura/`), backup e kit per il server mai provato su un server vero (`docs/SERVER.md`), vecchi progetti in `docs/archivio/`.

## Cosa sappiamo

Il dettaglio di ogni test è nella scheda Test e nei file `docs/V*_STORICO.md`. Ogni test è stato pre-registrato ed eseguito una volta sola.

- **B3, i setup degli alert:** su 15 passa solo il panico cripto (+0,75%), di poco e non alla soglia più severa.
- **v2, trend lungo:** l'incrocio della media a 200 sedute non dà vantaggio (+0,08%, t = 0,26). La prova sui dati futuri è stata chiusa il 25 novembre 2026 senza calcolare alcun rendimento: servivano anni per un'idea già piatta sullo storico.
- **v3, le 15 letture dell'app:** regge solo O2: con opzioni «economiche» comprare uno straddle rende 22 punti di premio più del solito, ma il netto resta −1%. Le altre 14 non reggono.
- **v4, momentum su 50 mercati nuovi:** dopo «scende forte» e «sale forte» il prezzo continua per 10 sedute, circa +0,6% rispetto al caso, ma tolti i costi lo short perde e il long è in pari. Regge anche «sale forte da 3 sedute».
- **v5, BYZ e SZT letti come il nome:** nessuna ipotesi regge su 99 azioni USA nuove. Per questo BYZ non è più un nome del momentum.
- **v6, liquidità e proiezioni della Fed (24 novembre, `docs/V6_STORICO.md`):** nessuna delle 5 regge. Liquidità della Fed in forte aumento: no (p 0,20). Dollaro in forte rialzo (short) e impatto alto (long) vanno vicini ma non passano Holm (p 0,015 e 0,012). Stablecoin e Fed più dura: troppi pochi casi. Le vicine si provano solo sui dati futuri.
- **v7, tutte le coppie di letture (24 novembre, `docs/V7_ESAME.md`):** 484 regole cercate sul 2008–2018, controllate sul 2019–2022, esaminate una volta sul 2023–2026. Nessuna regge. Le 4 arrivate all'esame comprano tutte il prezzo basso nell'anno; «posizione bassa → long» è positiva in tutti e tre i periodi (p 0,025 all'esame, soglia 0,017): è la candidata per la prova sui dati futuri.
- **v8 (24 novembre, `docs/V8_STORICO.md`):** due idee degli agenti dalla psicologia dei mercati, sul Fear & Greed cripto. Dopo la paura estrema le cripto si muovono meno, non di più (non supportata); dopo l'euforia estrema lo short perde, ma con 21 cluster non è informativa. **Prova sui dati futuri** dal 25 novembre 2026 di posizione bassa (v7), dollaro forte e impatto alto (v6), paura ed euforia: contata ogni giorno dal servizio degli alert, risultati in `data/v8`. Emendamento del 25 novembre 2026, con 0 eventi: dollaro forte, paura ed euforia chiuse senza guardare (troppo rare per arrivare a un giudizio); posizione bassa e impatto alto si guardano a 20, 40 e 60 cluster o il 24 novembre 2028, con soglie di O'Brien-Fleming (`config/setups_v8_sequenziale.json`).
- **Mercati osservati (25 novembre):** credito con 10 ETF (HYG, LQD, BKLN, ANGL, CWB, PFF, EMB, MUB, IHYG, IEAC), Euro Stoxx 50, DAX, FTSE MIB, Nikkei, emergenti, Cina e Bund lunghi (`bzd/history.py#WATCH`), con prezzi, tensione, tecnica e posizione nell'app, ma fuori da setup, alert, termometro su Telegram e test congelati. Nella liquidità: spread Baa di Moody's (FRED, dal 1986), credito HYG/IEF, spread BTP–Bund (BCE, mensile) e Bund 10 anni (Bundesbank, giornaliero).
- **v9, copiare i trader di Hyperliquid (25 novembre, `docs/V9_STORICO.md`):** la classifica ha memoria su 19 giorni. Dei 50 migliori del mese al 6 novembre l'86% era ancora in utile il 25, contro il 27% degli altri, e le tre ipotesi reggono anche mettendo ultimi i 919 conti usciti dalla classifica. Ma è un solo momento di mercato, in calo. **Copia sulla carta** dal 26 novembre 2026, servizio `bzd-copia` (`python -m bzd.copia stato`, log in `data/copia.log`): C copia i 20 migliori, R 20 a caso, ogni 5 minuti con i costi; nessuna chiave, nessun ordine. Sguardi a 60 e 120 giorni con soglie O'Brien-Fleming (emendamento del 25 novembre, `config/setups_v9_sequenziale.json`), giudizio al più tardi il 25 maggio 2027 (`data/v9`). Del bot vero si parla solo se regge, e con una decisione dell'utente sulla cifra.
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
- Il bot Deribit non scrive su Telegram (24 novembre, `BZD_BOT_TELEGRAM=off`): stato ed eventi solo nella scheda Bots.

## Prossimi passi

La roadmap completa, in ordine di urgenza, è in `docs/ROADMAP.md` (24 novembre). Deciso il 5 novembre: **prima l'app, gli alert e le indicazioni devono avere senso, poi il server.**

1. **App e alert:** che ogni indicazione sia chiara e coerente con i test.
2. **Agenti di ricerca:** il supervisore (Opus) ricontrolla le note del lettore (Haiku) e scrive bozze solo da quelle che reggono, una volta al mese o ogni 10 note nuove (`python -m bzd.research stima`). Un'idea resta «non testata» finché non passa una pre-registrazione su dati nuovi.
3. **Backup fuori dal server:** il server c'è dal 24 novembre; manca la copia fuori. `data/` e `.env` non sono su GitHub.

## Domande aperte

- Avvio automatico anche da `~/.bashrc` o `postAttachCommand`, visto che il `postStartCommand` a volte non parte?
- BZD capitolazione: pre-registrarla per una prova sui dati futuri? È rara, quindi servirebbero anni.
- Momentum anche sul bot? Consiglio: prima la prova sui dati futuri.
- Segno COT dal vivo su USD/JPY, USD/CHF e USD/CAD: correggerlo ora o nella prossima versione dei setup? Intanto l'alert lo segnala.
- Prezzi di bond non USA, per la forza e la tecnica?
