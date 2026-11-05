# Chi compra il dip e chi vende il top

Scheda dell'app «Chi compra» (`bzd/flows.py`). Descrive chi cambia posizione quando il prezzo è tirato, e quanto forte. Non è testato come segnale e non è un consiglio. Niente alert su Telegram.

## Come funziona

**Due gruppi per mercato, più il denaro sulle cripto.**

| Mercati | Retail | Grossi o fondi | Denaro | Frequenza |
|---|---|---|---|---|
| Cripto (9) | quota di conti long su Binance e Bybit, dove ogni conto vale uno | quota long nelle posizioni dei top trader Binance, il 20% di conti con più margine | dollari comprati meno venduti da chi attraversa lo spread, su spot e futures Binance | 4h e giorno, dal dicembre 2021 |
| Azioni, bond, materie prime, forex (21) | «nonreportable» del COT: posizioni sotto la soglia di segnalazione | leveraged funds, o managed money sulle materie prime | – | settimanale dal 2006, misurato di martedì e pubblicato giorni dopo |

**Dip e top.** Sono le zone BYZ e SZT sui soli indicatori di prezzo (`zones.indicator_score`): punteggio fino a −50 e da +50 in su. Sul COT si legge il punteggio giornaliero alla data del report.

**Pressione e intensità.** Si misura la variazione di posizione: 1 giorno sul 4h, 3 giorni sul giornaliero, un report sul settimanale. La pressione è il percentile di quella variazione tra le variazioni precedenti dello stesso gruppo, riportato da −100 a +100, e usa solo il passato. L'intensità è la sua grandezza: +90 vuol dire più acquisti del 95% del passato.

| Intensità | Parola | Lettura |
|---|---|---|
| sotto 50 | debole | «fermo»: rumore normale |
| 50–79 | moderata | compra o vende |
| 80–94 | forte | compra o vende |
| da 95 | estrema | compra o vende |

**✦ Oltre il movimento.** La stessa pressione, tolto quanto il solo movimento del prezzo farebbe prevedere. Sul grafico, un triangolo pieno è ✦ e uno vuoto è riflesso. La pendenza usa solo barre precedenti, su una finestra mobile: 90 giorni sul 4h, 6 mesi sul giornaliero, 2 anni sul settimanale. Le finestre sono scelte perché il resto risulta scorrelato dal prezzo (tra −0,05 e +0,01 su BTC, ETH, oro e S&P 500), senza guardare i rendimenti.

**Apre o chiude.** Il COT separa long e short, quindi lì è un fatto. Sulle cripto è dedotto dalle posizioni aperte di tutto il mercato, con un «?» accanto, e sotto lo 0,5% non si dice.

Le soglie sono scelte a giudizio, non testate.

**Dove sono i dati.** `data/hist/positions/`, da `python -m bzd.history get positions`, circa 30 minuti. Le cripto si aggiornano ogni 4 ore con il giro degli alert, il COT con il suo giro settimanale. I file usati dai setup congelati non vengono toccati.

## Limiti: cosa è stato risolto e cosa resta

| Limite | Stato | Cosa c'è ora |
|---|---|---|
| Sulle cripto conta i conti, non i soldi | ridotto | il denaro è in dollari, ma dice dove spinge il denaro e non chi spinge. La size del retail resta invisibile |
| «Più long» può voler dire chiudere short | risolto sul COT, stimato sulle cripto | «apre» o «chiude» accanto a ogni gruppo |
| Solo Binance | ridotto | conti da Binance e Bybit, che si muovono insieme (correlazione 0,80–0,93 a 3 giorni su BTC, ETH e SOL). Top trader e denaro restano solo Binance, e Hyperliquid e OKX mancano |
| L'intensità dipende dal movimento | risolto | ✦ oltre il movimento |
| COT in ritardo | reso visibile, non risolto | colonna «Da allora» e ⚠ se oggi il prezzo non è più allo stesso estremo. Il dato resta settimanale |
| «Fondi» troppo generici | risolto | leveraged funds e managed money al posto dei non commerciali |
| Il retail del COT comprende piccoli professionisti | non risolvibile | la CFTC non li separa |

## Cosa dicono i dati

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
