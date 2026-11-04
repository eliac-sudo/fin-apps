# B3 — risultati del test pre-registrato (v1)

Configurazione `1bde3cb89104`, eventi `9fe19d37d397`. Regole in `docs/PREREGISTRAZIONE_v1.md`, codice in `bzd/b3.py`. Eseguito una sola volta. Non è consulenza finanziaria.

## Test primari

Eccesso = rendimento netto rispetto a ingressi casuali su stesso mercato e stesso anno. Per il surriscaldamento ci si aspetta un eccesso negativo.

| Mercato | Setup | Episodi | Eccesso medio | IC 90% | d | p | Potenza d=0,3 | Rend. netto medio | Esito |
|---|---|---:|---:|---|---:|---:|---:|---:|---|
| crypto | Panico | 131 | +0.75% | +0.20% … +1.32% | +0.19 | 0.016 | 90% | +0.75% | **supportata** |
| crypto | Squeeze | 221 | -0.01% | -0.44% … +0.45% | -0.00 | 0.512 | 99% | -0.45% | **non supportata** |
| crypto | Surriscaldamento | 73 | -1.03% | -1.92% … -0.21% | -0.23 | 0.027 | 65% | -1.22% | **non supportata** |
| equities | Panico | 44 | +0.02% | -0.80% … +0.78% | +0.01 | 0.486 | 42% | +0.43% | **non informativa** |
| equities | Squeeze | 55 | -0.17% | -0.65% … +0.33% | -0.08 | 0.712 | 52% | -0.02% | **non supportata** |
| equities | Surriscaldamento | 20 | -0.65% | -1.46% … +0.14% | -0.28 | 0.112 | 19% | -0.54% | **non informativa** |
| bonds | Panico | 40 | -0.12% | -0.42% … +0.15% | -0.11 | 0.754 | 39% | -0.25% | **non informativa** |
| bonds | Squeeze | 64 | +0.03% | -0.11% … +0.16% | +0.04 | 0.364 | 59% | -0.15% | **non supportata** |
| bonds | Surriscaldamento | 28 | -0.10% | -0.38% … +0.19% | -0.11 | 0.278 | 27% | -0.14% | **non informativa** |
| commodities | Panico | 96 | -0.68% | -1.47% … +0.20% | -0.13 | 0.905 | 78% | -0.29% | **non supportata** |
| commodities | Squeeze | 226 | +0.39% | -0.04% … +0.82% | +0.10 | 0.069 | 99% | +0.13% | **non supportata** |
| commodities | Surriscaldamento | 120 | -0.79% | -1.55% … -0.05% | -0.16 | 0.043 | 87% | -0.52% | **non supportata** |
| fx | Panico | 86 | +0.01% | -0.19% … +0.22% | +0.01 | 0.459 | 73% | -0.09% | **non supportata** |
| fx | Squeeze | 182 | +0.05% | -0.07% … +0.15% | +0.05 | 0.242 | 97% | -0.12% | **non supportata** |
| fx | Surriscaldamento | 73 | -0.24% | -0.64% … +0.06% | -0.13 | 0.143 | 65% | -0.24% | **non supportata** |

★ = regge anche alla soglia globale 0.0033. Soglia per test 0.0167.

## Altri orizzonti (solo descrittivi)

- crypto/panic: 1 barre +0.04%, 18 barre +0.56%; punteggio ed effetto, Spearman +0.01
- crypto/squeeze: 1 barre -0.05%, 18 barre +0.37%; punteggio ed effetto, Spearman +0.17
- crypto/overheating: 1 barre +0.01%, 18 barre -0.38%; punteggio ed effetto, Spearman +0.02
- equities/panic: 1 barre -0.29%, 10 barre -0.46%, 20 barre -0.77%; punteggio ed effetto, Spearman +0.03
- equities/squeeze: 1 barre -0.03%, 10 barre +0.38%, 20 barre -0.32%; punteggio ed effetto, Spearman -0.13
- equities/overheating: 1 barre -0.06%, 10 barre -1.43%, 20 barre -2.42%; punteggio ed effetto, Spearman +0.09
- bonds/panic: 1 barre -0.08%, 10 barre -0.15%, 20 barre -0.23%; punteggio ed effetto, Spearman -0.19
- bonds/squeeze: 1 barre -0.02%, 10 barre +0.01%, 20 barre -0.08%; punteggio ed effetto, Spearman -0.16
- bonds/overheating: 1 barre -0.08%, 10 barre -0.27%, 20 barre -0.43%; punteggio ed effetto, Spearman -0.01
- commodities/panic: 1 barre -0.19%, 10 barre -1.68%, 20 barre -2.72%; punteggio ed effetto, Spearman +0.02
- commodities/squeeze: 1 barre +0.09%, 10 barre +0.82%, 20 barre +1.00%; punteggio ed effetto, Spearman -0.07
- commodities/overheating: 1 barre -0.63%, 10 barre -1.13%, 20 barre +0.00%; punteggio ed effetto, Spearman +0.03
- fx/panic: 1 barre -0.00%, 10 barre -0.13%, 20 barre -0.14%; punteggio ed effetto, Spearman -0.21
- fx/squeeze: 1 barre -0.00%, 10 barre +0.15%, 20 barre +0.41%; punteggio ed effetto, Spearman -0.01
- fx/overheating: 1 barre +0.00%, 10 barre -0.50%, 20 barre -0.20%; punteggio ed effetto, Spearman -0.16

## Uscite (test H3 sulle regole selezionate, in R)

- crypto/panic, descrittivo: stop + 3R -0.02R (peggior 10% -1.11R), tieni +0.31R (peggior 10% -3.88R)
- crypto/squeeze, descrittivo: stop + 3R -0.12R (peggior 10% -1.07R), tieni -0.06R (peggior 10% -1.85R)
- equities/panic, descrittivo: stop + 3R -0.09R (peggior 10% -1.10R), tieni +0.62R (peggior 10% -2.80R)
- equities/squeeze, descrittivo: stop + 3R +0.15R (peggior 10% -1.05R), tieni +0.22R (peggior 10% -0.68R)
- bonds/panic, descrittivo: stop + 3R -1.08R (peggior 10% -2.13R), tieni -1.43R (peggior 10% -3.83R)
- bonds/squeeze: `stop_half_time` -0.42R contro tieni -0.40R, p 0.6164321444346197, esito **non supportata**
- bonds/squeeze, descrittivo: stop + 3R -0.43R (peggior 10% -1.42R), tieni -0.40R (peggior 10% -1.44R)
- commodities/panic, descrittivo: stop + 3R -0.16R (peggior 10% -1.10R), tieni -0.23R (peggior 10% -2.24R)
- commodities/squeeze: `target_3R` +0.09R contro tieni +0.05R, p 0.23437799322238287, esito **non supportata**
- commodities/squeeze, descrittivo: stop + 3R +0.09R (peggior 10% -1.04R), tieni +0.05R (peggior 10% -1.10R)
- fx/panic: `thirds_then_trail` -0.20R contro tieni -0.26R, p 0.3914290075211359, esito **non supportata**
- fx/panic, descrittivo: stop + 3R -0.35R (peggior 10% -1.26R), tieni -0.26R (peggior 10% -2.53R)
- fx/squeeze, descrittivo: stop + 3R -0.05R (peggior 10% -1.15R), tieni -0.09R (peggior 10% -1.66R)
