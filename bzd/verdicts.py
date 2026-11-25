"""What the historical test v3 said about each reading the app shows (config/validation_v3_storico.json, docs/V3_STORICO.md).

One short sentence per reading, for the app and the alerts, in place of "not tested". The numbers come from the frozen results
file, so the sentence can't drift from the test. The wording says what happened, not what to do.
"""
import json
from functools import lru_cache

from .recorder import BASE

RESULTS = BASE / "config" / "validation_v3_storico.json"
PERIOD = "2008–2026"

TEXT = {  # the reading, and what was seen when it went the other way. Prices only: no "buy" or "sell" in a message
    "O1": ("vendere straddle quando le opzioni sono care", None),
    "O2": ("comprare straddle quando le opzioni sono economiche", None),
    "Z1": ("BYZ letto come vecchio nome (oggi «scende forte»)", "ha continuato a scendere più del solito"),
    "Z2": ("SZT letto come vecchio nome (oggi «sale forte»)", "ha continuato a salire più del solito"),
    "R1": ("un reset in ipervenduto", None),
    "R2": ("un reset in ipercomprato", None),
    "T1": ("un mercato ipervenduto (forza sotto 20)", None),
    "T2": ("un mercato ipercomprato (forza sopra 80)", None),
    "S1": ("una fase di paura estrema", None),
    "S2": ("una fase di euforia estrema", None),
    "F1": ("un dip preso dai grossi", None),
    "F2": ("un dip preso dal retail", None),
    "M1": ("un movimento forte", None),
    "L1": ("un test del supporto", None),
    "L2": ("un test della resistenza", None),
}
LONG = {"Z1", "R1", "T1", "S1", "F1", "F2", "L1"}  # the name says up; M1 says "the same way"; the rest say down


@lru_cache(maxsize=1)
def _results(mtime):
    return json.loads(RESULTS.read_text())


def results():
    return _results(RESULTS.stat().st_mtime) if RESULTS.exists() else None


def outcome(rid):
    r = results()
    return (r or {}).get("results", {}).get(rid)


def line(rid):
    """One sentence, e.g. 'Testato 2008–2026: dopo BYZ il prezzo non è salito più che in un giorno qualsiasi; anzi, ...'"""
    t = outcome(rid)
    what, seen = TEXT[rid]
    if not t:
        return "Non ancora testato."
    if t["outcome"] == "supportata":
        if rid == "O2":
            return (f"Testato {PERIOD}: {what} è andato meglio che negli altri giorni ({100 * t['mean']:+.0f} punti di premio), "
                    f"ma tolti i costi resta {100 * t['mean_net']:+.0f}% del premio: vuol dire non venderle, più che comprarle.")
        return f"Testato {PERIOD}: {what} ha superato il test ({100 * t['mean']:+.2f}% rispetto a ingressi casuali)."
    if rid in ("O1", "O2"):
        return f"Testato {PERIOD}: {what} non ha reso più che in un giorno qualsiasi."
    went = "salito" if rid in LONG else "proseguito nello stesso verso" if rid == "M1" else "sceso"
    tail = f"; anzi, {seen}" if seen and t.get("passes_t3") else ""
    return f"Testato {PERIOD}: dopo {what} il prezzo non è {went} più che in un giorno qualsiasi{tail}."


def alert_line(rid):
    """The test sentence for a Telegram message: only when the test held. The user asked (24 Nov 2026) not to see the misses in alerts; they stay in the app's Test tab."""
    t = outcome(rid)
    return line(rid) if t and t["outcome"] == "supportata" else ""


def short(rid):
    """A few words for a badge."""
    t = outcome(rid)
    if not t:
        return "non testato"
    if t["outcome"] == "supportata":
        if t.get("mean_net") is not None and t["mean_net"] <= 0:
            return f"test: meglio del solito, ma netto {100 * t['mean_net']:+.0f}%".replace("-", "−")
        return "test superato"
    return "test: al contrario" if TEXT[rid][1] and t.get("passes_t3") else "test: nessun vantaggio"


