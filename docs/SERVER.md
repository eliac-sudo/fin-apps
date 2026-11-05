# Spostare BZD su un server

Lo sviluppo resta nel Codespace, i servizi girano sul server. Il kit è pronto ma **non è stato provato su un server vero**: la prima installazione va controllata passo per passo.

## Cosa ti serve

Un server Ubuntu 22.04 o 24.04 con accesso SSH e `sudo` senza password, almeno 2 GB di RAM e 40 GB di disco.

## Primo avvio

Dal Codespace, con `utente@server` al posto dell'indirizzo:

```
rsync -az --exclude data --exclude .venv --exclude .env --exclude .git ./ utente@server:bzd-install/
ssh utente@server 'sudo bash bzd-install/scripts/server-install.sh'
bash scripts/server-move-data.sh utente@server     # prima copia, a servizi accesi
```

Poi il passaggio, che deve lasciare **il bot in un posto solo**:

1. Nel Codespace ferma i servizi: alert e bot per primi.
2. `bash scripts/server-move-data.sh utente@server` di nuovo, per l'ultima parte dei dati.
3. Sul server: `sudo systemctl start bzd-recorder bzd-backfill bzd-alerts bzd-app bzd-backup.timer`
4. Controlla: `systemctl is-active bzd-recorder bzd-backfill bzd-alerts bzd-app`, poi `/piano` sul bot.
5. Togli `postStartCommand` da `.devcontainer/devcontainer.json`, altrimenti alla riaccensione del Codespace due bot si contendono i messaggi.

## Aggiornare

`bash scripts/server-update.sh utente@server` manda il codice com'è nel Codespace, senza toccare `data/` e `.env`, e riavvia i servizi.

## L'app

Ascolta solo sul server stesso (`127.0.0.1:8787`), e non va esposta su Internet perché non ha password. Per aprirla: `ssh -L 8787:127.0.0.1:8787 utente@server`, poi `http://127.0.0.1:8787`.

## Backup

`scripts/backup.sh` crea un archivio di `data/` in `~/bzd-backups`, tiene gli ultimi 7 e controlla che si rilegga. Sul server parte ogni giorno alle 03:30 UTC, nel Codespace va lanciato a mano. Sullo stesso disco protegge dagli errori, non dalla perdita del server: per quella imposta `BZD_BACKUP_TO=utente@altro:cartella`. `.env` resta fuori dagli archivi: tienine una copia nel gestore di password.

Per ripristinare: ferma i servizi, `tar -xf bzd-data-....tar` in `/opt/bzd`, `chown -R bzd:bzd /opt/bzd/data` e riavvia.
