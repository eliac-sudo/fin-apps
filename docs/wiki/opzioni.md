---
title: Opzioni
kind: calcolo
status: modello, non testato come segnale
brief: Black-76, curva SVI e previsione di volatilità HAR: quali contratti costano più o meno di quanto il modello giustifica.
code: bzd/option_models.py#black76, bzd/option_models.py#fit_svi, bzd/option_models.py#har_forecast, bzd/option_models.py#gex_by_strike, bzd/option_lab.py#analyze_chain, bzd/options_report.py#build_report
docs: docs/OPZIONI_MODELLI.md
data: data/raw/opt_cboe_spy, data/raw/opt_deribit_btc
feeds: app, alert-telegram
tab: opzioni
---
## Come funziona
1. Il prezzo a termine si ricava dalla parità put-call, così non servono i dividendi.
2. Dal prezzo medio si ricava la volatilità implicita con Black-76, e la curva SVI la liscia.
3. HAR prevede la volatilità dai rendimenti passati; il valore giusto tiene la forma della curva del mercato ma ne sposta il livello a quello previsto.
4. **Economica** se l'ask è sotto il valore giusto, **cara** se il bid è sopra: una differenza più piccola dello spread non conta.

## Cosa sappiamo
HAR batte GARCH ed EWMA, ma su BTC ed ETH la volatilità implicita prevede meglio. Nessuno ha verificato che comprare le economiche renda. Il messaggio giornaliero sulle opzioni è `bzd/options_report.py#build_report`; la GEX resta fuori perché il suo segno dipende da un'ipotesi.
