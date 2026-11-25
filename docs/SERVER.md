# Spostare BZD su un server

I servizi girano sul server. Dal 24 novembre 2026 si sviluppa anche sul server stesso, nella copia dell'utente `dev` (vedi «Sviluppare sul server»), perché le ore gratuite di Codespace sono finite. Dal 24 novembre 2026 girano su un Hetzner Cloud CX22 (Ubuntu 26.04, 2 CPU, 4 GB, Falkenstein, `49.13.4.137`). Nel Codespace l'alias SSH è `bzd-server`, con la chiave `~/.ssh/bzd_server` per root e per `codespace`. Sul server l'accesso è solo con chiave e il firewall lascia passare solo SSH. Se il Codespace viene ricostruito la chiave si perde: si rientra dalla console web di Hetzner e se ne aggiunge una nuova.

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
3. Sul server: `sudo systemctl start bzd-recorder bzd-backfill bzd-wallets bzd-copia bzd-alerts bzd-vol-bot bzd-app bzd-backup.timer`
4. Controlla: `systemctl is-active bzd-recorder bzd-backfill bzd-wallets bzd-copia bzd-alerts bzd-vol-bot bzd-app`, poi `/piano` sul bot.
5. Nel Codespace scrivi l'host in `.sul-server` (es. `echo bzd-server > .sul-server`). Da quel momento `start-services.sh` ed `ensure-services.sh` non accendono più niente qui, così i due bot non si contendono i messaggi: aprono solo un tunnel che porta l'app del server sulla porta 8787 del Codespace. Per riportare i servizi nel Codespace prima si fermano sul server, poi si cancella `.sul-server`.

## Sviluppare sul server

L'utente `dev` (sudo senza password, nel gruppo `bzd`) ha una copia del repo con la storia git in `/home/dev/fin-apps`, separata da `/opt/bzd` dove girano i servizi. `data` lì è un collegamento a `/opt/bzd/data`, quindi si lavora sui dati veri: attenzione a quello che ci si scrive. `.env` è una copia di quello dei servizi. `ensure-services.sh` e `start-services.sh` da quella copia non accendono niente, così non partono due bot.

- **Entrare:** dal PC o dal telefono con Tailscale acceso, `ssh dev@bzd`. Tailscale SSH non chiede chiavi; la prima volta può chiedere di confermare l'accesso nel browser.
- **Sessione che resta viva:** `tmux new -A -s claude`, poi `cd ~/fin-apps && claude`. Se la connessione cade, si rientra con lo stesso comando e si ritrova tutto.
- **Prima volta:** `curl -fsSL https://claude.ai/install.sh | bash`, poi `claude` e login con l'account Claude. Per il push: `gh auth login` (GitHub.com, HTTPS, accesso dal browser con il codice) e `gh auth setup-git`.
- **Mandare il codice ai servizi:** `bash scripts/server-update.sh local`.

## Aggiornare

`bash scripts/server-update.sh utente@server` dal Codespace, o `bash scripts/server-update.sh local` dalla copia di sviluppo sul server, manda il codice com'è lì, senza toccare `data/` e `.env`, e riavvia i servizi.

## L'app

Ascolta solo sul server stesso (`127.0.0.1:8787`) e non va esposta su Internet: non ha password, e dalla scheda Bots si comanda il bot Deribit. La si apre in due modi:
- **Da PC e telefono, ovunque:** `https://bzd.tail5e1e60.ts.net`, attraverso Tailscale. Il server è nella rete Tailscale dell'utente (nodo `bzd`, Tailscale SSH acceso) e `tailscale serve --bg 8787` porta l'app solo dentro quella rete, con HTTPS. Per farla usare a qualcun altro si condivide il nodo `bzd` dalla console di Tailscale (Share): la persona installa Tailscale e vede solo il server. Per spegnere l'accesso: `tailscale serve --https=443 off`.
- **Dal Codespace:** il tunnel di `start-services.sh` porta l'app sulla porta 8787.

Tailscale SSH permette anche di entrare nel server dai dispositivi dell'utente se la chiave del Codespace si perde.

## Backup

`scripts/backup.sh` crea un archivio di `data/` in `~/bzd-backups`, tiene gli ultimi 7 e controlla che si rilegga. Sul server parte ogni giorno alle 03:30 UTC, nel Codespace va lanciato a mano. Sullo stesso disco protegge dagli errori, non dalla perdita del server: per quella imposta `BZD_BACKUP_TO=utente@altro:cartella`. `.env` resta fuori dagli archivi: tienine una copia nel gestore di password.

Per ripristinare: ferma i servizi, `tar -xf bzd-data-....tar` in `/opt/bzd`, `chown -R bzd:bzd /opt/bzd/data` e riavvia.
