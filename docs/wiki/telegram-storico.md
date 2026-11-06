---
title: Storico Telegram
kind: raccolta
status: servizio acceso
brief: Scarica all'indietro i canali Telegram pubblici, dal più recente al più vecchio, senza login.
code: bzd/telegram.py#backfill, bzd/telegram.py#parse_page, bzd/telegram.py#parse_liquidation
data: data/telegram
feeds: testi
---
## In breve
Legge la versione web pubblica dei canali (`t.me/s/<canale>`). Ogni messaggio tiene il suo numero, quindi si ricontrolla a mano su `https://t.me/<canale>/<numero>`. Dai canali di liquidazioni estrae importi e lato (`bzd/telegram.py#parse_liquidation`).
