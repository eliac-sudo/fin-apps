---
title: Previsioni di Fed, BCE, OCSE e mercati
kind: fonte
status: dato pubblico
brief: Cosa si aspettano gli attori importanti su tassi, inflazione, crescita e lavoro, con la data in cui l'hanno detto.
code: bzd/forecasts.py#get_forecasts, bzd/forecasts.py#parse_sep, bzd/forecasts.py#parse_philly, bzd/forecasts.py#parse_ecb_spf, bzd/forecasts.py#parse_oecd, bzd/jobs.py#forecast_jobs
data: data/hist/forecasts, data/raw/fc_kalshi_kxfed, data/raw/fc_polymarket_fed, data/raw/fc_oecd_outlook
feeds: storico, recorder
---
## In breve
Una previsione è quello che qualcuno si aspettava, non quello che è successo. Ogni tabella in `data/hist/forecasts` ha `made` (quando è uscita), `target` (l'anno o il trimestre previsto) e `value`.

- **Fed, proiezioni del FOMC** (`fomc_sep`): mediana e forbice dei «dots» sul tasso, crescita, disoccupazione, inflazione PCE e core, ogni edizione dal 2015, dalle versioni storiche di FRED (ALFRED). La mediana di lungo periodo dal 2012.
- **Fed di Filadelfia, previsori professionali** (`us_spf`): mediane trimestrali dal 1968 su inflazione, PIL, disoccupazione, produzione, case, tassi a 3 mesi e 10 anni, e le attese a 5 e 10 anni su inflazione, crescita e rendimento di azioni e bond. Le colonne 1–6 vanno dal trimestre prima del sondaggio a 4 trimestri dopo; A–D sono le medie annue da quest'anno a tre anni avanti.
- **BCE, previsori professionali** (`ecb_spf`): medie su inflazione, inflazione core, PIL e disoccupazione dell'area euro, ogni trimestre dal 1999, per anno solare e per il lungo periodo.
- **OCSE, Economic Outlook** (`oecd_outlook`): crescita, inflazione, disoccupazione e tassi di USA, area euro, Cina, Giappone, Germania, Italia, Regno Unito, Francia e mondo. Gratis c'è solo l'ultima edizione: le precedenti si conservano da qui in avanti.
- **GDPNow** della Fed di Atlanta: la stima in tempo reale del PIL del trimestre, in `data/hist/macro/GDPNOW.csv.gz`.
- **Mercati di previsione** (Kalshi e Polymarket): le probabilità che il mercato dà a tagli della Fed, inflazione, PIL, posti di lavoro, recessione e livelli di fine anno di S&P, Nasdaq, Bitcoin e petrolio. Non hanno storico gratuito: il recorder li salva ogni 6 ore.
- **Discorsi dei banchieri centrali**: Fed, Banca d'Inghilterra, Banca del Giappone e la raccolta della BIS, come testo in `data/raw/news_*`.

## Come si aggiorna
`python -m bzd.history get forecasts` scarica tutto la prima volta. Poi l'aggiornamento giornaliero degli alert (`refresh_daily`) lo rifà ogni giorno, e il recorder salva una copia di ogni fonte, così resta anche la versione di ogni giorno.

## Quanto fidarsi
- Le date delle edizioni del FOMC vengono dalle versioni di FRED: qualche data può essere una correzione e non una riunione.
- Le serie BCE a orizzonte mobile (per esempio «fra 21 mesi») sono escluse, perché la loro data è quella prevista e non quella del sondaggio.
- Il FMI blocca le richieste da questo server: le sue previsioni (World Economic Outlook) mancano.
- Nessuna di queste previsioni è stata testata come segnale. Per un test si usano solo le righe con `made` prima della data in esame.
