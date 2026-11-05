# Verifica del report Gemini

Aggiornata al 05/11/2026 con `python -m bzd.research verifica`, che cerca ogni lavoro su OpenAlex e controlla titolo, primo autore, anno e rivista.

**13 lavori su 17 confermati** con tutti e quattro i controlli. Che un lavoro esista non vuol dire che dica ciò che il report gli attribuisce: quello lo controlla il lettore sugli abstract (`NOTE.md`).

| Lavoro come citato | Esito | Trovato su OpenAlex | Citazioni |
|---|---|---|---:|
| Fama, MacBeth (1973), *Risk, Return, and Equilibrium: Empirical Tests*, Journal of Political Economy | confermato | [Risk, Return, and Equilibrium: Empirical Tests](https://doi.org/10.1086/260061), 1973, Journal of Political Economy | 13646 |
| Kyle (1985), *Continuous Auctions and Insider Trading*, Econometrica | confermato | [Continuous Auctions and Insider Trading](https://doi.org/10.2307/1913210), 1985, Econometrica | 9258 |
| Sloan (1996), *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?*, The Accounting Review | confermato | [Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?](https://doi.org/10.2308/tar-9608042309), 1996, The Accounting Review | 2571 |
| Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*, Journal of Accounting Research | confermato | [Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers](https://doi.org/10.2307/2672906), 2000, Journal of Accounting Research | 1208 |
| Almgren, Chriss (2000), *Optimal Execution of Portfolio Transactions*, Journal of Risk | confermato | [Optimal execution of portfolio transactions](https://doi.org/10.21314/jor.2001.041), 2001, The Journal of Risk | 1507 |
| Barberis, Thaler (2003), *A Survey of Behavioral Finance*, Handbook of the Economics of Finance | confermato | [Chapter 18 A survey of behavioral finance](https://doi.org/10.1016/s1574-0102(03)01027-6), 2003, Handbook of the economics of finance | 1568 |
| Baker, Wurgler (2006), *Investor Sentiment and the Cross-Section of Stock Returns*, Journal of Finance | confermato | [Investor Sentiment and the Cross‐Section of Stock Returns](https://doi.org/10.1111/j.1540-6261.2006.00885.x), 2006, The Journal of Finance | 6231 |
| Budish, Cramton, Shim (2015), *The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response*, Quarterly Journal of Economics | esiste, dettagli diversi (non torna: anno) | [The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response](https://doi.org/10.1093/qje/qjv027), 2013, The Quarterly Journal of Economics | 865 |
| Aquilina, Budish, O'Neill (2022), *Quantifying the High-Frequency Trading Arms Race*, Quarterly Journal of Economics — aggiunto da noi, non è nel report | esiste, dettagli diversi (non torna: anno) | [Quantifying the High-Frequency Trading "Arms Race"](https://doi.org/10.1093/qje/qjab032), 2020, The Quarterly Journal of Economics | 189 |
| Fama, French (2015), *A Five-Factor Asset Pricing Model*, Journal of Financial Economics | confermato | [A five-factor asset pricing model](https://doi.org/10.1016/j.jfineco.2014.10.010), 2014, Journal of Financial Economics | 7709 |
| Harvey, Liu, Zhu (2016), *...and the Cross-Section of Expected Returns*, Review of Financial Studies | confermato | [… and the Cross-Section of Expected Returns](https://doi.org/10.1093/rfs/hhv059), 2015, Review of Financial Studies | 2074 |
| Gu, Kelly, Xiu (2020), *Empirical Asset Pricing via Machine Learning*, Review of Financial Studies | confermato | [Empirical Asset Pricing via Machine Learning](https://doi.org/10.1093/rfs/hhaa009), 2020, Review of Financial Studies | 2683 |
| Schwarz, Barber, Huang, Jorion, Odean (2023), *The 'Actual Retail Price' of Equity Trades*, Journal of Finance | esiste, dettagli diversi (non torna: anno) | [The “Actual Retail Price” of Equity Trades](https://doi.org/10.1111/jofi.13467), 2025, The Journal of Finance | 26 |
| Neely, Rapach, Tu, Zhou (2014), *Forecasting the Equity Risk Premium: The Role of Technical Indicators*, Management Science | esiste, dettagli diversi (non torna: anno) | [Forecasting the Equity Risk Premium: The Role of Technical Indicators](https://doi.org/10.1287/mnsc.2013.1838), 2011, Management Science | 1011 |
| Park, Irwin (2007), *What Do We Know About the Profitability of Technical Analysis?*, Journal of Economic Surveys | confermato | [WHAT DO WE KNOW ABOUT THE PROFITABILITY OF TECHNICAL ANALYSIS?](https://doi.org/10.1111/j.1467-6419.2007.00519.x), 2007, Journal of Economic Surveys | 607 |
| Bailey, Borwein, López de Prado, Zhu (2014), *The Probability of Backtest Overfitting*, Journal of Computational Finance | esiste, dettagli diversi (non torna: anno) | [The probability of backtest overfitting](https://doi.org/10.21314/jcf.2016.322), 2016, The Journal of Computational Finance | 144 |
| Bollerslev (1986), *Generalized Autoregressive Conditional Heteroskedasticity*, Journal of Econometrics | confermato | [Generalized autoregressive conditional heteroskedasticity](https://doi.org/10.1016/0304-4076(86)90063-1), 1986, Journal of Econometrics | 22830 |
| Hamilton (1989), *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*, Econometrica | confermato | [A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle](https://doi.org/10.2307/1912559), 1989, Econometrica | 9550 |

## Affermazioni senza un lavoro dietro

- «arrivando a rappresentare oltre il 70% dei volumi azionari statunitensi.» Nel report non ha una fonte.

## Note

- Un anno diverso di solito non è un errore del report: OpenAlex data spesso un lavoro dalla prima versione online o dal working paper, mentre le citazioni usano l'anno del numero stampato. Fa eccezione Schwarz e altri: il report dice Journal of Finance 2023, ma lì è uscito nel 2025, e nel 2023 era un working paper.
- Il dato sui «message data» con le cancellazioni fallite, e la tassa di miliardi l'anno, il report lo attribuisce a Budish, Cramton e Shim (2015). Sembra invece venire da Aquilina, Budish e O'Neill (2022), che abbiamo aggiunto alla verifica: lo confermano o lo smentiscono i loro abstract.
- Il report è quasi tutto su azioni USA: microstruttura, fattori, bilanci. Per BZD contano soprattutto Baker e Wurgler sul sentiment, Harvey, Liu e Zhu e Bailey e López de Prado sui test multipli, e Neely e altri sugli indicatori tecnici. Le parti su retail e posizionamento in BZD vengono dal catalogo, non da qui.
