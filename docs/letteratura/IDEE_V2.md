# Bozze di setup v2

Scritte dal supervisore (`python -m bzd.research supervisore`) a partire da `NOTE.md`, dopo aver ricontrollato ogni nota sul suo abstract. **Nessuna è testata.** Non entrano negli alert né nei setup congelati: ognuna diventa un setup solo se passa una pre-registrazione v2 su dati raccolti dopo la sua data.

Generate il 2026-11-24 con claude-opus-5-5.

## Revisione delle note

Il supervisore ha riletto 40 note sul loro abstract: 24 reggono.
- **cat-beyondpurehypenewssentimentanditsroleint**, forzata: L'abstract mostra solo un'associazione, non che il sentiment anticipi il posizionamento. Inoltre BZD non ha una variabile di sentiment delle notizie, quindi la pertinenza «alta» è eccessiva. Abstract: «The findings reveal that news sentiment is significantly associated with futures price movements and market positioning by professional investors.».
- **cat-anassetpricingmodelwithlossaversionandit**, forzata: Il modello riproduce l'asimmetria dei rendimenti di mercato. Non dice nulla su indicatori di sentiment o di posizionamento del retail che anticipino rendimenti. Abstract: «In particular, for the first time our model enables us to match the following empirically observed properties: conditional heavy tails of returns, gains/loss asymmetry, volume power-law and long memory and volume-volatility relations.».
- **cat-analysisofcryptocurrencyasafinancialinst**, forzata: L'abstract tratta rischio e diversificazione di portafoglio. Non studia se il rischio di coda preveda rendimenti futuri. Abstract: «Tangency portfolio analysis shows that adding cryptocurrencies to traditional assets substantially improves risk-adjusted returns».
- **cat-arefrenchindividualinvestorsreluctanttor**, forzata: Il risultato nasce da conti individuali di un broker. BZD non ha prezzi di ingresso né chiusure per conto, quindi l'idea non è misurabile con i suoi dati. Abstract: «We analyze the presence of the disposition effect for 90 244 French individual investors based on a large brokerage account database between 1999 and 2006.».
- **cat-behavioralbiasesinpanicsellingexploringt**, forzata: Il lavoro misura l'effetto del framing con un sondaggio. Non osserva un eccesso di vendite nei dati di mercato, che è ciò che l'idea presuppone. Abstract: «Utilizing data from a collaborative survey, we examine Japanese investors’ behavior during the COVID-19 market crisis.».
- **cat-behavioralfinancelossaversionmarketanoma**, forzata: È un saggio concettuale senza dati. Non sostiene alcun legame misurabile tra perdite recenti, posizionamento e movimenti successivi. Abstract: «This paper delves into the intricate world of investor psychology to shed light on the processes that underlie financial decision-making.».
- **cat-beliefoverreactionandstockmarketpuzzles**, forzata: Il lavoro riguarda le attese di crescita degli utili di lungo periodo dell'S&P 500. Non riguarda il posizionamento retail né orizzonti da un giorno a un mese. Abstract: «We construct an index of long-term expected earnings growth for S&P 500 firms».
- **cat-blockbusterorbustsilverscreeneffectandst**, forzata: L'effetto riguarda i mercati azionari. L'estensione al forex e a un indice di ricerche sull'intrattenimento non è sostenuta dall'abstract. Abstract: «This study introduces a novel mood metric—blockbuster movie releases—and investigates its correlation with stock market dynamics.».
- **cat-cognitivebiasesandportfoliodecisionsaneu**, forzata: Il lavoro usa solo letteratura e studi fMRI, senza dati di mercato. L'idea di posizionamento estremo prima delle inversioni non ha base nell'abstract. Anche il giudizio sulla rivista non viene dall'abstract. Abstract: «the research incorporates the secondary data in the literature of behavioural finance and insights provided by neuroimaging research».
- **cat-corporateinsidersexploitationofinvestors**, forzata: Il risultato riguarda gli insider di singole aziende. Non dice che massimi e minimi a 52 settimane predicano rendimenti su cripto, materie prime o forex. Abstract: «We find that insiders adopt dissimulation strategies to conceal their informational advantage and trade profitably when their firms’ stock prices reach 52‐week highs and lows».
- **cat-detectingregimeshiftsthecausesofunderand**, forzata: Sono esperimenti di laboratorio su stime di probabilità. Non mostrano che il posizionamento di mercato sovrareagisca in base al regime di volatilità. Abstract: «We conduct three experiments to test how effective individuals are at detecting such regime shifts.».
- **cat-dispositioneffectonethereumevidencefromp**, da correggere: La nota presenta l'asimmetria tra guadagni e perdite come un risultato. L'abstract descrive solo ciò che il disegno di studio vuole identificare e non riporta esiti. Abstract: «Findings: The framework is designed to identify three mechanisms: asymmetric realization of gains over losses, stronger gain realization under high volatility, and attenuation around major protocol-upgrade events.».
- **cat-doshortexposureandsystematicriskexposure**, da correggere: La nota scrive «framing ampio», ma l'abstract dice framing ristretto (narrow). Abstract: «We show that short positions exhibit a weaker disposition effect than long positions under narrow framing».
- **cat-emotionalinstabilityandfinancialdecision**, forzata: È un sondaggio sulla personalità. Non dice nulla su uscite del retail che precedano ulteriori ribassi dei prezzi. Abstract: «The data for this research were derived from a comprehensive survey titled Survey on Life and Money».
- **cat-faultyanchorsindividualinvestororderinte**, forzata: L'idea ipotizza rendimenti negativi dopo il massimo a 52 settimane. L'abstract parla invece di rendimenti in stile momentum, che vanno a favore delle istituzioni controparti. Abstract: «This study uncovers how household investors intensify the effect of the 52-week high (52WH): increased volume and momentum-like returns at the 52WH price.».
- **cat-gamblingpreferencesoptionsmarketsandvola**, forzata: Il segnale è il rapporto tra volume call e volume totale di opzioni sulle azioni. BZD non ha questo dato, quindi la pertinenza dichiarata va oltre. Abstract: «Focusing on the options market, we find that the ratio of call option volume relative to total option volume is greatest for stocks with return distributions that resemble lotteries.».

