# Note sulla letteratura

Scritte dal lettore (`python -m bzd.research leggi`) **solo sugli abstract**, e controllate dal codice: ogni citazione è nell'abstract e ogni numero ha una fonte. Un abstract è breve, quindi «non verificabile» è l'esito normale per molte affermazioni. Leggere il lavoro intero resta l'unico controllo vero.

## The probability of backtest overfitting (2016)

[Fonte](https://doi.org/10.21314/jcf.2016.322) · da report Gemini · ok

**Tesi.** I backtest usati per scegliere strategie di investimento sono spesso inaffidabili e rischiano l'overfitting; gli autori propongono un metodo per stimare la probabilità che un backtest sia overfit (PBO).

**Metodo e dati.** Metodo numerico chiamato combinatorially symmetric cross-validation (CSCV), usato per stimare la PBO nel contesto delle simulazioni di investimento. Non specificati nell'abstract. Gli autori rimandano alle appendici disponibili su SSRN.

- Le tecniche statistiche standard, come l'hold-out, sono poco affidabili per i backtest di investimento. («Standard statistical techniques designed to prevent regression over-fitting, such as hold-out, tend to be unreliable and inaccurate in the context of investment backtests»)
- Viene proposto un quadro per stimare la probabilità di overfitting dei backtest, tramite CSCV. («We propose a framework that estimates the probability of backtest over-fitting (PBO)»)
- Gli autori sostengono che CSCV dia stime accurate della probabilità che un dato backtest sia overfit. («We show that CSCV produces accurate estimates of the probability that a particular backtest is over-fit»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Il teorema dimostra che esplorare e ottimizzare decine di configurazioni dei parametri di un indicatore tecnico su una serie storica garantisce artificialmente l'identificazione di un apparente In-Sample Sharpe Ratio eccellente, che si traduce ineluttabilmente in fallimento Out-of-Sample.» Abstract: «We propose a framework that estimates the probability of backtest over-fitting (PBO)». L'abstract parla di una probabilità stimata con CSCV, non di un teorema. Non cita In-Sample Sharpe Ratio, decine di configurazioni né un fallimento certo fuori campione, quindi non si può confermare né contraddire l'affermazione.

**Per BZD:** pertinenza alta, setup e test. BZD testa strategie su backtest e il lavoro riguarda proprio il rischio che quei backtest siano sovradattati, quindi serve a valutare la robustezza dei test.
Idea da misurare: Stimare con CSCV la probabilità di overfitting delle strategie BZD su orizzonti da un giorno a un mese, prima di allocarvi capitale.
Limiti: L'abstract è breve e non riporta dati, risultati numerici né dettagli del metodo; Le appendici non sono state lette, quindi non è possibile verificare le dimostrazioni; Il lavoro non dice nulla su cripto, azioni, bond, materie prime o forex né su dati di retail o funding.

## Empirical Asset Pricing via Machine Learning (2020)

[Fonte](https://doi.org/10.1093/rfs/hhaa009) · da report Gemini · ok

**Tesi.** Il machine learning misura i premi al rischio degli asset meglio dei metodi di regressione classici, con grandi guadagni economici per l'investitore. Alberi e reti neurali sono i metodi migliori, e il vantaggio nasce dalle interazioni non lineari tra predittori.

**Metodo e dati.** Confronto comparativo di diversi metodi di machine learning per stimare i premi al rischio degli asset, misurati anche in termini di rendimento economico per l'investitore. Non specificati nell'abstract: si parla solo di premi al rischio degli asset, senza indicare quali asset, periodo o fonte.

- I guadagni economici con il machine learning sono grandi, in alcuni casi il doppio delle strategie di regressione di riferimento. («in some cases doubling the performance of leading regression-based strategies from the literature»)
- I metodi migliori sono alberi e reti neurali. («We identify the best-performing methods (trees and neural networks)»)
- Il vantaggio dei metodi migliori deriva dalle interazioni non lineari tra predittori, che gli altri metodi non colgono. («allowing nonlinear predictor interactions missed by other methods»)
- Tutti i metodi concordano sullo stesso insieme di segnali predittivi dominanti, che include varianti di momentum, liquidità e volatilità. («All methods agree on the same set of dominant predictive signals, a set that includes variations on momentum, liquidity, and volatility»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Le Reti Neurali (con strutture feed-forward a più strati) raggiungono i migliori risultati in termini di R-quadro predittivo out-of-sample» Abstract: «We identify the best-performing methods (trees and neural networks)». L'abstract dice che le reti neurali sono tra i metodi migliori, insieme agli alberi, ma non parla di R-quadro out-of-sample né di strutture feed-forward a più strati, quindi quei dettagli non si possono verificare.
- Confermata: «I segnali che il machine learning identifica costantemente come più informativi sono invariabilmente legati a dinamiche di trend dei prezzi (momentum a breve termine e reversal), metriche di liquidità e volatilità passata.» Abstract: «All methods agree on the same set of dominant predictive signals, a set that includes variations on momentum, liquidity, and volatility». Momentum, liquidità e volatilità sono confermati come segnali dominanti. L'abstract non parla di reversal di breve termine né dice invariabilmente, quindi questi dettagli restano non verificati.

**Per BZD:** pertinenza media, tecnica e tag BYZ/SZT, setup e test. Il lavoro mostra che segnali di momentum, liquidità e volatilità dominano la previsione dei rendimenti attesi, e tutto il confronto è fatto su predizione out-of-sample. Questo è utile a BZD per la parte di tecnica e di test dei segnali, anche se l'abstract non dice nulla su cripto, forex, opzioni o orizzonti da un giorno a un mese.
Idea da misurare: Usare un modello non lineare (ad esempio un albero) su momentum, liquidità e volatilità per prevedere i rendimenti a un mese di cripto e azioni, confrontandolo con una regressione lineare semplice.
Limiti: L'abstract non specifica dati, periodo, universo di asset né orizzonte di previsione; Non riporta i valori numerici di R-quadro né l'entità esatta dei guadagni economici; Non dice come sono stati costruiti i portafogli né quali costi di transazione sono stati considerati; L'appendice tecnica è citata ma non è disponibile nel testo fornito.

## Investor Sentiment and the Cross‐Section of Stock Returns (2006)

[Fonte](https://doi.org/10.1111/j.1540-6261.2006.00885.x) · da report Gemini · ok

**Tesi.** Il sentiment degli investitori influisce sulla cross-section dei rendimenti azionari: gli effetti sono maggiori su titoli con valutazioni molto soggettive e difficili da arbitrare.

**Metodo e dati.** Dall'abstract non si ricava il dettaglio del metodo. Il lavoro costruisce proxy di sentiment all'inizio del periodo e confronta i rendimenti successivi di diverse categorie di titoli in base al livello del sentiment. L'abstract non specifica i dati né i proxy di sentiment. Cita solo rendimenti azionari su categorie di titoli: piccole, giovani, ad alta volatilità, non redditizie, senza dividendi, growth estremi e in difficoltà.

- Con sentiment basso a inizio periodo, i rendimenti successivi sono relativamente alti per le categorie di titoli considerate. («when beginning‐of‐period proxies for sentiment are low, subsequent returns are relatively high»)
- Con sentiment alto, le stesse categorie rendono relativamente poco nel periodo successivo. («When sentiment is high, on the other hand, these categories of stock earn relatively low subsequent returns.»)
- L'effetto del sentiment è previsto più forte su titoli con valutazioni soggettive e difficili da arbitrare, e i dati sono coerenti con questa previsione. («a wave of investor sentiment has larger effects on securities whose valuations are highly subjective and difficult to arbitrage»)

**Cosa dice Gemini, e l'abstract.**

- Confermata: «durante i regimi di elevato ottimismo, l'eccesso di domanda irrazionale si concentra sui titoli "difficili da prezzare" e "difficili da arbitrare"» Abstract: «a wave of investor sentiment has larger effects on securities whose valuations are highly subjective and difficult to arbitrage». L'abstract sostiene che gli effetti del sentiment sono maggiori sui titoli difficili da prezzare e da arbitrare. Il meccanismo dell'eccesso di domanda irrazionale non compare nell'abstract.
- Non verificabile dall'abstract: «i rendimenti attesi di questi asset nei periodi successivi a picchi di sentiment risultano sistematicamente inferiori e spesso negativi» Abstract: «subsequent returns are relatively high». L'abstract dice che i rendimenti successivi sono relativamente bassi dopo sentiment alto. Non parla di rendimenti negativi né di sistematicità in senso stretto.

**Per BZD:** pertinenza media, sentiment. Il lavoro riguarda il sentiment come fattore di rendimento, che è vicino al modulo sentiment di BZD. Però l'universo è quello delle singole azioni, mentre BZD non sceglie singole azioni: il segnale utile sarebbe a livello di panieri o mercato.
Idea da misurare: Verificare se un indicatore di sentiment da dati gratuiti (posizionamento di retail o fondi) anticipa a un mese il rendimento relativo di panieri ad alta volatilità contro panieri a bassa volatilità.
Limiti: Il giudizio si basa solo sull'abstract, senza metodo, dati e periodo campionario; I proxy di sentiment non sono specificati nell'abstract; Lo studio è del 2006 e riguarda il mercato azionario USA, non cripto, bond, materie prime o forex; Non è chiaro quanto l'effetto resista a costi di transazione e a orizzonti di un mese.

## Optimal execution of portfolio transactions (2001)

[Fonte](https://doi.org/10.21314/jor.2001.041) · da report Gemini · ok

**Tesi.** Il lavoro propone di eseguire operazioni su un portafoglio minimizzando insieme il rischio di volatilità e i costi di transazione, dovuti all'impatto di mercato permanente e temporaneo. Il rischio di volatilità cresce con il tempo di liquidazione, mentre i costi crescono con la velocità di esecuzione: la scelta ottima sta nel compromesso tra le due cose.

**Metodo e dati.** Ottimizzazione di strategie di liquidazione dipendenti dal tempo, con un modello di costo lineare che permette di costruire esplicitamente la frontiera efficiente. Le strategie ottime si selezionano minimizzando una funzione di utilità quadratica oppure il value-at-risk (VaR), da cui il concetto di L-VaR (liquidity-adjusted VaR). L'abstract non descrive dati empirici né un campione di mercato: il lavoro è di tipo teorico-modellistico.

- Nello spazio delle strategie di liquidazione dipendenti dal tempo, la frontiera efficiente contiene le strategie con il costo atteso di esecuzione più basso per un dato livello di incertezza. («the efficient frontier consists of strategies having the lowest expected execution cost for a given level of uncertainty»)
- Con un modello di costo lineare la frontiera efficiente si può costruire esplicitamente. («with a linear cost model this frontier can be explicitly constructed»)
- Minimizzando il VaR si ottiene il L-VaR, che considera il miglior compromesso tra rischio di volatilità e costi di liquidazione. («explicitly considers the best tradeoff between volatility risk and liquidation costs»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Il testo sacro per gli algoritmi di esecuzione ottima (TWAP/VWAP istituzionale) sui mercati digitali.» L'abstract tratta l'esecuzione ottima di portafogli con un modello teorico e non menziona mercati digitali, TWAP o VWAP. Non dice nulla sul fatto che sia il testo di riferimento del settore, né sull'uso istituzionale degli algoritmi. Le parole TWAP e VWAP non compaiono nell'abstract.

**Per BZD:** pertinenza media, uscite e piano. Il lavoro riguarda come eseguire uscite da posizioni grandi con costi e rischio bilanciati. È utile per il piano di uscita e per stimare i costi di impatto, ma è un modello teorico e non usa cripto o dati di retail, funding o sentiment. Non riguarda la scelta di cosa comprare.
Idea da misurare: Stimare con dati di volume gratuiti quanto costa uscire da una posizione in cripto o forex in tempi diversi, e confrontare il costo stimato con il rischio di volatilità durante l'uscita.
Limiti: L'abstract non riporta dati empirici né risultati numerici; Il modello assume un costo di impatto lineare, che potrebbe non valere nei mercati cripto o in periodi di stress; Il lavoro è del 2001 e riguarda principalmente i mercati azionari tradizionali; Il testo non contiene indicazioni su segnali di acquisto o di vendita.

## Risk, Return, and Equilibrium: Empirical Tests (1973)

[Fonte](https://doi.org/10.1086/260061) · da report Gemini · ok

**Tesi.** Il lavoro verifica se per le azioni del NYSE il rendimento medio cresca con il rischio, come previsto dai modelli di equilibrio derivati dal modello di portafoglio a due parametri. Gli autori non rifiutano l'ipotesi che i prezzi riflettano investitori avversi al rischio che tengono portafogli efficienti.

**Metodo e dati.** Regressioni rischio-rendimento sui titoli del NYSE, con test dei coefficienti e dei residui. Il metodo preciso (regressioni cross-sectional per gruppi di titoli) non è dettagliato nell'abstract. Azioni ordinarie quotate al New York Stock Exchange. Periodo e numero di titoli non sono nell'abstract.

- Non si rifiuta l'ipotesi che i prezzi delle azioni riflettano investitori avversi al rischio che cercano portafogli efficienti in media e dispersione dei rendimenti. («We cannot reject the hypothesis of these models»)
- Le proprietà fair game dei coefficienti e dei residui sono coerenti con un mercato efficiente. («are consistent with an "efficient capital market"»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «L'origine della metrica di cross-sectional regression, imprescindibile per validare qualsiasi anomalia o rischio sistematico.» L'abstract non dice nulla sull'origine della metrica cross-sectional né su anomalie o rischio sistematico. Il lavoro usa regressioni rischio-rendimento, ma la affermazione di Gemini va oltre quanto l'abstract riporta.

**Per BZD:** pertinenza media, nessuno. Il lavoro è un riferimento classico sul rapporto tra rischio e rendimento e sull'efficienza dei mercati, utile per capire i fondamenti del rischio sistematico. Non tocca direttamente cripto, sentiment, posizionamento o opzioni, e il dataset del 1973 è solo azionario NYSE.
Limiti: L'abstract è breve e non riporta periodo, numero di titoli né risultati numerici; Il lavoro è del 1973 e riguarda solo azioni NYSE, quindi la generalizzazione a cripto e altri asset è da verificare; L'affermazione di Gemini non è verificabile dal solo abstract.

## WHAT DO WE KNOW ABOUT THE PROFITABILITY OF TECHNICAL ANALYSIS? (2007)

[Fonte](https://doi.org/10.1111/j.1467-6419.2007.00519.x) · da report Gemini · ok

**Tesi.** Il lavoro rivede le prove sulla redditività dell'analisi tecnica, dividendo la letteratura in studi 'early' e 'modern'. Gli studi early trovano profitti nei cambi e nei futures ma non nelle azioni; quelli modern trovano profitti costanti in vari mercati speculativi almeno fino ai primi anni '90, pur con problemi di metodo.

**Metodo e dati.** Rassegna della letteratura empirica, classificata per caratteristiche delle procedure di test. Conteggio di 95 studi modern: 56 positivi, 20 negativi, 19 misti. Non specificati nell'abstract: il lavoro riassume studi esistenti su mercati dei cambi, futures e azionari.

- Studi early: strategie tecniche redditizie nei cambi e nei futures, non nelle azioni. («Early studies indicate that technical trading strategies are profitable in foreign exchange markets and futures markets, but not in stock markets.»)
- Studi modern: profitti economici costanti in vari mercati speculativi, almeno fino ai primi anni '90. («Modern studies indicate that technical trading strategies consistently generate economic profits in a variety of speculative markets at least until the early 1990s.»)
- Esito della letteratura modern: 56 positivi, 20 negativi, 19 misti su 95 studi. («56 studies find positive results regarding technical trading strategies, 20 studies obtain negative results, and 19 studies indicate mixed results.»)
- Limiti dei test: data snooping, selezione ex post delle regole, stima di rischio e costi di transazione. («data snooping, ex post selection of trading rules or search technologies, and difficulties in estimation of risk and transaction costs»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Le valutazioni storiche (es. la rassegna di Park e Irwin, 2007) mostravano una certa profittabilità dei pattern tecnici (es. moving average crossover, figure di supporto/resistenza) nei mercati fino agli anni '90.» L'abstract non cita pattern specifici come moving average crossover o supporto/resistenza, né il periodo storico come 'fino agli anni 90' per la rassegna del 2007 in questi termini: parla di profitti fino ai primi anni '90 in generale, senza menzionare i pattern richiesti.

**Per BZD:** pertinenza media, tecnica e tag BYZ/SZT, setup e test. È una rassegna sulla redditività delle regole tecniche, quindi utile per il modulo di test e per capire quali risultati riguardano mercati simili a quelli di BZD. Però copre studi fino ai primi anni '90 e non dice nulla su dati gratuiti come posizionamento, funding o sentiment.
Idea da misurare: Rifare un test di regole tecniche semplici su cripto e forex a orizzonte da un giorno a un mese, con controllo di data snooping e costi di transazione.
Limiti: Abstract breve: non si possono verificare i dettagli delle regole né i periodi dei singoli studi; La letteratura citata è in gran parte precedente agli anni '90, quindi datata rispetto ai mercati attuali; Non riguarda dati di posizionamento, sentiment o opzioni.

## … and the Cross-Section of Expected Returns (2015)

[Fonte](https://doi.org/10.1093/rfs/hhv059) · da report Gemini · ok

**Tesi.** Con tanti fattori testati, la soglia usuale di significatività non basta: un nuovo fattore deve superare una soglia molto più alta, con t-statistic maggiore di 3.0. Gli autori sostengono che la maggior parte dei risultati dichiarati in finanza empirica probabilmente sono falsi.

**Metodo e dati.** Un nuovo framework di test multipli, che fornisce soglie storiche dai primi test empirici del 1967 a oggi. L'abstract non descrive altro dettaglio tecnico. Non specificati nell'abstract, se non il riferimento ai fattori e ai lavori empirici dal 1967 in poi.

- Serve una soglia più alta della consueta per i nuovi fattori («A new factor needs to clear a much higher hurdle, with a t-statistic greater than 3.0»)
- Le soglie sono calcolate storicamente, dal 1967 a oggi («provides historical cutoffs from the first empirical tests in 1967 to today»)
- Gran parte dei risultati dichiarati potrebbe essere falsa («We argue that most claimed research findings in financial economics are likely false»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Gli autori hanno censito oltre 316 fattori pubblicati sulle principali riviste accademiche» Abstract: «Hundreds of papers and factors attempt to explain the cross-section of expected returns». L'abstract dice centinaia di lavori e fattori, ma non riporta il numero 316 né il fatto che siano sulle principali riviste.
- Confermata: «Il nuovo standard accademico stabilisce che, per dichiarare valida una nuova anomalia, il test t-statistic debba essere innalzato ad almeno 3.0.» Abstract: «A new factor needs to clear a much higher hurdle, with a t-statistic greater than 3.0». L'abstract dice maggiore di 3.0, mentre Gemini scrive almeno 3.0: sostanza uguale, ma la soglia precisa è leggermente diversa. Parla di nuovi fattori, non di anomalie in senso generale.

**Per BZD:** pertinenza media, setup e test. Il lavoro riguarda il rischio di falsi positivi quando si testano molte variabili. BZD testa molti segnali su cripto, azioni, bond, materie prime e forex, quindi la stessa logica serve a valutare i propri test. Non riguarda però direttamente posizionamento, sentiment, opzioni od orizzonti di trading.
Idea da misurare: Applicare una soglia di t-statistic più severa, o una correzione per test multipli, ai segnali di BZD che hanno superato il backtest su più varianti.
Limiti: Solo abstract, senza dettagli sul metodo di correzione né sui dati; Riguarda il cross-section dei fattori di rendimento atteso, non segnali di trading a breve termine; Non dice quanto la nuova soglia riduca i falsi positivi in pratica; Le affermazioni di Gemini includono un numero (316) non presente nell'abstract.

## A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle (1989)

[Fonte](https://doi.org/10.2307/1912559) · da report Gemini · ok

**Tesi.** Il lavoro propone un modello per salti discreti e occasionali nel tasso di crescita di una serie non stazionaria, con algoritmi per stimarli e per la massima verosimiglianza. Applicato al PIL USA, suggerisce che il passaggio da crescita positiva a negativa è una caratteristica ricorrente del ciclo economico e potrebbe servire come criterio oggettivo per definire le recessioni.

**Metodo e dati.** Modello a cambio di regime con salti discreti nel tasso di crescita di una serie non stazionaria; algoritmi per inferire gli stati non osservati, che producono anche la stima dei parametri per massima verosimiglianza. Serie storiche macroeconomiche degli Stati Uniti, in particolare il PIL (GNP): l'abstract cita esplicitamente il GNP, ma non specifica periodo o frequenza.

- Il passaggio da crescita positiva a negativa è una caratteristica ricorrente del ciclo economico USA. («the periodic shift from a positive growth rate to a negative growth rate is a recurrent feature of the U.S. business cycle»)
- Il modello potrebbe fornire una definizione oggettiva di recessione. («could be used as an objective criterion for defining and measuring economic recessions»)
- Una tipica recessione è associata a un calo permanente del livello del GNP di circa il 3 per cento. («a typical economic recession is associated with a 3 percent permanent drop in the level of GNP»)

**Per BZD:** pertinenza bassa, nessuno. Il lavoro riguarda il ciclo macroeconomico USA con dati trimestrali di PIL e non tocca cripto, azioni singole, bond, materie prime o forex a orizzonti da un giorno a un mese. Non ci sono dati di posizionamento, funding, sentiment, opzioni o tecnica di prezzo. Può dare un contesto sul regime di recessione, ma non un input operativo per BZD.
Limiti: L'abstract è breve e non dà dettagli su periodo campionario, frequenza dei dati o specificazione completa del modello; Non ci sono affermazioni di Gemini da verificare; Il lavoro usa il PIL, che non è disponibile con frequenza giornaliera, quindi non si adatta agli orizzonti di BZD.

## Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings? (1996)

[Fonte](https://doi.org/10.2308/tar-9608042309) · da report Gemini · ok

**Tesi.** Il lavoro chiede se i prezzi azionari riflettono l'informazione sugli utili futuri contenuta nelle componenti accruals e flussi di cassa dell'utile corrente. L'abstract pone la domanda ma non riporta una conclusione.

**Metodo e dati.** Non specificato nell'abstract. Non specificati nell'abstract.

- L'abstract presenta la domanda di ricerca (se i prezzi riflettono l'informazione su accruals e flussi di cassa) ma non riporta risultati. («Investigates whether stock prices reflect information about future corporate earnings»)

**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «Poiché la componente legata ai flussi di cassa operativi è molto più persistente nel tempo rispetto alla componente contabile (accruals), gli investitori tendono a "fissarsi" sul dato netto aggregato dell'utile, sovrastimando le performance future delle aziende con alti accruals e sottostimando quelle con forti cash flow.» L'abstract non dice nulla sulla persistenza dei flussi di cassa rispetto agli accruals, né su una sovrastima o sottostima dei prezzi. Dichiara solo la domanda di ricerca.

**Per BZD:** pertinenza bassa, nessuno. Il lavoro riguarda l'efficienza dei prezzi azionari rispetto alla composizione dell'utile di singole aziende. BZD non sceglie singole azioni e non usa bilanci: l'uso è solo indiretto, come contesto sul sentiment del mercato.
Limiti: L'abstract non riporta metodo, dati, campione né risultati; Il lavoro usa bilanci aziendali, dati che BZD non usa; L'orizzonte temporale della previsione non è indicato.

## Quantifying the High-Frequency Trading "Arms Race" (2020)

[Fonte](https://doi.org/10.1093/qje/qjab032) · da report Gemini · ok

**Tesi.** Il lavoro quantifica il costo dell'arbitraggio di latenza, una forma negativa di trading ad alta frequenza, usando i dati dei messaggi della borsa, che includono anche i tentativi di trade o cancellazione falliti. Sostiene che queste gare sono frequenti, molto rapide e costose per la liquidità.

**Metodo e dati.** Analisi dei dati dei messaggi di borsa per individuare le gare di latenza, cioè eventi in cui più operatori cercano di sfruttare la stessa opportunità, e stima dei loro effetti su impatto di prezzo, spread effettivo e costo della liquidità. Dati di messaggi di una borsa azionaria, con esempio sulle azioni del FTSE 100. L'abstract non descrive in dettaglio il periodo né la fonte esatta.

- Le gare di arbitraggio di latenza sono molto frequenti, circa una al minuto per simbolo per le azioni del FTSE 100. («latency arbitrage races are very frequent (about one per minute per symbol for FTSE 100 stocks)»)
- Le gare durano pochissimo e rappresentano una quota grande del volume totale. («account for a remarkably large portion of overall trading volume (about 20%)»)
- La partecipazione è concentrata: sei imprese fanno oltre l'80% delle vittorie e sconfitte. («the top six firms accounting for over 80% of all race wins and losses»)
- L'arbitraggio di latenza impone una tassa stimata di circa 0,5 punti base sugli scambi. («latency arbitrage imposes a roughly 0.5 basis point tax on trading»)
- Le somme in gioco sono nell'ordine di 5 miliardi di dollari l'anno solo nei mercati azionari globali. («the total sums at stake are on the order of $5 billion per year in global equity markets alone»)

**Cosa dice Gemini, e l'abstract.**

- Confermata: «L'evidenza basata su "message data" (che includono i tentativi di cancellazione falliti, a differenza dei tradizionali dataset TAQ) stima che tale arbitraggio costi ai mercati miliardi di dollari annualmente, funzionando come una tassa sulla fornitura di liquidità.» Abstract: «latency arbitrage imposes a roughly 0.5 basis point tax on trading». L'abstract conferma miliardi di dollari l'anno e una tassa sugli scambi, non esplicitamente sulla fornitura di liquidità. La stima da miliardi riguarda solo i mercati azionari globali. L'abstract non menziona i dataset TAQ, quindi quella parte non è verificabile dall'abstract.

**Per BZD:** pertinenza bassa, nessuno. Il lavoro studia gare di latenza in microsecondi sui mercati azionari, cioè alta frequenza, che BZD non fa. BZD opera su orizzonti da un giorno a un mese e non sceglie singole azioni. Il risultato sul costo della liquidità è utile come contesto ma non si traduce nei segnali di BZD.
Limiti: Il lavoro riguarda gare in microsecondi, fuori dagli orizzonti di BZD; I risultati si riferiscono alle azioni, mentre BZD studia anche cripto, bond, materie prime e forex; L'abstract non dà dettagli sul periodo, sulla fonte esatta dei dati e sul metodo di stima; Le stime in dollari valgono solo per i mercati azionari globali.

## The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response (2013)

[Fonte](https://doi.org/10.1093/qje/qjv027) · da report Gemini · ok

**Tesi.** Il lavoro sostiene che la corsa all'alta frequenza è un sintomo di un design di mercato difettoso. Propone le aste a lotti frequenti (batch auction a prezzo uniforme, ad esempio ogni decimo di secondo) al posto del libro ordini a tempo continuo.

**Metodo e dati.** Tre parti: analisi empirica di fatti stilizzati a livello di millisecondi; un modello teorico semplice che spiega i fatti; un confronto tra aste a lotti frequenti e libro ordini continuo. Dati direct-feed a livello di millisecondi provenienti dagli exchange. L'abstract non specifica altri dataset.

- Nel mercato continuo le correlazioni a orizzonti di alta frequenza si rompono completamente. («correlations completely break down»)
- Ne derivano opportunità di arbitraggio meccanico evidenti, costruite nel design del mercato. («are built into the market design»)
- La concorrenza non ha cambiato dimensione e frequenza di questi arbitraggi, ha solo alzato la velocità richiesta per catturarli. («it has only raised the bar for how fast one has to be to capture them»)
- Le aste a lotti frequenti eliminano le rendite di arbitraggio meccanico e trasformano la competizione sulla velocità in competizione sul prezzo. («the auction transforms competition on speed into competition on price»)

**Cosa dice Gemini, e l'abstract.**

- Confermata: «dimostra che l'architettura a tempo continuo del LOB genera un'inefficienza intrinseca: una competizione per la priorità temporale che sfocia in un "latency arbitrage" (arbitraggio di latenza).» Abstract: «continuous-time serial-processing implies that even symmetrically observed public information creates arbitrage rents». L'abstract sostiene che il tempo continuo con elaborazione seriale genera rendite di arbitraggio anche da informazioni pubbliche. Il termine «latency arbitrage» non compare nell'abstract, ma il contenuto corrisponde.
- Non verificabile dall'abstract: «L'evidenza basata su "message data" (che includono i tentativi di cancellazione falliti, a differenza dei tradizionali dataset TAQ) stima che tale arbitraggio costi ai mercati miliardi di dollari annualmente, funzionando come una tassa sulla fornitura di liquidità.» Abstract: «These rents harm liquidity provision». L'abstract dice che le rendite danneggiano la fornitura di liquidità, ma non parla di «message data», di miliardi di dollari annui né di una tassa sulla liquidità. Il dataset citato è direct-feed a livello di millisecondi.

**Per BZD:** pertinenza bassa, nessuno. Il lavoro riguarda la microstruttura degli exchange e la latenza a livello di millisecondi, cioè l'alta frequenza. BZD lavora su orizzonti da un giorno a un mese con dati gratuiti su posizionamento, sentiment, tecnica e opzioni, quindi il tema è lontano dal suo uso.
Limiti: L'abstract non riporta stime quantitative dei costi dell'arbitraggio; Il lavoro usa dati direct-feed a millisecondi, non disponibili a BZD con dati gratuiti; Il lavoro è teorico e normativo: propone un cambio di design di mercato, non una strategia di trading; Il riassunto è breve e non permette di verificare i dettagli empirici.

## The “Actual Retail Price” of Equity Trades (2025)

[Fonte](https://doi.org/10.1111/jofi.13467) · da report Gemini · ok

**Tesi.** Il prezzo effettivo di esecuzione degli ordini di mercato varia molto tra broker, e la differenza nasce dai grossisti off-exchange che danno prezzi diversi agli stessi ordini a seconda del broker; la variazione del PFOF non spiega questa differenza.

**Metodo e dati.** Confronto di sei conti di brokeraggio presso cinque broker, con ordini di mercato inviati simultaneamente (campione di 85.000 ordini) per misurare il costo di round-trip a livello di conto, esclusa la commissione. Ordini di mercato azionari generati dagli autori su sei conti reali presso cinque broker, con misure di commissioni e PFOF per conto.

- Il costo medio di round-trip per conto, escluse le commissioni, va da 0,07% a 0,46%. («the mean account‐level round‐trip cost ranges from 0.07% to 0.46%»)
- La dispersione dipende dai grossisti off-exchange che applicano prezzi diversi agli stessi ordini a broker diversi. («off‐exchange wholesalers systematically giving different execution prices for the same trades to different brokers»)
- La variazione del PFOF tra broker non spiega la grande variazione nei prezzi di esecuzione. («variation in PFOF does not explain the large variation in price execution»)

**Cosa dice Gemini, e l'abstract.**

- Confermata: «documentano che il pagamento in sé (nell'ordine di frazioni di centesimo) non è il fattore primario che determina la qualità dell'esecuzione.» Abstract: «Across brokers, variation in PFOF does not explain the large variation in price execution.». L'abstract dice che la variazione del PFOF non spiega la grande variazione nei prezzi di esecuzione. Non cita però l'entità del PFOF in frazioni di centesimo, che resta non verificabile dall'abstract; la conclusione sul fattore primario è coerente con la frase citata.

**Per BZD:** pertinenza bassa, nessuno. Lavoro sulla qualità dell'esecuzione al dettaglio, utile come contesto sui costi di trading. BZD opera su orizzonti da un giorno a un mese con dati gratuiti e non ha accesso a esecuzioni o ordini di retail da confrontare, quindi il lavoro non si collega ai suoi moduli.
Limiti: L'abstract non riporta il metodo di stima dei costi né il periodo del campione; Il campione riguarda sei conti presso cinque broker, quindi la generalizzabilità è limitata; Non si applica direttamente a cripto, forex o materie prime.

## Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers (2000)

[Fonte](https://doi.org/10.2307/2672906) · da report Gemini · ok

**Tesi.** Non ricavabile: il testo fornito è solo la citazione bibliografica, senza contenuto del riassunto.

**Metodo e dati.** Non ricavabile dall'abstract fornito. Non ricavabile dall'abstract fornito.


**Cosa dice Gemini, e l'abstract.**

- Non verificabile dall'abstract: «incrementando il rendimento annuale medio del portafoglio di 7.5% su un periodo di vent'anni.» Il testo fornito non contiene risultati sul rendimento del portafoglio, quindi il 7.5% annuo non può essere né confermato né smentito.

**Per BZD:** pertinenza bassa, nessuno. Il titolo parla di separare vincitori e perdenti tra le singole aziende con dati di bilancio, mentre BZD non sceglie singole azioni e non usa bilanci.
Limiti: L'abstract fornito è solo la citazione bibliografica, senza il testo del riassunto; Senza il riassunto non si possono verificare metodo, dati e risultati; L'affermazione di Gemini riguarda un dato numerico che non compare nel testo fornito.

## A five-factor asset pricing model (2014)

[Fonte](https://doi.org/10.1016/j.jfineco.2014.10.010) · da report Gemini · no_abstract

Nessuna nota: l'editore non rende pubblico l'abstract, quindi nessuna chiamata.

## Chapter 18 A survey of behavioral finance (2003)

[Fonte](https://doi.org/10.1016/s1574-0102(03)01027-6) · da report Gemini · no_abstract

Nessuna nota: l'editore non rende pubblico l'abstract, quindi nessuna chiamata.

## Continuous Auctions and Insider Trading (1985)

[Fonte](https://doi.org/10.2307/1913210) · da report Gemini · no_abstract

Nessuna nota: l'editore non rende pubblico l'abstract, quindi nessuna chiamata.

## Forecasting the Equity Risk Premium: The Role of Technical Indicators (2011)

[Fonte](https://doi.org/10.1287/mnsc.2013.1838) · da report Gemini · no_abstract

Nessuna nota: l'editore non rende pubblico l'abstract, quindi nessuna chiamata.

## Generalized autoregressive conditional heteroskedasticity (1986)

[Fonte](https://doi.org/10.1016/0304-4076(86)90063-1) · da report Gemini · no_abstract

Nessuna nota: l'editore non rende pubblico l'abstract, quindi nessuna chiamata.
