---
title: Alert su Telegram
kind: uscita
status: servizio acceso
brief: Setup, forti movimenti, reset, tensione e opzioni ogni giorno. La direzione e il test solo dove il test ha retto. Risponde a /piano e ai comandi di lettura (/oggi, /ticker, /alert, /bot, /test).
code: bzd/tg.py#num, bzd/tg.py#app_link, bzd/alerts.py#cycle, bzd/alerts.py#poll_commands, bzd/commands.py#answer, bzd/alerts.py#detect, bzd/alerts.py#build_alert, bzd/alerts.py#format_item, bzd/alerts.py#price_clash, bzd/alerts.py#send_text
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

## Come appaiono
Dal 25 novembre 2026 i messaggi sono brevi e visivi (scelta dell'utente: «sembrano dei muri di testo»). `bzd/tg.py` dà a tutti lo stesso aspetto: numeri all'italiana, frecce del trend, barre ▰▱ per la forza, pallini ●○ per la paura delle opzioni, livelli come «🧱 supporto │ resistenza», e in fondo un link alla scheda dell'app (`bzd/tg.py#app_link`, indirizzo in `BZD_PUBLIC_URL`). Un mercato occupa due o tre righe. Le opzioni non stanno più dentro gli alert ma solo nel report del giorno. Il parere degli [[agenti-alert]] è ridotto a lettura, umore, una frase e un punto per lato. Dopo ogni giro di [[aisetups]] arriva anche il suo messaggio.

## Comandi
`bzd/alerts.py#poll_commands` risponde solo alla chat dell'utente. `/piano` fa il [[piano]]. Gli altri comandi (`bzd/commands.py#answer`) leggono gli stessi dati dell'[[app]] dal suo indirizzo locale, così Telegram e app dicono le stesse cose: `/oggi`, `/ticker MERCATO`, `/alert`, `/bot`, `/test` e `/aiuto`. Sono tutti in sola lettura: pausa e chiusura del [[bot-deribit]] restano nell'app. Un comando sconosciuto riceve l'elenco; il testo libero è ignorato.
