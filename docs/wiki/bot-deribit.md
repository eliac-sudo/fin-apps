---
title: Bot Deribit
kind: uscita
status: sul testnet dal 24 novembre 2026, conto vero spento; giudizio non prima del 24 novembre 2027
brief: Vende ogni lunedì lo strangle 25 delta su BTC in USDC da maker e ne copre il delta sul perpetuo, l'unica variante che ha retto nello storico.
code: bzd/bots.py#view, bzd/bots.py#act, bzd/vol_bot.py#choose_strangle, bzd/vol_bot.py#entry_amount, bzd/vol_bot.py#hedge_trade, bzd/vol_bot.py#maker_price, bzd/vol_bot.py#Bot
docs: docs/BOT_DERIBIT.md, docs/BOT_DERIBIT_STORICO.md, config/vol_bot_v2.json
feeds: app
tab: bots
---
## Come funziona
1. Ogni lunedì tra le 10 e le 16 UTC offre la put e la call più vicine a 25 delta, sulla scadenza vicina a 30 giorni, al prezzo medio del book ([[opzioni]]).
2. Il 25% del conto come nozionale per entrata, al massimo 1× in tutto.
3. Copre il delta sul perpetuo ogni giorno alle 08:00 UTC e dopo ogni esecuzione; tiene fino a scadenza.
4. Sicurezza: copertura d'emergenza fuori orario, niente entrate con margine sopra il 50%, tutto chiuso sopra l'80%, stop dopo un drawdown del 15%, blocco se il conto non torna con il registro.

5. Nella scheda BOTS dell'app ([[app]]) si vede lo stato scritto dal bot a ogni giro, e si mette in pausa, si riprende, si abbassa la dimensione o si chiude tutto in emergenza. L'app scrive solo un file di comandi che il bot legge entro 10 secondi: non ha le chiavi e non manda ordini.

## Cosa sappiamo
Nello storico Deribit dal 2019 (`docs/BOT_DERIBIT_STORICO.md`) questa variante fa +0,81% del nozionale per entrata con il funding, t 1,9: la migliore di 15, ma non significativa dopo i confronti multipli. Put spread, iron condor e garanzia in moneta non guadagnano; i filtri (premio, contango, regime calmo) non aiutano. Ora è in prova sui dati futuri come le [[opzioni-in-prova]].
