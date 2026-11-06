---
title: App
kind: uscita
status: servizio acceso, solo lettura
brief: L'app per PC sulla porta 8787: legge i dati salvati, non scrive nulla tranne le tue etichette.
code: bzd/app.py#Handler, bzd/app.py#snapshot, bzd/snapshot.py#build, bzd/snapshot.py#part, bzd/app.html#TABS, bzd/wiki.py#pages
feeds: 
---
## Come funziona
1. `bzd/snapshot.py#build` mette insieme ogni parte: mercati e [[tensione]], [[opzioni]], [[sentiment]], [[zone]], alert, [[tecnica]], [[chi-compra]], [[portafogli-hl]]. Se una parte si rompe, `bzd/snapshot.py#part` la segna come mancante e il resto si vede lo stesso.
2. `bzd/app.py#snapshot` tiene in memoria l'ultima lettura per 2 minuti e la rifà in background.
3. La pagina è un file solo, `bzd/app.html`, con una scheda per vista.

## Sicurezza
Ascolta solo su questa macchina. L'unica scrittura sono le [[etichette]], e accetta solo richieste della pagina stessa. Questa scheda mostra codice e documenti, e dei dati solo l'elenco dei file e le prime righe; mai `.env` né file di stato.
