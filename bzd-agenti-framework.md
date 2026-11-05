# BZD — framework degli agenti (scheda v0.3, 4/11/2026)

Stato: **solo progetto**, nessun codice. Fonti verificate il 4/11/2026 (elenco in fondo). Potenze calcolate in codice
(`bzd-potenza.py`, seed 42/43). Metodo come DRUCK/TERMINAL e AMBRA: verifica → ipotesi pre-registrate → potenza → limiti.
Regola dei tre esiti (supportata / non supportata solo se potenza ≥ 50% / non informativa).

**Cambi rispetto alla v0.1 (indicazioni dell'utente, 4/11):** (1) obiettivo = **più confidenza sugli ingressi** per operazioni
brevi, soprattutto in **panico** e **short squeeze**, non solo l'uscita; (2) sentiment da **notizie + risposte sotto i post
di grandi account X** (10 account × 4 aree × 30 risposte); Fear & Greed solo come una componente tra le altre;
(3) l'app è **supervisionata**, con una parte manuale e una automatica.

**Cambi rispetto alla v0.2 (indicazioni dell'utente, 4/11):** (1) **prima le uscite**, con i segnali in parallelo (`ROADMAP.md`);
(2) **niente API di X**: solo fonti social e notizie leggibili gratis; (3) calibrazione su **più exchange**; (4) AMBRA, DRUCK e quant_crew
si reimplementano dopo: i riferimenti qui sotto sono solo storici; (5) **tutti i mercati** (cripto, azioni, materie prime, forex, obbligazioni) e **segnali dalle opzioni**, con dati raccolti su tutti. Dove questa scheda e `ROADMAP.md` divergono, vale `ROADMAP.md`.

## 0. Conclusione

1. **Output centrale: la «scheda setup».** Quando scatta un setup (panico o squeeze) l'app mostra: quante condizioni sono
   soddisfatte (checklist pre-registrata), e **cosa è successo nei casi simili del passato** (n casi, quota in rialzo a 4/24/72 h
   con IC 95%, mediana, caso peggiore), più notizie e testi social citati. È la forma onesta di «confidenza»: una frequenza
   storica con la sua incertezza, non una probabilità inventata.
2. **L'evidenza sui due setup è mista.** Dopo giorni di «iper-reazione» in cripto il giorno dopo si muove di più in entrambe le
   direzioni, ma comprare il rimbalzo non è risultato profittevole e seguire l'inerzia non batte il caso (Caporale-Plastun, JES 2019).
   Il momentum giornaliero è forte (Liu-Tsyvinski, RFS 2021): nel brevissimo il panico tende a proseguire, non a rimbalzare.
   Sui regimi di funding negativo (squeeze) i dati favorevoli sono di un broker (K33), su orizzonti 30–360 giorni e pochi regimi.
3. **Potenza.** Conteggio reale (`python -m bzd.setups events`, nessun rendimento futuro calcolato): panico cripto con almeno 1 condizione oltre al prezzo = **188 cluster indipendenti**;
   con tutte le condizioni quasi nessun caso, in ogni mercato: la checklist completa non è utilizzabile come filtro. Con 79 cluster di test la potenza è ~59% a d = 0,30:
   gli effetti piccoli resteranno probabilmente «non informativi». Dettagli in `ROADMAP.md`.
4. **Niente X.** Sentiment solo da fonti gratuite: Reddit (con storia via Arctic Shift, quindi valutabile nei backtest), notizie, Bluesky, Telegram pubblico e altre.
   Le fonti senza storia si registrano da subito e si valutano solo in avanti.
5. **Automatico solo dopo i test**, su testnet, con un «API wallet» di Hyperliquid che può tradare ma non prelevare,
   e limiti rigidi (rischio per trade, perdita giornaliera, leva, interruttore). La parte manuale parte subito.

## 1. Come l'hanno fatto altri (verificato, invariato dalla v0.1)

| Progetto | Architettura | Cosa prendiamo / cosa no |
|---|---|---|
| **TradingAgents** (arXiv 2412.20138) | analisti per fonte → dibattito bull/bear → trader → team rischio | Separazione per fonte e dibattito pro/contro nella scheda setup. Non i risultati (look-ahead nei pesi degli LLM) |
| **ai-hedge-fund** (virattt) | agenti «alla investitore famoso» + tecnico, sentiment, risk manager; solo simulazione | Risk manager separato |
| **Alpha Arena S1** (nof1, ott-nov 2025, Hyperliquid, denaro reale) | LLM che tradano da soli | 4 su 6 in perdita: l'LLM non decide e non calcola |
| quant_crew (nostro) | CrewAI, tool deterministici | Tool che leggono da cache, guardrail sul report |

## 2. Framework

### 2.1 Psicologia e microstruttura dei due setup
| Setup | Meccanismo | Evidenza | Implicazione |
|---|---|---|---|
| **Panico / capitolazione** | vendite forzate (liquidazioni dei long) spingono il prezzo oltre il valore → rimbalzo quando finiscono (ipotesi di iper-reazione, De Bondt-Thaler) | cripto: movimenti successivi più ampi in entrambe le direzioni; strategia contraria **non profittevole** al netto, inerzia non diversa dal caso (Caporale-Plastun 2019). Momentum giornaliero forte (Liu-Tsyvinski) | Non «compra ogni crollo»: servono segni che la vendita forzata è **finita** (OI crollato, funding tornato neutro/negativo, volume in calo dopo il picco) |
| **Short squeeze** | short affollati (funding negativo persistente, OI in salita) + prezzo che sale → coperture forzate | K33 (broker, non peer-reviewed): acquisti in regimi di funding medio 30 g negativo, win rate 83–96% vs 55–70% casuale su 30–360 g, dal 2018. Controesempio citato: maggio 2022, setup simile seguito da un calo a doppia cifra | Pochi regimi indipendenti; orizzonti lunghi ≠ trade brevi. Va testato su 4–72 h |
| Sentiment estremo | paura/euforia della folla vs addetti | letteratura divisa (v. 2.2) | componente della checklist, non segnale a sé |
| Pre-impegno | decidere stop e obiettivo prima di entrare | Kaminski-Lo 2014: gli stop aiutano con momentum/regimi, peggiorano con passeggiata casuale | ogni setup nasce con stop e obiettivo: serve ai trade brevi ed è l'antidoto al greed |

### 2.2 Sentiment (Fear & Greed solo come una componente)
- **Notizie**: GDELT (volume e tono, gratuito, finestra 3 mesi) + RSS Fed/BCE + Google News `site:reuters.com` (non ufficiale).
- **Pannello social** (gratuito, senza API di X): Reddit, Bluesky (thread con risposte), canali Telegram pubblici, 4chan /biz/. Le fonti testate sono in `ROADMAP.md`.
  Misure: quota di testi impauriti/euforici, **divergenza tra il tono dell'autore e quello delle risposte** (esperto vs folla) dove esistono thread,
  numero di risposte (attenzione), visite Wikipedia come misura di attenzione.
- **Fear & Greed** (alternative.me): una componente; metà del suo peso è già prezzo/volatilità.
- Evidenza: Fear & Greed predice in Granger (Cavalheiro et al. 2024); Twitter predittivo per alcune cripto (Kraaijeveld-De Smedt 2020,
  con molti bot); nessuna causalità da Twitter/Reddit (Ciganovic 2023). Alta attenzione → rendimenti più alti a 1 settimana
  (Liu-Tsyvinski): l'euforia può essere momentum.

### 2.3 Derivati
Funding, OI, basis (He-Manela-Ross-von Wachter: deviazioni perp-spot in cripto molto più ampie che nelle valute);
opzioni BTC/ETH da Deribit (IV ATM, skew 25-delta, put/call, GEX con **due convenzioni di segno**, perché il segno dei dealer è un'ipotesi).

## 3. Architettura

```
 [1 Mercato]  codice ─┐
 [3 Testi]    codice ─┼─► archivio + tabella EVIDENZE (fonte, URL, ora, hash della risposta grezza)
                      │
 [2 Calcolo]  codice ─┤   indicatori → rilevatore setup → checklist → casi simili del passato
 [4 Sentiment] LLM + baseline ─┤   etichette con frase citata
                      ▼
 [5 Supervisore] regole in codice + LLM che scrive ─► SCHEDA SETUP ─► app (manuale | automatico)
```
Nessun framework agentico in v0 (pipeline Python + chiamate all'API Anthropic); CrewAI riusabile da quant_crew se servisse.
Ogni numero nella scheda ha un `id` di evidenza verificabile con `bzd verifica <id>`.

## 4. Gli agenti

### Agente 1 — Mercato (codice)
| Fonte | Dati | Accesso |
|---|---|---|
| Hyperliquid `POST /info` | candele, funding storico, OI e mark, libro L2, i tuoi `userFills` | pubblico; 1200 di peso/min per IP |
| Deribit `public/*` | catena opzioni BTC/ETH | pubblico senza chiave |
| alternative.me `/fng/` | Fear & Greed dal 2018 | gratuito con attribuzione |
| Coin Metrics Community, DefiLlama | on-chain, stablecoin | come AMBRA P1c |
| Storia lunga | candele, funding, OI | **Binance e Bybit, gratuiti** (candele e funding dal 2019-09, OI dal 2020-07): testati il 4/11 |
| Liquidazioni | segnale chiave del panico | **canali Telegram pubblici con storia** (Binance dal 2019-05, Hyperliquid dal 2024-12; bot di terzi con soglie minime: da validare); proxy: calo di OI + volume + prezzo; OKX registrato in avanti |

### Agente 2 — Calcolo e rilevatore setup (codice)
Indicatori (barre 1 h e 4 h, più giornaliere): rendimento in unità di volatilità (z), volume z, ΔOI 1/4/24 h, funding e suo z-score,
basis, RSI 14, distanza da VWAP e medie 50/200, ATR; IV ATM e suo salto, skew 25-delta; tono GDELT e suo salto; indici social.

**Setup (soglie da fissare fino a fine 2023 per le cripto e fino a fine 2014 per gli altri mercati, poi congelate). Aggiungere il setup SURRISCALDAMENTO (ridurre o stringere gli stop, non short):**

| Condizione | PANICO (long sul rimbalzo) | SQUEEZE (long sulla copertura degli short) |
|---|---|---|
| Prezzo | rendimento 4 h ≤ −3 z | rendimento 4 h ≥ +2 z dopo consolidamento |
| Leva | ΔOI 24 h ≤ 10° percentile (leva ripulita) | funding medio 7 g < 0 e OI 7 g in salita |
| Funding | tornato ≤ 0 | negativo da ≥ 3 giorni |
| Volume | picco z ≥ 3 nella barra, in calo nella successiva | in salita |
| Opzioni | IV ATM nel 90° percentile; skew put estremo | skew che si normalizza |
| Sentiment | quota di paura nei testi social / tono GDELT nel 10° percentile | sentiment ancora negativo (incredulità) |
| Contesto | nessun shock macro in corso (notizie Fed/BCE) | idem |

Punteggio storico = condizioni con storia oltre al prezzo (leva, funding, volume: 0–3), pesi uguali (Occam); opzioni, sentiment e contesto restano separati finché non hanno storia comparabile. **Casi simili** = eventi passati con punteggio ≥ quello attuale
e stesso setup → tabella con n, quota in rialzo a 4/24/72 h (IC di Wilson), mediana, 10° percentile, drawdown massimo intermedio,
tutto **al netto di commissioni e funding** (commissioni Hyperliquid da verificare in P0).

Quanto è larga la «confidenza» (quota osservata 60%, IC 95% di Wilson):

| casi simili | 10 | 20 | 40 | 80 | 160 |
|---|---|---|---|---|---|
| IC 95% | 31–83% | 39–78% | 45–74% | 49–70% | 52–67% |

Questi intervalli contano casi indipendenti: nella scheda vanno calcolati sui **cluster**, non sui casi grezzi (40 casi al 60% con n efficace 16,7 danno ~37–79%). Con pochi cluster l'intervallo comprende quasi sempre il 50%: la scheda lo deve dire esplicitamente.

### Agente 3 — Testi (codice)
| Fonte | Note verificate |
|---|---|
| GDELT DOC 2.0 | gratuito, senza chiave, 3 mesi, tono; ~1 richiesta ogni 5 s |
| RSS Fed e BCE | già in DRUCK |
| Reuters | nessun RSS ufficiale dal 2020; ripiego Google News (non ufficiale) |
| **Social gratuiti** | Reddit RSS e Arctic Shift, Bluesky, Telegram `t.me/s/`, 4chan, Mastodon, Lemmy, Hacker News, YouTube RSS; X escluso |

Costo delle fonti: 0 $. Costo reale: limiti di frequenza e copertura cripto da misurare, fonti di terzi che possono sparire; si archivia la risposta grezza.

**Lista degli account/canali**: la scegli tu, con criteri scritti prima (attivi, seguiti, mix di posizioni, niente account a pagamento noti);
congelata e versionata, ogni cambio registrato. Filtri: account nuovi o con pochi follower marcati come possibili bot.

### Agente 4 — Sentiment (LLM + baseline)
Per ogni testo: `{rialzista, ribassista, neutro, irrilevante}` + paura/euforia (−2…+2) + frase citata + URL.
Validazione su 100 testi etichettati da te (kappa di Cohen ≥ 0,6, altrimenti fuori dal punteggio). Baseline senza LLM: tono GDELT,
Fear & Greed. Nei backtest solo fonti con storia e baseline (gli LLM hanno visto il passato); le etichette LLM storiche su Reddit vanno trattate con cautela.

### Agente 5 — Supervisore e scheda setup
Regole in codice: freschezza per fonte, coerenza (es. prezzo in panico ma funding molto positivo → leva non ripulita → avviso), ogni numero con `id`.
L'LLM scrive: cosa sta succedendo, caso pro e caso contro, cosa dicono notizie e social (con citazioni), casi simili, stop e obiettivo proposti
(da regole in codice: es. stop sotto il minimo del panico − 0,5 ATR, obiettivo a k·ATR), cosa non sappiamo.

## 5. Ipotesi pre-registrate
Famiglia dei setup: 2 setup × 3 orizzonti = 6 test, α = 0,05/6 ≈ 0,0083 unilaterale.

| ID | Ipotesi | Test | Potenza (calcolata) | Atteso |
|---|---|---|---|---|
| **P1** | Dopo un PANICO con punteggio ≥ s* il rendimento netto a 4/24/72 h **batte entrate casuali sullo stesso asset**; risultati anche con stop e obiettivo, in R | event study, errori per cluster di eventi | v. conclusione 3 (per cluster) | non informativo se l'effetto è piccolo |
| **Q1** | Idem per SQUEEZE | idem | idem | idem |
| **P2/Q2** | Punteggio più alto → rendimento più alto (monotonia) | Spearman / Jonckheere-Terpstra | da simulare con gli n reali | — |
| **U0** | Le tue entrate sui dip battono entrate casuali negli stessi giorni | bootstrap sui tuoi `userFills` (eseguito in locale) | dipende dal n. di trade | — |
| **H3** | Una regola d'uscita pre-registrata batte le tue uscite reali e il mantenimento fino a orizzonte fisso | replay delle regole | dipende dal n. di trade | — |
| **U1** | Le tue entrate **con** la scheda battono le tue entrate senza (in avanti) | confronto prima/dopo, stesse regole di rischio | bassa all'inizio | descrittivo per mesi |
| **H1/H2** (v0.1) | Termometro → rendimento 30 g / calo ≥ 20% | regressione, Fisher | 20% (R² 2%); 35% (15→45%) | non informativo |

Ipotesi sui parametri della potenza: 3 asset per evento, correlazione 0,7 tra asset nello stesso evento (n efficace = n/2,4); rendimenti normali iid
(ottimistico: code spesse e cluster riducono la potenza reale).

## 6. App supervisionata (manuale + automatico)
| | Manuale (da subito) | Automatico (solo dopo) |
|---|---|---|
| Cosa fa | mostra la scheda setup, prepara l'ordine con dimensione da rischio fisso, stop e obiettivo; **tu** confermi | esegue da solo **solo** i setup con esito «supportata» |
| Dove | lettura dati mainnet, nessuna chiave in v0 | prima **testnet** Hyperliquid, poi mainnet con importi piccoli |
| Chiavi | — | **API wallet** (agent wallet): firma ordini ma **non può prelevare**; revocabile; con scadenza |
| Limiti rigidi | consigliati | obbligatori: rischio per trade (es. 0,5% del conto), perdita massima giornaliera, leva massima, n. massimo di trade/giorno, interruttore; tutto in codice, non nel prompt |
| Registro | ogni scheda e ogni tua decisione (anche «non entro») | ogni ordine con l'`id` della scheda che l'ha generato |
Il registro serve a U1: misurare se lo strumento migliora davvero le tue decisioni.

## 7. Come farli girare (v0)
1. VM Ubuntu (Multipass) come AMBRA e DRUCK; sviluppo con Claude Code da questa scheda.
2. `.env`: `ANTHROPIC_API_KEY`, `FRED_API_KEY` (già presente), indirizzo Hyperliquid (solo in locale).
3. Comandi: `bzd storico` (storia + fixture reali), `bzd raccogli`, `bzd calcola`, `bzd sentiment`, `bzd scheda`, `bzd tutto --ogni 15m`
   (il pannello social gira a intervalli entro i limiti di ciascuna fonte), `bzd verifica <id>`.
4. Costi: dati gratuiti; LLM da misurare al primo collaudo.

## 8. Limiti e ipotesi fragili
- Storia: Hyperliquid limitata (candele 1 h dal 2026-04-10, 4 h dal 2024-07-24 via API); calibrare su altri exchange introduce differenze di basis e liquidità.
- Liquidazioni solo da bot di terzi con soglie minime: i totali sono un minimo, da validare.
- Pannello social: selezione arbitraria, bot, chi scrive non è chi trada; la copertura cripto fuori da Reddit è da misurare; le fonti gratuite possono cambiare.
- Soglie dei setup: scelte da me come punto di partenza, da congelare prima di guardare il campione di test.
- K33 è ricerca di un broker con interesse commerciale; gli studi sul sentiment non concordano.
- Operazioni brevi con leva: costi (commissioni, funding, slippage nei momenti di panico) possono annullare un vantaggio piccolo;
  la liquidazione può far perdere tutto il margine della posizione. Fiscalità italiana delle cripto da verificare prima dell'automatico.
- La tua premessa («bravo sui dip») resta da misurare (U0). Non è consulenza finanziaria.

## 9. Da fare (ordine)
Vedi `ROADMAP.md`. Setup congelati: `config/setups_v1.json` e `docs/PREREGISTRAZIONE_v1.md`.



## Fonti (consultate il 4/11/2026)
- TradingAgents: https://arxiv.org/abs/2412.20138 · ai-hedge-fund: https://github.com/virattt/ai-hedge-fund
- Alpha Arena S1: https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/
- Caporale-Plastun, *Price overreactions in the cryptocurrency market*, J. Economic Studies 46(5) 2019: https://econpapers.repec.org/RePEc:ces:ceswps:_6861
- Liu-Tsyvinski, RFS 2021: https://econpapers.repec.org/RePEc:oup:rfinst:v:34:y:2021:i:6:p:2689-2727.
- K33 sul funding negativo (via The Block, 6/5/2026): https://www.theblock.co/post/400182/bitcoin-longest-negative-funding-streak-this-decade-k33-flags-short-squeeze-risk · controesempio maggio 2022 (Decrypt): https://decrypt.co/364713/negative-funding-rates-hit-yearly-high-as-bitcoin-tests-76k
- He-Manela-Ross-von Wachter: https://arxiv.org/abs/2212.06888 · Kaminski-Lo 2014: https://dspace.mit.edu/handle/1721.1/114876
- Sentiment: Cavalheiro et al. 2024 https://ideas.repec.org/a/eme/rbfpps/rbf-08-2023-0224.html · Kraaijeveld-De Smedt 2020 https://core.ac.uk/download/391332344.pdf · Ciganovic 2023 https://iris.uniroma1.it/retrieve/1d32ef71-fae2-444c-a49b-40d528a423d4/Ciganovic_Forecasting_2023.pdf
- Disposition effect: https://arxiv.org/abs/2010.12415 · https://openaccess.city.ac.uk/id/eprint/32534
- X: `conversation_id` https://docs.x.com/x-api/fundamentals/conversation-id · prezzi pay-per-use https://opentweet.io/how-to/x-api-pay-per-use-explained (secondaria; autorità: Developer Console)
- Hyperliquid info: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint · API wallet: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets (via https://docs.privy.io/recipes/hyperliquid/agents-and-subaccounts) · prelievi solo dal master: https://docs.privy.io/recipes/hyperliquid-guide
- Deribit: https://docs.deribit.com/api-reference/market-data/public-get_book_summary_by_currency · GEX in cripto: https://insights.glassnode.com/gamma-exposure
- Fear & Greed: https://alternative.me/crypto/fear-and-greed-index/ · GDELT: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ · Reuters RSS: https://feeder.co/knowledge-base/rss-content/reuters-rss-feeds/
