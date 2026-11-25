# Pre-registrazione v9: copiare i trader di Hyperliquid

Scritta il 25 novembre 2026, prima di calcolare qualunque rendimento. Configurazione `config/setups_v9.json`, SHA-256 `26777a85afa74ca6f58e079c102d63c255db9a4f0836c29e268aca6839aa994f`. Codice `bzd/v9.py` (test) e `bzd/copia.py` (copia sulla carta). Il test storico si fa una volta sola: `python -m bzd.v9 storico --confirm` rifiuta di ripartire.

## Perché

L'utente chiede un bot che segua i portafogli Hyperliquid e li copi. La letteratura dice che chi copia raramente guadagna: su eToro e Wikifolio non c'è un vantaggio costante, e su tre piattaforme cripto solo il 44% circa dei leader ha fatto guadagnare chi li copiava (studio di 90 giorni, citato di seconda mano). Su Hyperliquid nessuno l'ha misurato in modo serio. Dal 6 novembre registriamo la classifica, quindi due domande hanno già una risposta nei nostri dati o l'avranno presto. Niente soldi veri: `bzd/copia.py` legge solo l'API pubblica, non ha chiavi e non può mandare ordini.

## Parte 1: chi vinceva il 6 novembre ha continuato a vincere?

Gruppo di partenza: i conti della classifica del 6 novembre 2026 con almeno $100.000 e un giro d'affari mensile tra 0,5 e 100 volte il capitale. È la stessa regola di `bzd/wallets.py`, che esclude i conti fermi e i market maker. Il rendimento dopo è il profitto di sempre nella classifica del 25 novembre meno quello del 6 novembre, diviso il capitale del 6 novembre. Il profitto di Hyperliquid non conta depositi e prelievi.

| ID | Domanda | Test |
|---|---|---|
| P1 | Chi rendeva di più nel mese rende di più dopo? | Spearman tra il rendimento del mese al 6 novembre (profitto del mese / capitale) e il rendimento dopo, a una coda |
| P2 | I 50 con più profitti del mese battono gli altri? | Mann-Whitney a una coda, i 50 contro il resto del gruppo |
| P3 | I 150 con più profitti di sempre battono gli altri? | come P2 |

Holm al 5% sulle tre. **I conti usciti dalla classifica** (sotto i $10.000 o spariti) non hanno un profitto affidabile: l'API `portfolio` dà numeri diversi dalla classifica per i conti grandi (controllato su 7 conti prima del test). Si fa il test due volte, escludendoli e mettendoli all'ultimo posto. Una domanda è supportata solo se lo è in entrambi i modi.

## Parte 2: copiarli sulla carta rende?

Dal 26 novembre 2026 il servizio `bzd-copia` tiene due portafogli finti da $10.000.

- **C** copia i 20 conti del gruppo con più profitti del mese, scegliendo solo quelli con profitto del mese e di sempre positivo.
- **R** copia 20 conti estratti a caso dallo stesso gruppo, con un seme fisso.

Tutti e due si riscelgono ogni lunedì. Ogni 5 minuti si leggono le posizioni dei conti, sulla borsa principale e sul mercato `xyz` di azioni e indici. Il bersaglio è la media delle posizioni dei conti come quota del loro capitale. Se un conto ha più di 3 volte di leva, la sua leva si riduce prima a 3. Si scambia solo quando una posizione è lontana dal bersaglio più dell'1% del capitale. Il prezzo è quello medio letto subito dopo le posizioni, più lo 0,045% di commissione e lo 0,05% di slittamento per lato. Il funding si paga ogni ora al tasso corrente. Se in un passo non si legge almeno il 75% dei conti, si tiene il portafoglio com'è.

| ID | Domanda | Test |
|---|---|---|
| H1 | Copiare i migliori rende più che copiare a caso? | rendimento netto giornaliero di C meno quello di R, media > 0 |
| H2 | Copiare i migliori fa guadagnare? | rendimento netto giornaliero di C, media > 0 |

