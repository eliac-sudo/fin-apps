# Bot Deribit: strangle BTC venduto da maker e coperto

Riscritto il 24 novembre 2026. Codice `bzd/vol_bot.py`, regole `config/vol_bot_v2.json`, test `tests/test_vol_bot.py`. Non è consulenza finanziaria.

## Perché questa strategia e nessun'altra

Su 15 varianti provate sui prezzi veri di Deribit dal 2019 (`docs/BOT_DERIBIT_STORICO.md`), questa è l'unica che ha retto: vendere lo strangle 25 delta su BTC da maker e coprire il delta ogni giorno sul perpetuo (DH2m). Risultato: +0,81% del nozionale per entrata, +7,3% l'anno con nozionale pari al conto, calo massimo −12%, nessun anno negativo oltre lo 0,1%. Il t è 1,9 con il funding: non supera una soglia corretta per i confronti multipli.

Il put spread della prima versione (`config/vol_bot_v1.json`) e le opzioni con garanzia in BTC ed ETH sono stati tolti, perché nello storico non guadagnano. Nemmeno i filtri provati (implicita sopra la realizzata, contango, regime calmo) migliorano lo strangle: il bot vende ogni settimana.

## Regole

| | |
|---|---|
| Entrata | ogni lunedì 10–16 UTC: la put e la call fuori dal denaro più vicine a 25 delta, sulla scadenza più vicina a 30 giorni (21–45) |
| Prezzo | ordini post-only al prezzo medio del book, riprezzati quando il book si muove; quello che non si esegue entro le 16 si cancella |
| Dimensione | 25% del conto come nozionale per entrata, al massimo 1× in tutto |
| Copertura | delta di tutte le opzioni aperte coperto sul perpetuo BTC_USDC ogni giorno alle 08:00 UTC e subito dopo un'esecuzione |
| Uscita | a scadenza, regolata da Deribit |

## Sicurezza (non c'è nel backtest)

Lo strangle non ha ali, quindi la coda la gestiscono queste regole:
- **Copertura d'emergenza:** fuori orario, se il delta netto supera 0,2 BTC per BTC di strangle.
- **Margine:** sopra il 50% del conto niente entrate nuove; sopra l'80% il bot chiude tutto da solo, prima che Deribit liquidi.
- **Interruttore:** drawdown del 15% dal massimo, niente entrate nuove finché non si lancia `riprendi`.
- **Controllo del registro:** il conto deve tornare con il registro; ogni differenza blocca le entrate e manda un messaggio.
- **Prezzi:** bid e ask si leggono dal book degli ordini. Sul testnet il ticker era in ritardo e un ordine non si eseguiva.

## Rete e chiavi

- Gira sul **testnet** se non si scrive altro. Per il conto vero servono due righe in `.env`: `DERIBIT_NETWORK=live` e `BZD_BOT_LIVE=ho-capito`.
- Chiavi in `.env`: `DERIBIT_CLIENT_ID` e `DERIBIT_CLIENT_SECRET`. Per il conto vero solo `account: read` e `trade: read_write`, mai prelievi.
- Messaggi su Telegram con `BZD_BOT_TELEGRAM=on`.

```
.venv/bin/python -m bzd.vol_bot stato      # conto, strangle aperti, delta, margine
.venv/bin/python -m bzd.vol_bot once       # un giro solo
.venv/bin/python -m bzd.vol_bot run        # sempre acceso
.venv/bin/python -m bzd.vol_bot pausa      # niente entrate nuove; copertura e sicurezza continuano
.venv/bin/python -m bzd.vol_bot riprendi   # di nuovo entrate, anche dopo l'interruttore
.venv/bin/python -m bzd.vol_bot chiudi     # ricompra tutte le opzioni e chiude la copertura
```

Registro in `data/vol_bot/`: `state.json`, `journal.jsonl` (ordini, coperture, conto ogni giorno), `control.json`. Il registro della prima versione è in `data/vol_bot_v1_archivio/`.

## Prova sui dati futuri

Le regole sono fissate dal 24 novembre 2026. Giudizio non prima del 24 novembre 2027 e di 52 entrate: il risultato settimanale medio deve essere sopra zero, con le entrate sovrapposte contate come cluster di 4. Il confronto è con il backtest (+0,81% del nozionale per entrata).

Il testnet prova i meccanismi e quanto spesso gli ordini da maker vengono eseguiti. Il guadagno lì non conta: i prezzi copiano quelli veri, ma le esecuzioni no.

## Conto minimo per il conto vero

Il lotto minimo è 0,01 BTC per gamba; con il 25% del conto per entrata servono circa 2.500 USDC per una sola entrata minima e circa 10.000 per avere quattro scadenze aperte insieme. Il margine standard di Deribit su uno strangle venduto va controllato sul testnet.

## Prima del conto vero

1. Mesi sul testnet senza differenze né errori, con almeno una copertura d'emergenza e una scadenza.
2. Il server: il Codespace si è fermato più volte, e uno strangle scoperto con il bot spento non ha protezione.
3. La decisione esplicita dell'utente, con la cifra.
