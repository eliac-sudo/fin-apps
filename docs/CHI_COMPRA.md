# Chi è long e chi è short

Scheda dell'app «Chi compra» (`bzd/flows.py`). Dice come sono posizionati il retail e i grossi su ogni mercato, rispetto alla loro storia recente. Descrive, non è testato come segnale e non è un consiglio. Niente alert su Telegram.

Rifatta il 6 novembre 2026. La versione precedente chiedeva «chi compra il dip e chi vende il top», misurando la variazione di posizione in percentili, con verdetti, episodi, «oltre il movimento» e «apre o chiude». Era confusa. Inoltre il dip e il top sono le zone BYZ e SZT, che i test v3, v4 e v5 hanno smentito, e seguire chi compra sul dip (F1, F2) non ha dato vantaggi. Il codice delle variazioni resta solo perché il test v3 congelato lo usa.

## Come funziona

| Mercati | Retail | Grossi o fondi | Livello | Frequenza |
|---|---|---|---|---|
| Cripto (9) | quota di conti long su Binance e Bybit, dove ogni conto vale uno | quota long delle posizioni dei top trader Binance, il 20% di conti con più margine | la quota stessa | giornaliera, dal dicembre 2021 |
| Azioni, bond, materie prime, forex (21) | «nonreportable» del COT: posizioni sotto la soglia di segnalazione | leveraged funds, o managed money sulle materie prime | netto long meno short, in quota delle posizioni aperte, col segno della coppia come è quotata | settimanale dal 2006, misurato di martedì e pubblicato giorni dopo |

**Percentile sui 3 anni.** Per ogni gruppo, dove sta il livello di oggi tra quelli degli ultimi 3 anni dello stesso gruppo, da 0 (il più short) a 100 (il più long). Ogni valore usa solo il passato. Sul COT è il classico «COT index». Con meno di un anno (cripto) o due (COT) di storia non si calcola.

| Percentile | Parola |
|---|---|
| da 90 | molto long, affollato |
| 70–89 | più long del solito |
| 30–69 | nella norma |
| 10–29 | più short del solito |
| sotto 10 | molto short, affollato |

**Opposti:** un gruppo sopra il 70 e l'altro sotto il 30. **↑ o ↓:** il percentile si è mosso di almeno 5 punti in 3 giorni (cripto) o nell'ultimo report (COT). **Prezzo da allora:** sul COT, quanto si è mosso il prezzo dal martedì del report.

Perché il livello e non la variazione: la variazione di una settimana è rumore, e sulle cripto il retail si muove contro il prezzo per riflesso. Il livello dice se un gruppo è già sbilanciato, che è la domanda utile. Le soglie sono convenzioni, non testate.

**Dove sono i dati.** `data/hist/positions/`, da `python -m bzd.history get positions`. Le cripto si aggiornano ogni 4 ore con il giro degli alert, il COT con il suo giro settimanale.

## Limiti

- Sulle cripto il retail conta i conti, non i soldi; i top trader e i conti vengono solo da Binance e Bybit, mancano Hyperliquid e OKX.
- Il COT è in ritardo di 3–10 giorni e il suo retail comprende piccoli professionisti, che la CFTC non separa.
- La storia cripto parte dal dicembre 2021, quindi i «3 anni» coprono un solo ciclo.
- I livelli non sono testati: che un gruppo affollato preceda un'inversione è un'idea diffusa, non verificata qui.

## Cosa dicevano i dati della versione precedente

Misura descrittiva del 5 novembre 2026, non un test: barre sovrapposte, dati già visti, nessuna soglia fissata prima. Non va usata come regola.

**Il riflesso è delle cripto.** Variazione della quota long a 3 giorni contro il prezzo: retail −0,54 su BTC, −0,45 su ETH e −0,41 su SOL. I top trader stanno tra 0,01 e 0,22. Fuori dalle cripto non si vede: per settimana, sull'oro il retail ha +0,25 e i fondi +0,50, mentre sull'S&P 500 ha −0,02 e i fondi −0,37. Dire «il retail compra i dip» vale per le cripto, non in generale.

**Agli estremi è meno netto.** Su BTC ci sono 110 barre giornaliere di dip: il retail supera la soglia di acquisto nel 24%, i grossi nel 35%, il denaro nel 6%. Con ✦ il retail scende al 2% su BTC e al 4% su ETH: quasi tutto il suo comprare sui dip è riflesso.