UNTESTED = {  # readings the app shows that no test has measured on their own
    "BYZ": "BZD, la capitolazione: regola scelta il 7 novembre 2026 guardando la storia, mai provata su dati nuovi.",
    "RSI": "L'RSI a un estremo da solo non è stato testato. È stato testato dentro il reset (R1, R2) e non ha dato vantaggio.",
    "FLOW": "I livelli di retail e grossi in percentile non sono testati da soli. Comprare il dip con loro (F1, F2) non ha dato vantaggio.",
    "RESET_W": "Il reset su settimanale e mensile (soglia RSI 40/60) non è mai stato testato. Sul giornaliero, con soglia 30/70, non ha dato vantaggio (R1, R2).",
    "LIQ": "Liquidità testata nel v6 (24 novembre 2026): né la liquidità della Fed, né il dollaro, né l'impatto alto hanno dato un vantaggio che regge; stablecoin troppo pochi casi. M2, volumi da soli e book non sono testati.",
    "SENT": "Il sentiment del giorno e della settimana è un conteggio di parole non confrontato con i prezzi. Le fasi estreme (S1, S2) non hanno dato vantaggio.",
}


def momentum_short():
    """A few words for the momentum badge, from v4: a small edge that the costs eat."""
    if not RESULTS_V4.exists():
        return "non testato"
    r = json.loads(RESULTS_V4.read_text())["results"]
    return "test: piccolo, non copre i costi" if r["N1"]["outcome"] == "supportata" and r["N2"]["outcome"] == "supportata" else "test: nessun vantaggio"


def _res(name):
    p = BASE / "config" / name
    return json.loads(p.read_text())["results"] if p.exists() else {}


def _forward(k):
    """The forward state of one v8 hypothesis, or None before the first daily count."""
    try:
        from .v8 import forward_dir
        st = json.loads((forward_dir() / "stato.json").read_text())["state"].get(k)
    except (OSError, ValueError, KeyError):
        return None
    return st


def _fwd_text(k):
    st = _forward(k)
    if not st:
        return "In prova sui dati futuri dal 25 novembre 2026."
    if st.get("judged"):
        return f"Prova sui dati futuri: {st['result']['outcome']} il {st['result']['judged_on'][:10]}."
    return f"In prova sui dati futuri dal 25 novembre 2026: {st['clusters']} episodi su 60."


def pct_art(x):
    """«il 27%», «l'86%», «l'11%»: the article Italian wants before a percentage."""
    n = f"{x:.0f}"
    return ("l'" if n[0] == "8" or n in ("1", "11") else "il ") + n + "%"