## 1. Paura cripto e ampiezza dei movimenti successivi

Quando il Fear & Greed cripto è in zona di paura estrema, nei giorni successivi i movimenti sono più ampi, in valore assoluto, rispetto a ingressi casuali. Si misura l'ampiezza, non il verso. B3 aveva misurato il verso del rendimento dopo il panico cripto (+0,75% sulle 24 ore); qui cambia la domanda: si guarda la volatilità realizzata, come suggerisce la nota sui FEARS.

- **Da:** cat-essaysincryptocurrency, cat-behavioraldriversofcryptocurrencymarkets
- **Mercati:** crypto
- **Regola:** fear_greed <= 20
- **Orizzonte:** 3 giorni
- **Confronto:** Ingressi casuali sullo stesso mercato cripto, nello stesso periodo e con lo stesso orizzonte. Si confronta la media dei movimento_z assoluti sommati nei giorni successivi.
- **La smentisce:** L'idea è smentita se l'ampiezza media dei movimenti dopo il segnale non supera quella degli ingressi casuali, oppure se la differenza sparisce quando si controlla per l'ampiezza dei movimenti dei giorni precedenti.
- **Dati che mancano:** Misura di volatilità realizzata in avanti ricavata dai prezzi, definita prima del test; Indice di paura FEARS usato nel lavoro originale, non disponibile: si usa il Fear & Greed come sostituto
- **Rischi:** La paura estrema arriva spesso dopo giorni già volatili: l'effetto potrebbe essere solo persistenza della volatilità; Pochi episodi indipendenti, eventi raggruppati nel tempo; Sovrapposizione con il segnale di panico già testato in B3

## 2. Euforia cripto e rendimento a quattro settimane

Un sentiment molto euforico sulle cripto si accompagna a errori di prezzo che poi si correggono. Il rendimento fino a quattro settimane dopo è più basso di quello di ingressi casuali, come la nota GIF trova per le azioni. B3 aveva testato il surriscaldamento solo sulle 24 ore senza esito; qui cambia l'orizzonte, che diventa mensile.

- **Da:** cat-giffluenceavisualapproachtoinvestorsenti, cat-behavioraldriversofcryptocurrencymarkets, cat-expectationsofreturnsandexpectedreturns
- **Mercati:** crypto
- **Regola:** fear_greed >= 80
- **Orizzonte:** 4 settimane
- **Confronto:** Ingressi casuali sullo stesso mercato cripto, nello stesso periodo e con lo stesso orizzonte. Il confronto riguarda il rendimento medio, con eventi raggruppati per non contare più volte la stessa fase euforica.
- **La smentisce:** L'idea è smentita se il rendimento medio dopo il segnale non è più basso di quello degli ingressi casuali, oppure se la differenza ha segno opposto nella metà dei casi più recente.
- **Dati che mancano:** Indice GIFsentiment del lavoro, non disponibile: si usa il Fear & Greed come sostituto; Regola per raggruppare i giorni consecutivi sopra soglia in un solo evento
- **Rischi:** Il risultato originale riguarda le azioni: il trasferimento alle cripto non è garantito; Le fasi euforiche coincidono con trend forti, che il tag momentum di BZD vede continuare; Pochi episodi indipendenti su un orizzonte lungo