**Dopo non si vede una differenza utile.** Rendimento medio rispetto alla deriva del mercato fino a quel momento, con un voto per mese:

| Mercati, orizzonte | Estremo | Chi agisce | Quando agisce | Altrimenti |
|---|---|---|---|---|
| Cripto, 5 giorni | dip | retail compra | +1,89% | +2,78% |
| Cripto, 5 giorni | dip | retail compra ✦ | +1,34% | +2,95% |
| Cripto, 5 giorni | dip | grossi comprano | +1,50% | +2,67% |
| Cripto, 5 giorni | dip | denaro compra | +0,82% | +2,52% |
| Cripto, 5 giorni | top | retail vende | −1,00% | −1,22% |
| Cripto, 5 giorni | top | grossi vendono | −0,23% | −1,89% |
| Cripto, 5 giorni | top | denaro vende | −1,62% | −1,57% |
| Altri, 4 settimane | dip | retail compra | −0,23% | +0,60% |
| Altri, 4 settimane | dip | fondi comprano | +1,37% | +0,49% |
| Altri, 4 settimane | top | retail vende | −0,29% | −0,49% |
| Altri, 4 settimane | top | fondi vendono | −0,27% | −0,52% |

Sui dip delle cripto i rendimenti sono stati migliori quando il gruppo in questione **non** comprava con forza, per tutti e tre i gruppi, presi uno alla volta. Sono più di venti confronti senza intervalli di confidenza, quindi qualche scarto è atteso per caso: è un'ipotesi, non un risultato. Dire che seguire un gruppo aiuta richiede una pre-registrazione v2 su dati nuovi.

## Portafogli profittevoli su Hyperliquid

`bzd/wallets.py`, servizio `python3 -m bzd.wallets run`. Rifatto il 6 novembre 2026: prima seguiva anche i perdenti e mostrava solo una tabella per mercato, poco leggibile.

**Chi si segue, scelto ogni giorno.**
- **Trader:** i 150 con più profitti di sempre e i 50 del mese (se non già nei primi). Solo conti sopra $100.000 che nel mese muovono tra 0,5 e 100 volte il capitale: sotto sono conti fermi, sopra market maker. Le soglie vengono dalla classifica del 6 novembre.
- **Vault:** fino a 40 vault aperti, con almeno $100.000 depositati, 90 giorni di vita e un profitto storico, ordinati per profitto. I vault del protocollo (HLP) restano fuori, perché sono il market making della borsa e non una strategia.

**Cosa si registra.** Ogni ora le posizioni di tutti. Ogni giorno i fill nuovi, che si accumulano per 180 giorni: Hyperliquid dà solo gli ultimi 10.000, quindi per i conti più attivi senza registrazione la storia si perderebbe.

**Nell'app** («Chi compra», in fondo), ogni conto mostra capitale, profitto storico, profitto del mese o APR del vault, quanto è net long o short, la leva e le posizioni principali. Cliccandolo si aprono:
- le posizioni aperte, con entrata, PnL aperto, leva e distanza dalla liquidazione;
- per i vault, la descrizione del gestore, i depositanti, la commissione e la quota del gestore;
- **come opera**, ricostruito dai fill degli ultimi 30 giorni: quanto tiene una posizione, se apre long o short, su quali mercati e con che risultato, quante chiusure in utile, ordini limite o a mercato, TWAP, e in che ore UTC;
- la curva del profitto dall'inizio e il calo massimo;
- l'esposizione nel tempo, dalle nostre foto orarie.

**Come si stima la durata.** Una posizione conta da quando parte da zero a quando torna a zero. Molti conti grandi non tornano mai a zero: aggiungono e tolgono. Per loro la durata è stimata dal giro d'affari, cioè l'esposizione di oggi divisa per metà del volume giornaliero, e l'app scrive «circa».

Cautele:
- **Descrive, non è testato.** Il profitto passato non prova bravura: un vincente può essere fortunato, coprire una posizione fatta altrove o essere una gamba di un arbitraggio.
- **I vincenti del mese sono in parte circolari:** dopo un calo sono soprattutto chi era short.
- **Copiare non è stato provato.** Dire se seguire questi conti renderebbe richiede mesi di registrazione e una pre-registrazione.
