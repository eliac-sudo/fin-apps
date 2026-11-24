# Spostare BZD su un server

Lo sviluppo resta nel Codespace, i servizi girano sul server. Dal 24 novembre 2026 girano su un Hetzner Cloud CX22 (Ubuntu 26.04, 2 CPU, 4 GB, Falkenstein, `49.13.4.137`). Nel Codespace l'alias SSH è `bzd-server`, con la chiave `~/.ssh/bzd_server` per root e per `codespace`. Sul server l'accesso è solo con chiave e il firewall lascia passare solo SSH. Se il Codespace viene ricostruito la chiave si perde: si rientra dalla console web di Hetzner e se ne aggiunge una nuova.

## Cosa ti serve

Un server Ubuntu (provato su 26.04) con accesso SSH e `sudo` senza password, almeno 2 GB di RAM e 40 GB di disco.

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
3. Sul server: `sudo systemctl start bzd-recorder bzd-backfill bzd-wallets bzd-alerts bzd-vol-bot bzd-app bzd-backup.timer`
4. Controlla: `systemctl is-active bzd-recorder bzd-backfill bzd-wallets bzd-alerts bzd-vol-bot bzd-app`, poi `/piano` sul bot.
5. Nel Codespace scrivi l'host in `.sul-server` (es. `echo bzd-server > .sul-server`). Da quel momento `start-services.sh` ed `ensure-services.sh` non accendono più niente qui, così i due bot non si contendono i messaggi: aprono solo un tunnel che porta l'app del server sulla porta 8787 del Codespace. Per riportare i servizi nel Codespace prima si fermano sul server, poi si cancella `.sul-server`.

## Aggiornare

`bash scripts/server-update.sh utente@server` manda il codice com'è nel Codespace, senza toccare `data/` e `.env`, e riavvia i servizi.

## L'app

Ascolta solo sul server stesso (`127.0.0.1:8787`), e non va esposta su Internet perché non ha password. Per aprirla: `ssh -L 8787:127.0.0.1:8787 utente@server`, poi `http://127.0.0.1:8787`.

## Backup

`scripts/backup.sh` crea un archivio di `data/` in `~/bzd-backups`, tiene gli ultimi 7 e controlla che si rilegga. Sul server parte ogni giorno alle 03:30 UTC, nel Codespace va lanciato a mano. Sullo stesso disco protegge dagli errori, non dalla perdita del server: per quella imposta `BZD_BACKUP_TO=utente@altro:cartella`. `.env` resta fuori dagli archivi: tienine una copia nel gestore di password.

Per ripristinare: ferma i servizi, `tar -xf bzd-data-....tar` in `/opt/bzd`, `chown -R bzd:bzd /opt/bzd/data` e riavvia.
