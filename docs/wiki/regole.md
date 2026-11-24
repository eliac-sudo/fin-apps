---
title: Regole dell'utente
kind: verifica
status: decisioni
brief: Le decisioni che il codice deve rispettare: fonti gratuite, ordini solo dal bot Deribit, alert con l'esito del test.
docs: docs/STATO.md#Decisioni dell'utente
feeds: alert-telegram, agenti-alert
---
## Le regole
- Solo fonti gratuite e leggibili, niente API di X.
- Ordini solo dal [[bot-deribit]], sul testnet finché l'utente non decide il conto vero, con la cifra. Solo strategie che hanno retto un test. L'app non ha chiavi. L'indirizzo Hyperliquid dell'utente non va chiesto.
- Nessuna chiamata a pagamento agli agenti senza chiedere.
- Alert su Telegram: insight e direzione («potenziale long») sempre con l'esito del test. Entry, stop e target solo nell'app.
- Gli agenti possono citare e dare un parere, non cambiare numeri o bloccare un alert.
- Un'idea nuova resta «non testata» finché non passa una pre-registrazione su dati nuovi ([[v2]]).
- Paura rossa, euforia verde. App per PC.
