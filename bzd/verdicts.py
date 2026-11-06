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
    "Z1": ("BYZ (oggi MOM↓)", "ha continuato a scendere più del solito"),
    "Z2": ("SZT (oggi MOM↑)", "ha continuato a salire più del solito"),
    "R1": ("un reset in ipervenduto", None),
    "R2": ("un reset in ipercomprato", None),
    "T1": ("un mercato molto tirato in basso", None),
    "T2": ("un mercato molto tirato in alto", None),
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


def short(rid):
    """A few words for a badge."""
    t = outcome(rid)
    if not t:
        return "non testato"
    if t["outcome"] == "supportata":
        return "test superato"
    return "test: al contrario" if TEXT[rid][1] and t.get("passes_t3") else "test: nessun vantaggio"


def all_lines():
    out = {rid: {"line": line(rid), "short": short(rid), "outcome": (outcome(rid) or {}).get("outcome")} for rid in TEXT}
    out["momentum"] = {"line": momentum_line(), "short": "v4", "outcome": None}
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
    return (f"Su 50 mercati mai usati dal programma (test v4), in 10 sedute dopo MOM↓ il prezzo ha fatto {it(n1['mean'])} peggio di un giorno qualsiasi, "
            f"dopo MOM↑ {it(n2['mean'])} meglio. È un vantaggio relativo e piccolo: tolti i costi, uno short dopo MOM↓ ha perso in media ({it(n1['mean_net'], True)}) "
            f"e un long dopo MOM↑ è rimasto in pari ({it(n2['mean_net'], True)}). Con 3 sedute di fila regge solo MOM↑; la soglia ±70 non aiuta.")