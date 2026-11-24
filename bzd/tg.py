"""How Telegram messages look: short lines, Italian numbers, small bars and arrows, and a link to the app for the detail.

Every alert uses these, so they all read the same way at a glance.
"""
import html, os

TREND = {"rialzo": "↗", "ribasso": "↘", "laterale": "→"}
MINUS = "−"


def num(x):
    """A price the Italian way, with as many decimals as its size needs: 59.694 · 70,16 · 1,4339 · 0,08213."""
    if x is None:
        return "–"
    a = abs(x)
    d = 0 if a >= 1000 else 2 if a >= 10 else 4 if a >= .1 else 6
    s = f"{a:,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return (MINUS if x < 0 else "") + s


def pct(x, d=1, plus=True):
    """+2,3% · −10,1%. Rounded to 0 decimals above 10 when d is None."""
    if x is None:
        return "–"
    if d is None:
        d = 0 if abs(x) >= 10 else 1
    if round(abs(x), d) == 0:
        return "0%"
    s = f"{abs(x):.{d}f}".replace(".", ",")
    return (MINUS if x < 0 else "+" if plus and x > 0 else "") + s + "%"


def bar(v, n=10):
    """▰▰▰▱▱▱▱▱▱▱ for a value from 0 to 100."""
    k = max(0, min(n, round((v or 0) / 100 * n)))
    return "▰" * k + "▱" * (n - k)


def dots(v, n=5):
    """●●●○○ for a percentile from 0 to 100."""
    k = max(1, min(n, int((v or 0) // (100 / n)) + 1))
    return "●" * k + "○" * (n - k)


def arrow(trend):
    return TREND.get(trend, "·")


def esc(s):
    return html.escape(html.unescape(str(s)), quote=False)  # some labels are stored already escaped (S&amp;P)


def app_link(hash_="", text="Apri nell'app"):
    """A link to the app's tab when the app's address is known (BZD_PUBLIC_URL), so the detail is one tap away. Plain text otherwise."""
    url = os.environ.get("BZD_PUBLIC_URL", "").rstrip("/")
    if not url:
        return f"<i>{text}</i>"
    return f'📱 <a href="{html.escape(url + ("/#" + hash_ if hash_ else "/"), quote=True)}">{text}</a>'


def levels(ctx):
    """🧱 67,29 −4% │ 75,25 +7%: the nearest weekly support and resistance, from technicals.levels_of."""
    if not ctx or (ctx.get("sup") is None and ctx.get("res") is None):
        return ""
    sup = f"{num(ctx['sup'][0])} <i>{pct(ctx['sup'][1], None)}</i>" if ctx.get("sup") else "—"
    res = f"{num(ctx['res'][0])} <i>{pct(ctx['res'][1], None)}</i>" if ctx.get("res") else "—"
    return f"🧱 {sup} │ {res}"
