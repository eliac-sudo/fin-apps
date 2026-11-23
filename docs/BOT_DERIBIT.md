# Bot Deribit: put spread venduti su BTC ed ETH

Scritto il 23 novembre 2026. Codice `bzd/vol_bot.py`, regole `config/vol_bot_v1.json`, test `tests/test_vol_bot.py`. Non è consulenza finanziaria.

## Cosa fa

Vende volatilità con rischio definito: ogni settimana vende la put vicina a 20 delta e compra l'ala vicina a 7 delta, sulla scadenza più vicina a 30 giorni (tra 21 e 45).

Un **libro** per garanzia, ognuno con il suo registro, i suoi tetti e il suo interruttore:

| Libro | Opzioni | Garanzia | Acceso | Conto minimo oggi* |
|---|---|---|---|---|
| `btc_usdc` | BTC_USDC-… | USDC | sì | ~3.000 USDC (lotto 0,01 BTC) |
| `btc_btc` | BTC-… | BTC | sì | ~1,4 BTC (lotto 0,1 BTC) |
| `eth_eth` | ETH-… | ETH | no: il premio di ETH dal 2021 è circa zero | ~16 ETH (lotto 1 ETH) |

\*Il conto per cui il lotto più piccolo perde al massimo il 3%, sugli spread che il bot sceglierebbe il 23 novembre 2026 sul mercato vero. Due libri accesi sulla stessa garanzia non sono ammessi, perché i tetti di rischio si sommerebbero.

**Garanzia in cripto:** con BTC come garanzia, la perdita in BTC di uno spread non si ferma all'ala: lo spread paga la larghezza diviso il prezzo, quindi più BTC scende, più BTC costa. Il bot la misura a un prezzo di stress, metà dello strike dell'ala (`coin_stress`): per questo il conto minimo è molto più alto. In dollari conta anche che la garanzia stessa scende con BTC: tenere BTC e vendere put è una scommessa al rialzo più grossa, non solo vendita di volatilità.

**Perché un put spread e non la put nuda:** l'ala comprata è la gestione delle code. La perdita massima si conosce prima di entrare ed è la larghezza meno il premio. Uno stop su un'opzione venduta nuda, in un crollo, si esegue a prezzi pessimi o non si esegue.

## Regole

| | |
|---|---|
| Entrata | una ogni 7 giorni; spread bid/ask di ogni gamba entro il 15% del medio; premio almeno l'8% della larghezza |
| Dimensione | perdita massima per operazione 3% del conto; tutte le aperte insieme al massimo 12%; in multipli del lotto dell'exchange |
| Uscita | al 50% del premio incassato, oppure a 7 giorni dalla scadenza |
| Interruttore | drawdown del 15% dal massimo: niente entrate nuove finché non si lancia `riprendi`; le aperte restano protette dall'ala |
| Ordini | limite al prezzo medio, poi in 5 passi verso il lato peggiore, 20 secondi a passo; quello che non si esegue si cancella |

**Ordine delle gambe:** in entrata compra prima l'ala, poi vende la put; in uscita ricompra prima la put, poi vende l'ala. Il conto non ha mai una put venduta senza ala, nemmeno a metà di un'operazione o dopo un crash del programma.

**Controllo a ogni giro (5 minuti):** confronta le posizioni del conto con il proprio registro.
- Una put venduta senza ala, per esempio aperta a mano, viene ricomprata subito.
- Qualunque altra differenza blocca le entrate e manda un messaggio.
- Gli spread scaduti che il conto non mostra più si segnano come regolati da Deribit.

## Rete e chiavi

- Gira sul **testnet** (test.deribit.com, soldi finti) se non si scrive altro.
- Per il conto vero servono due righe in `.env`: `DERIBIT_NETWORK=live` e `BZD_BOT_LIVE=ho-capito`. Senza la seconda il bot si rifiuta di partire.
- Chiavi in `.env`: `DERIBIT_CLIENT_ID` e `DERIBIT_CLIENT_SECRET`, con permessi di lettura e trading, **niente prelievi**.
- Messaggi su Telegram con `BZD_BOT_TELEGRAM=on`: entrate, uscite, riparazioni, interruttore, errori (lo stesso errore al massimo una volta l'ora).

```
.venv/bin/python -m bzd.vol_bot stato      # conto, spread aperti, rischio in uso
.venv/bin/python -m bzd.vol_bot once       # un giro solo
.venv/bin/python -m bzd.vol_bot run        # sempre acceso
.venv/bin/python -m bzd.vol_bot pausa      # niente entrate nuove; uscite e riparazioni continuano
.venv/bin/python -m bzd.vol_bot riprendi   # di nuovo entrate, anche dopo l'interruttore
.venv/bin/python -m bzd.vol_bot chiudi     # chiude tutto adesso
```

Registro in `data/vol_bot/<libro>/`: `state.json` (spread aperti e chiusi), `journal.jsonl` (ogni ordine). `data/vol_bot/control.json` (pausa e ripresa) vale per tutti i libri.

## Cosa non sappiamo

- **Se rende.** Il premio sulla volatilità di BTC esiste: dal 2021 l'implicita ha superato la realizzata nel 72% dei giorni, di 10 punti di mediana. Per unità di rischio però non è meglio dell'S&P, e su ETH è zero. Il testnet prova i meccanismi, non il guadagno: i suoi prezzi copiano quelli veri ma le esecuzioni sono più facili. Il guadagno netto lo diranno V4 (put spread) e V3 (iron condor) in [prova sulla carta](OPZIONI_IN_PROVA.md).
- **Il margine.** Con il margine standard Deribit potrebbe chiedere per uno spread più della sua perdita massima. Si vede sul testnet.
- **L'accesso dall'Italia** a Deribit per un conto vero va verificato alla registrazione.
- **La piattaforma:** soldi su un exchange cripto sono un rischio a sé, che nessuna ala copre.

## Prima del conto vero

1. Almeno qualche settimana sul testnet senza differenze né errori, compresa una chiusura per profitto, una per scadenza e una riparazione.
2. Il server: il Codespace si è già fermato 16 giorni. Le ali proteggono anche con il bot spento, ma le uscite e l'interruttore no.
3. La decisione esplicita dell'utente, con la cifra.

Il direzionale con approvazione da Telegram non c'è: nessun segnale direzionale ha retto i test al netto dei costi.
