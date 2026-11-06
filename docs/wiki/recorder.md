---
title: Recorder
kind: raccolta
status: servizio acceso
brief: 150 lavori di raccolta che salvano ogni risposta grezza con data e impronta, prima che il dato sparisca.
code: bzd/recorder.py#Archive, bzd/recorder.py#run_one, bzd/recorder.py#cmd_run, bzd/jobs.py#all_jobs
data: data/raw, data/manifest
feeds: testi, movimenti, opzioni, tensione
fresh: live
---
## In breve
Il recorder gira sempre (`python3 -u -m bzd.recorder run`). La priorità è il dato che non ha storico gratuito: se non lo salviamo adesso è perso.

## Come funziona
1. `bzd/jobs.py#all_jobs` elenca cosa scaricare e ogni quanto, con una pausa minima per sito.
2. `bzd/recorder.py#run_one` scarica, toglie eventuali chiavi dall'indirizzo (`bzd/recorder.py#redact`) e controlla che la risposta sia valida.
3. `bzd/recorder.py#Archive` salva la risposta in `data/raw/<lavoro>/` e una riga con l'impronta SHA in `data/manifest/<giorno>.jsonl`, così ogni numero si può far risalire al file da cui viene.

## Controllo
`python -m bzd.recorder status` dice quali lavori sono in ritardo. Se il Codespace si riaccende i servizi possono restare fermi: `bash scripts/ensure-services.sh` come utente `codespace`.
