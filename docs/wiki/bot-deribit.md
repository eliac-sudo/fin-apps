---
title: Bot Deribit
kind: uscita
status: sul testnet dal 23 novembre 2026, conto vero spento
brief: Vende put spread con rischio definito, un libro per garanzia (BTC in USDC, BTC in BTC, ETH in ETH), e ripara da solo una put rimasta senza ala.
code: bzd/vol_bot.py#choose_legs, bzd/vol_bot.py#unit_loss, bzd/vol_bot.py#size, bzd/vol_bot.py#exit_reason, bzd/vol_bot.py#uncovered, bzd/vol_bot.py#Bot
docs: docs/BOT_DERIBIT.md, config/vol_bot_v1.json
---
## Come funziona
1. Ogni 7 giorni sceglie la scadenza più vicina a 30 giorni e calcola il delta di ogni put dalla volatilità di mark ([[opzioni]]).
2. Vende la put vicina a 20 delta e compra l'ala vicina a 7 delta. La dimensione è tale che la perdita massima resti entro il 3% del conto, e tutte le aperte entro il 12%. Con garanzia in BTC o ETH la perdita si misura a metà dello strike dell'ala, perché in moneta cresce mentre il prezzo scende.
3. Compra prima l'ala, poi vende; in uscita ricompra prima la put. Esce al 50% del premio o a 7 giorni dalla scadenza.
4. A ogni giro confronta il conto con il registro: una put senza ala si ricompra, ogni altra differenza blocca le entrate. Con un drawdown del 15% si ferma fino a `riprendi`.

## Cosa sappiamo
Lo storico su prezzi veri di Deribit dal 2019 (`docs/BOT_DERIBIT_STORICO.md`): il put spread del bot fa circa zero su BTC e perde su ETH al netto dei costi; nessuna variante a rischio definito guadagna in modo distinguibile dal caso. Il testnet prova solo i meccanismi. Le stesse idee sulla carta sono nelle [[opzioni-in-prova]] (V3 e V4). Nessun segnale direzionale ha retto i test, quindi il bot non fa direzionale.
