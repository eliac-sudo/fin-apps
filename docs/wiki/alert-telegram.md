---
title: Alert su Telegram
kind: uscita
status: servizio acceso
brief: Setup, forti movimenti, reset, tensione e opzioni ogni giorno. La direzione e il test solo dove il test ha retto. Risponde a /piano e ai comandi di lettura (/oggi, /ticker, /alert, /bot, /test).
code: bzd/alerts.py#cycle, bzd/alerts.py#poll_commands, bzd/commands.py#answer, bzd/alerts.py#detect, bzd/alerts.py#build_alert, bzd/alerts.py#format_item, bzd/alerts.py#price_clash, bzd/alerts.py#send_text
data: data/alerts
fresh: live
---
## Come funziona
Il servizio (`.venv/bin/python -u -m bzd.alerts run`) ripete `bzd/alerts.py#cycle` ogni 20 secondi:
1. aggiorna lo [[storico]] alle chiusure delle candele;
2. cerca i [[setup-v1]], i [[movimenti]] e i reset di [[tecnica]];
3. costruisce il messaggio: cosa si è mosso, il prezzo rispetto all'ultimo anno e le conferme presenti («2 su 3»). La direzione («potenziale long») e l'esito di [[test-b3]] compaiono solo se il test ha retto, con l'avviso se il prezzo la contraddice (`bzd/alerts.py#price_clash`). I test non superati restano nella scheda Test dell'app (scelta dell'utente, 24 novembre 2026);
4. chiede il parere degli [[agenti-alert]], se acceso;
5. invia e registra tutto in `data/alerts/log.jsonl`.

Ogni giorno alle 6 UTC parte la [[tensione]], e il messaggio delle [[opzioni]].

## Comandi
`bzd/alerts.py#poll_commands` risponde solo alla chat dell'utente. `/piano` fa il [[piano]]. Gli altri comandi (`bzd/commands.py#answer`) leggono gli stessi dati dell'[[app]] dal suo indirizzo locale, così Telegram e app dicono le stesse cose: `/oggi`, `/ticker MERCATO`, `/alert`, `/bot`, `/test` e `/aiuto`. Sono tutti in sola lettura: pausa e chiusura del [[bot-deribit]] restano nell'app. Un comando sconosciuto riceve l'elenco; il testo libero è ignorato.