Si giudica il 25 maggio 2027, con un bootstrap a blocchi di 5 giorni a una coda e Holm al 5% sulle due. Servono almeno 120 giorni registrati, altrimenti l'esito è «non informativa». Con l'emendamento qui sotto ci sono anche due sguardi prima. Si riportano anche BTC tenuto fermo, Sharpe, massimo ribasso, commissioni, funding e numero di scambi. **Se H2 non regge, del bot vero non si parla.** Se regge, il passo dopo è una tua decisione con la cifra.

## Emendamento del 25 novembre 2026: tre sguardi invece di uno

Scritto il 25 novembre alle 13 UTC, prima del primo dato della copia sulla carta, che parte il 26: non si è visto niente. Lo chiede l'utente perché sei mesi sono tanti. Configurazione `config/setups_v9_sequenziale.json`, SHA-256 `237704971fa4d9ceab76366eab52b70c30b5156bfedce5e92ae86975da7a7b00`. La configurazione sopra, la parte storica e le regole della copia non cambiano.

| Sguardo | Quando | Soglia del p, con H1 e H2 entrambe aperte | Soglia se ne resta una |
|---|---|---|---|
| 1 | 60 giorni registrati (circa fine gennaio 2027) | 0,0001 | 0,00069 |
| 2 | 120 giorni registrati (circa fine marzo 2027) | 0,006 | 0,016 |
| 3 | 25 maggio 2027, con almeno 120 giorni | 0,023 | 0,045 |

Le soglie sono quelle di O'Brien-Fleming (spesa dell'alfa di Lan e DeMets, frazioni 1/3, 2/3, 1): molto severe all'inizio, quasi il 5% alla fine, e l'errore complessivo resta al 5%. Holm tra le due ipotesi: finché sono aperte entrambe ognuna ha metà dell'alfa; quando una passa, l'altra si riguarda con l'alfa intero (Maurer e Bretz 2013). Un'ipotesi che passa a uno sguardo è giudicata «supportata» quel giorno e non si riguarda più. Una che non passa resta aperta: «non supportata» si dice solo all'ultimo sguardo. Il bootstrap usa 50.000 ripetizioni invece di 5.000, perché con 5.000 il p più piccolo possibile (0,0002) non scenderebbe mai sotto la prima soglia. La copia continua fino al 25 maggio in ogni caso, e i numeri finali si riportano lo stesso. Gli sguardi fatti restano in `data/v9/sguardi.json`.

In pratica: al primo sguardo passa solo una copia che va fortissimo, al secondo una che va chiaramente bene; una via di mezzo aspetta maggio.

## Limiti, detti prima

- **Parte 1:** sono 19 giorni e un solo momento di mercato. Se i vincenti erano tutti long e il mercato è salito, vincono insieme per la stessa ragione. Dice se la classifica ha memoria, non che copiarla renda.
- **Parte 1, sopravvivenza:** i conti spariti possono essere perdenti (sotto i $10.000) o conti svuotati con un prelievo. Per questo il test si fa due volte.
- **Parte 2, ritardo:** 5 minuti tra le letture, quindi lo scalping non si copia. È voluto: un bot vero via WebSocket arriverebbe in un secondo, ma pagherebbe lo stesso le commissioni a ogni scambio del leader.
- **Parte 2, prezzi:** il prezzo medio sottostima lo slittamento sulle monete piccole; lo 0,05% è un'ipotesi.
- **Parte 2, buchi:** se il servizio si ferma, il rendimento del buco cade sul giorno in cui riparte.

## Conteggi prima del test

Solo il numero di conti, senza rendimenti (`python -m bzd.v9 conta`):

Il gruppo di partenza ha 5.353 conti. Di questi, 4.434 sono nella classifica del 25 novembre e 919 (17%) ne sono usciti. Sono tanti, e per questo il test si fa due volte.

La copia sulla carta non ha conteggi prima: parte il 26 novembre.
