# Il motore di BZD

Questo wiki spiega come lavora il programma, dal dato grezzo al messaggio su Telegram. Ogni pagina è una parte del motore e cita il codice, la cartella dati e il documento da cui viene: clicca una citazione per aprire il file alla riga giusta.

Si legge da sinistra a destra: le **fonti** pubbliche, la **raccolta** che le salva in `data/`, i **calcoli** che ne ricavano letture, le **verifiche** che dicono se una lettura ha mai funzionato, e le **uscite** che vedi, cioè l'app e gli alert.

Segue lo schema del «LLM Wiki» di Karpathy: le fonti grezze non si toccano (codice, `data/`, `docs/`), il wiki è una cartella di pagine collegate (`docs/wiki/`), il registro tiene la storia e un controllo automatico (`python -m bzd.wiki lint`) verifica che ogni citazione porti ancora a qualcosa di vero. Le pagine le scrive chi lavora sul codice, mai un modello mentre l'app gira.
