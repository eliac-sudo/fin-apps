"""Potenza dei test del 'termometro' (BZD). Seed 42. Solo simulazioni, parametri dichiarati."""
import numpy as np
from scipy import stats
rng = np.random.default_rng(42)
ALPHA = 0.01; Z = stats.norm.ppf(1-ALPHA)

# H1: regressione predittiva rendimento 30g ~ termometro, dati giornalieri dal 2018 (~8,8 anni)
years = 8.8
N_eff = int(years*365/30)  # finestre non sovrapposte
print("N efficace (30g non sovrapposti):", N_eff)
for r2 in (0.01, 0.02, 0.05, 0.10):
    ncp = np.sqrt(N_eff*r2/(1-r2))
    print(f"R2={r2:.2f}  potenza analitica={1-stats.norm.cdf(Z-ncp):.2f}")
print("R2 minimo per potenza 80%:", round((Z+stats.norm.ppf(0.8))**2/N_eff, 3))

# H2: P(drawdown>=20% entro 30g | termometro nel decile alto) vs resto. Fisher esatto unilaterale, MC
def fisher_power(n1, n0, p1, p0, reps=4000):
    a = rng.binomial(n1, p1, reps); b = rng.binomial(n0, p0, reps); rej = 0
    for x, y in zip(a, b):
        _, p = stats.fisher_exact([[x, n1-x], [y, n0-y]], alternative="greater")
        rej += p < ALPHA
    return rej/reps
n1 = max(1, round(N_eff*0.10)); n0 = N_eff-n1
print(f"\nH2: n caldo={n1}, n resto={n0}")
for p0, p1 in [(0.15, 0.15), (0.15, 0.30), (0.15, 0.45), (0.15, 0.60)]:
    print(f"p0={p0} p1={p1}  potenza={fisher_power(n1, n0, p1, p0):.2f}")

# H3 (regola d'uscita) e U0 (entrate sui dip dell'utente): potenza da simulare quando sono fissati
# k1, k2 e quando conosciamo il numero dei trade reali (userFills). Non calcolata qui.

# ================= v0.2: setup d'ingresso (panico, short squeeze) =================
from scipy import stats
rng = np.random.default_rng(43)

# Famiglia: 2 setup x 3 orizzonti (4h, 24h, 72h) = 6 test -> alpha_i = 0.05/6 unilaterale
ALPHA = 0.05/6; Z = stats.norm.ppf(1-ALPHA)
print(f"alpha per test = {ALPHA:.4f}")

# Event study: rendimento netto post-evento r_i ~ N(mu, sigma), eventi raggruppati in cluster
# (piu' asset nello stesso panico: correlazione intra-cluster rho). Effetto in unita' di sigma: d = mu/sigma.
def power(n_events, d, m=3, rho=0.7, reps=20000):
    k = max(2, n_events // m)          # cluster indipendenti (es. 3 asset per panico)
    deff = 1 + (m-1)*rho               # design effect
    n_eff = n_events / deff
    t = rng.standard_normal(reps) + d*np.sqrt(n_eff)
    crit = stats.t.ppf(1-ALPHA, df=k-1)
    return (t > crit).mean(), n_eff
print("\nPotenza (3 asset per evento, rho=0.7 -> n efficace = n/2.4)")
print("eventi | d=0.10 | d=0.20 | d=0.30 | d=0.50 | n_eff")
for n in (30, 60, 120, 240, 480):
    row = [power(n, d) for d in (0.10, 0.20, 0.30, 0.50)]
    print(f"{n:6d} | " + " | ".join(f"{p:.2f}" for p, _ in row) + f" | {row[0][1]:.0f}")

# 'Confidenza' storica: % di casi simili in rialzo dopo 24h, IC 95% di Wilson
def wilson(k, n, z=1.96):
    p = k/n; den = 1+z*z/n; c = (p+z*z/(2*n))/den; h = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return c-h, c+h
print("\nAmpiezza dell'IC di Wilson al 95% per una quota osservata del 60%")
for n in (10, 20, 40, 80, 160):
    lo, hi = wilson(round(0.6*n), n)
    print(f"n={n:4d}: {lo:.2f}-{hi:.2f}")

# Costo del pannello X: 30 risposte x 10 account x 4 aree, 0,005 $ per post letto (pay-per-use, 2026)
reads = 30*10*4; price = 0.005
print(f"\nX: {reads} post letti per giro -> {reads*price:.2f} $/giro; 1 giro/giorno -> {reads*price*30:.0f} $/mese; 4/giorno -> {reads*price*120:.0f} $/mese (tetto 2 mln letture/mese non raggiunto)")
