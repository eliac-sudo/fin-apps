---
title: Alert su Telegram
kind: uscita
status: servizio acceso
brief: Setup, forti movimenti, reset, tensione e opzioni ogni giorno, con l'esito del test. Risponde a /piano.
code: bzd/alerts.py#cycle, bzd/alerts.py#detect, bzd/alerts.py#build_alert, bzd/alerts.py#format_item, bzd/alerts.py#price_clash, bzd/alerts.py#send_text
data: data/alerts
fresh: live
---
## Come funziona
Il servizio (`.venv/bin/python -u -m bzd.alerts run`) ripete `bzd/alerts.py#cycle` ogni 20 secondi:
1. aggiorna lo [[storico]] alle chiusure delle candele;
2. cerca i [[setup-v1]], i [[movimenti]] e i reset di [[tecnica]];
3. costruisce il messaggio con l'esito di [[test-b3]], le conferme («0 su 3») e l'avviso «in contrasto» se direzione e prezzo si contraddicono (`bzd/alerts.py#price_clash`);
4. chiede il parere degli [[agenti-alert]], se acceso;
5. invia e registra tutto in `data/alerts/log.jsonl`.

Ogni giorno alle 6 UTC parte la [[tensione]], e il messaggio delle [[opzioni]].