def findings():
    """Labels for the readings tested on 24 November 2026 (v6, v7, v8), from the frozen result files."""
    it = lambda x: f"{100 * x:+.2f}".replace(".", ",") + "%"
    pv = lambda x: f"{x:.3f}".replace(".", ",")
    v6, v7, v8 = _res("validation_v6_storico.json"), _res("validation_v7_esame.json"), _res("validation_v8_storico.json")
    out = {}
    def put(key, short, line):
        out[key] = {"short": short, "line": line, "outcome": None}
    if "L1" in v6:
        put("LIQ_NET", "test: nessun vantaggio", f"Test v6: dopo un forte aumento della liquidità netta della Fed, azioni, oro, rame e cripto hanno fatto {it(v6['L1']['mean'])} in 20 sedute rispetto al caso, p {pv(v6['L1']['p'])}: non regge.")
    if "L2" in v6:
        put("LIQ_STABLE", "test: pochi casi", f"Test v6: dopo un forte aumento delle stablecoin le cripto hanno fatto {it(v6['L2']['mean'])} in 20 sedute rispetto al caso, ma su {v6['L2']['clusters']} episodi soli: non informativo.")
    if "L3" in v6:
        put("LIQ_USD", "test: vicino, in prova", f"Test v6: dopo un forte rialzo del dollaro, azioni, oro, rame e cripto hanno fatto {it(-v6['L3']['mean'])} in 20 sedute rispetto al caso, p {pv(v6['L3']['p'])}: vicino alla soglia ma non regge. " + _fwd_text("D1"))
    if "L4" in v6:
        put("LIQ_IMPACT", "test: vicino, in prova", f"Test v6: con l'impatto al 90° percentile, comprare ha reso {it(v6['L4']['mean'])} in 10 sedute rispetto al caso, p {pv(v6['L4']['p'])}: vicino alla soglia ma non regge. Volumi da soli e book non sono testati. " + _fwd_text("A1"))
    if "F1" in v6:
        put("FED_SEP", "test: pochi casi", f"Test v6: dopo un'edizione delle proiezioni con la Fed più dura, S&P, Nasdaq e Treasury hanno fatto {it(-v6['F1']['mean'])} in 20 sedute rispetto al caso, su {v6['F1']['clusters']} edizioni soltanto: non informativo.")
    if "C1" in v7:
        put("POS", "test: vicino, in prova", f"Test v7: comprare con il prezzo nel quinto più basso del suo ultimo anno ha reso più del caso in tutti e tre i periodi; all'esame 2023–2026 {it(v7['C1']['mean'])} in 10 sedute, p {pv(v7['C1']['p'])} contro una soglia di {pv(v7['C1']['holm_threshold'])}: vicino, non ancora dimostrato. " + _fwd_text("P1"))
    if "G1" in v8 and "G2" in v8:
        put("FG", "test: nessun vantaggio", f"Test v8: dopo la paura estrema (≤ 20) le cripto si sono mosse meno del solito in 3 giorni ({it(v8['G1']['mean'])} di ampiezza), non di più. Dopo l'euforia estrema (≥ 80) vendere ha perso ({it(v8['G2']['mean'])} in 20 giorni), su {v8['G2']['clusters']} episodi. Il panico cripto del B3 resta l'unico segnale che regge. " + _fwd_text("G1"))
    v9 = _res("validation_v9_storico.json")
    if "P2" in v9:
        p2 = v9["P2"]
        days = None
        try:
            from .copia import root as copy_dir
            days = json.loads((copy_dir() / "stato.json").read_text()).get("days")
        except (OSError, ValueError):
            pass
        fwd = f"La copia sulla carta è in prova: {days or 0} giorni; si guarda a 60 e 120 giorni con soglie severe, giudizio comunque entro il 25 maggio 2027."
        put("COPY", "classifica: ha memoria; copia: in prova", f"Test v9: dei 50 trader con più profitti del mese al 6 novembre, {pct_art(100 * p2['share_up'])} era ancora in utile il 25 novembre, contro il {100 * p2['share_up_rest']:.0f}% degli altri "
            f"(mediana {it(p2['median'])} contro {it(p2['median_rest'])}). Regge, ma sono 19 giorni e un solo momento di mercato, e non dice ancora che copiarli renda dopo i costi. " + fwd)
    put("LIQ_NEW", "non testato", "Aggiunto il 25 novembre 2026 insieme ad azioni europee e asiatiche, credito e Bund. Non è mai stato confrontato con i prezzi: una regola su questa lettura si potrà giudicare solo sui dati che arrivano da ora.")
    put("LIQ_OTHER", "non testato", "M2, condizioni finanziarie e spread high yield non sono testati: il primo cambia poco, gli altri due non hanno uno storico usabile (ricalcolato all'indietro, o solo 3 anni gratis).")
    return out


def all_lines():
    out = {rid: {"line": line(rid), "short": short(rid), "outcome": (outcome(rid) or {}).get("outcome")} for rid in TEXT}
    out["momentum"] = {"line": momentum_line(), "short": momentum_short(), "outcome": None}
    out.update({k: {"line": v, "short": "non testato", "outcome": None} for k, v in UNTESTED.items()})
    out["RESET"] = {"line": line("R1") + " " + line("R2"), "short": short("R1") if short("R1") == short("R2") else "test: vedi Test", "outcome": None}
    out["OPT"] = {"line": line("O2") + " " + line("O1"), "short": "test: un po' meglio solo le economiche", "outcome": None}
    out.update(findings())
    return out


def unconditional():
    return (results() or {}).get("options_unconditional", {})


RESULTS_V4 = BASE / "config" / "validation_v4_storico.json"


def momentum_line():
    """What v4 said about reading BYZ and SZT the other way round, on 50 markets the program never used."""
    if not RESULTS_V4.exists():
        return ""
    r = json.loads(RESULTS_V4.read_text())["results"]
    n1, n2 = r["N1"], r["N2"]
    if n1["outcome"] != "supportata" or n2["outcome"] != "supportata":
        return "Su 50 mercati mai usati, il test v4 non conferma un effetto momentum."
    it = lambda x, sign=False: (f"{100 * x:+.2f}" if sign else f"{100 * x:.2f}").replace(".", ",") + "%"
    return (f"Su 50 mercati mai usati dal programma (test v4), in 10 sedute dopo «scende forte» il prezzo ha fatto {it(n1['mean'])} peggio di un giorno qualsiasi, "
            f"dopo «sale forte» {it(n2['mean'])} meglio. È un vantaggio relativo e piccolo: tolti i costi, uno short dopo «scende forte» ha perso in media ({it(n1['mean_net'], True)}) "
            f"e un long dopo «sale forte» è rimasto in pari ({it(n2['mean_net'], True)}). Con 3 sedute di fila regge solo «sale forte»; la soglia ±70 non aiuta.")