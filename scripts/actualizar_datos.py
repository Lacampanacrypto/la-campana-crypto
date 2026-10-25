"""
La Campana Crypto: genera datos.json con la información del día.

Fuentes (todas gratuitas, sin clave):
  - CoinGecko: precios cripto, dominancia de BTC, capitalización total
  - alternative.me: índice de miedo y codicia
  - Coinbase Exchange: velas de BTC para VWAP diario y aperturas
  - Yahoo Finance (vía yfinance): futuros, índices, bonos, dólar, petróleo, megacaps
  - Forex Factory (faireconomy): calendario económico de EE. UU.
  - holidays: feriados de la bolsa de Nueva York (NYSE)

Uso:  python scripts/actualizar_datos.py salida/datos.json

Cada fuente se consulta por separado: si una falla, el resto del archivo
se genera igual y esa sección queda vacía (la página la muestra como "sin datos").
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
HEADERS = {"User-Agent": "LaCampanaCrypto/1.0 (+https://github.com)", "Accept": "application/json"}
TIMEOUT = 20


# ---------------------------------------------------------------- utilidades
def aviso(msg: str) -> None:
    print(f"[aviso] {msg}", file=sys.stderr)


def seguro(nombre: str):
    """Ejecuta una fuente; si falla, registra el error y devuelve None."""
    def deco(fn):
        def envoltura(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:  # noqa: BLE001
                aviso(f"{nombre} falló: {e}")
                traceback.print_exc(file=sys.stderr)
                return None
        return envoltura
    return deco


def get_json(url: str, **params):
    r = requests.get(url, params=params or None, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def redondear(x, n=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return round(x, n)


def pct(actual, ref):
    if actual is None or ref in (None, 0):
        return None
    return round((actual / ref - 1) * 100, 2)


# ---------------------------------------------------------------- cripto
@seguro("CoinGecko precios")
def cripto_precios():
    data = get_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        vs_currency="usd", ids="bitcoin,ethereum,solana", price_change_percentage="24h",
    )
    simbolos = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
    por_id = {c["id"]: c for c in data}
    monedas = []
    for cid in ("bitcoin", "ethereum", "solana"):
        c = por_id.get(cid)
        if not c:
            continue
        monedas.append({
            "s": simbolos[cid],
            "precio": redondear(c.get("current_price")),
            "cambio24h": redondear(c.get("price_change_percentage_24h")),
            "max24h": redondear(c.get("high_24h")),
            "min24h": redondear(c.get("low_24h")),
        })
    return monedas


@seguro("CoinGecko global")
def cripto_global():
    d = get_json("https://api.coingecko.com/api/v3/global")["data"]
    return {
        "dominancia_btc": redondear(d["market_cap_percentage"].get("btc")),
        "cap_total": redondear(d["total_market_cap"].get("usd"), 0),
        "cap_cambio24h": redondear(d.get("market_cap_change_percentage_24h_usd")),
        "volumen24h": redondear(d["total_volume"].get("usd"), 0),
    }


@seguro("Miedo y codicia")
def miedo_codicia():
    d = get_json("https://api.alternative.me/fng/", limit=31)["data"]

    def punto(i):
        if i >= len(d):
            return None
        return {"valor": int(d[i]["value"]), "etiqueta": d[i]["value_classification"]}

    return {"hoy": punto(0), "ayer": punto(1), "semana": punto(7), "mes": punto(30)}


def velas_coinbase(granularidad: int, inicio: datetime, fin: datetime):
    """Velas BTC-USD de Coinbase: [tiempo, mínimo, máximo, apertura, cierre, volumen], ordenadas por tiempo."""
    data = get_json(
        "https://api.exchange.coinbase.com/products/BTC-USD/candles",
        granularity=granularidad,
        start=inicio.isoformat().replace("+00:00", "Z"),
        end=fin.isoformat().replace("+00:00", "Z"),
    )
    return sorted(data, key=lambda v: v[0])


@seguro("Niveles BTC")
def niveles_btc():
    ahora = datetime.now(UTC)
    inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    velas = velas_coinbase(300, inicio_dia, ahora)  # 5 minutos, máx. 288 velas
    if not velas:
        return None
    num = sum(((v[1] + v[2] + v[4]) / 3) * v[5] for v in velas)
    vol = sum(v[5] for v in velas)
    vwap = num / vol if vol else None

    lunes = inicio_dia - timedelta(days=inicio_dia.weekday())
    diarias = velas_coinbase(86400, lunes - timedelta(days=1), ahora)
    ap_semanal = next((v[3] for v in diarias if v[0] == int(lunes.timestamp())), None)

    return {
        "vwap_diario": redondear(vwap, 0),
        "apertura_diaria": redondear(velas[0][3], 0),
        "apertura_semanal": redondear(ap_semanal, 0),
        "max_dia": redondear(max(v[2] for v in velas), 0),
        "min_dia": redondear(min(v[1] for v in velas), 0),
    }


# ---------------------------------------------------------------- mercado americano
def _yf():
    import yfinance as yf  # import tardío: si falta, solo falla esta parte
    return yf


def _fecha_ny(ts) -> date:
    return ts.tz_convert(NY).date() if ts.tzinfo else ts.date()


@seguro("Cotización")
def cotizacion(simbolo: str, prepost: bool = False):
    """Último precio y cambio frente al cierre de la sesión anterior."""
    yf = _yf()
    t = yf.Ticker(simbolo)
    diario = t.history(period="10d", interval="1d", auto_adjust=False)
    diario = diario.dropna(subset=["Close"])
    if diario.empty:
        return None
    hoy = datetime.now(NY).date()
    if _fecha_ny(diario.index[-1]) == hoy and len(diario) >= 2:
        ref = float(diario["Close"].iloc[-2])
    else:
        ref = float(diario["Close"].iloc[-1])
    intradia = t.history(period="2d", interval="5m", prepost=prepost, auto_adjust=False).dropna(subset=["Close"])
    ultimo = float(intradia["Close"].iloc[-1]) if not intradia.empty else float(diario["Close"].iloc[-1])
    return {"precio": redondear(ultimo, 2), "ref": redondear(ref, 2), "cambio_pct": pct(ultimo, ref),
            "cambio": redondear(ultimo - ref, 3)}


def lista(simbolos: list[tuple[str, str, str]], prepost=False):
    salida = []
    for simbolo, etiqueta, nombre in simbolos:
        q = cotizacion(simbolo, prepost=prepost)
        if q:
            salida.append({"s": etiqueta, "nombre": nombre, **q})
    return salida


@seguro("Niveles NQ")
def niveles_nq():
    yf = _yf()
    t = yf.Ticker("NQ=F")
    barras = t.history(period="5d", interval="5m", auto_adjust=False).dropna(subset=["Close"])
    if barras.empty:
        return None
    barras = barras.tz_convert(NY)
    ahora = datetime.now(NY)

    # Sesión regular previa (9:30–16:00 ET) más reciente que ya terminó
    rth = barras.between_time("09:30", "15:55")
    dias = sorted({d for d in rth.index.date if datetime.combine(d, datetime.min.time(), NY).replace(hour=16) <= ahora})
    nivel = {}
    if dias:
        previa = rth[rth.index.date == dias[-1]]
        tipico = (previa["High"] + previa["Low"] + previa["Close"]) / 3
        vol = previa["Volume"].sum()
        nivel.update({
            "max_previo": redondear(previa["High"].max()),
            "min_previo": redondear(previa["Low"].min()),
            "cierre_previo": redondear(previa["Close"].iloc[-1]),
            "vwap_previo": redondear((tipico * previa["Volume"]).sum() / vol) if vol else None,
        })
        # Rango nocturno: desde las 18:00 ET posteriores a esa sesión
        desde = datetime.combine(dias[-1], datetime.min.time(), NY).replace(hour=18)
        noche = barras[(barras.index >= desde) & (barras.index <= ahora)]
        apertura = noche[(noche.index.date > dias[-1]) & (noche.index.time >= time(9, 30))]
        if not apertura.empty:  # si ya abrió la sesión, el rango nocturno termina a las 9:30
            noche = noche[noche.index < apertura.index[0]]
        if not noche.empty:
            nivel["overnight_max"] = redondear(noche["High"].max())
            nivel["overnight_min"] = redondear(noche["Low"].min())
    return nivel or None


# ---------------------------------------------------------------- calendario y feriados
@seguro("Calendario económico")
def calendario():
    eventos = []
    for semana in ("thisweek", "nextweek"):
        try:
            data = get_json(f"https://nfs.faireconomy.media/ff_calendar_{semana}.json")
        except Exception as e:  # noqa: BLE001
            aviso(f"calendario {semana}: {e}")
            continue
        for ev in data:
            if ev.get("country") != "USD" or ev.get("impact") not in ("High", "Medium"):
                continue
            eventos.append({
                "fecha": ev.get("date"),
                "titulo": ev.get("title"),
                "impacto": "alto" if ev.get("impact") == "High" else "medio",
                "consenso": ev.get("forecast") or None,
                "anterior": ev.get("previous") or None,
            })
    unicos = {(e["fecha"], e["titulo"]): e for e in eventos}  # sin duplicados entre semanas
    return sorted(unicos.values(), key=lambda e: e["fecha"] or "")


@seguro("Feriados")
def feriados():
    import holidays
    hoy = datetime.now(NY).date()
    salida = {}
    for anio in (hoy.year, hoy.year + 1):
        for d, nombre in holidays.financial_holidays("NYSE", years=anio).items():
            salida[d.isoformat()] = {"t": "closed", "n": traducir_feriado(nombre)}
        # Cierres anticipados (1:00 pm ET)
        acc = date(anio, 11, 1)
        jueves = [acc + timedelta(days=i) for i in range(30) if (acc + timedelta(days=i)).weekday() == 3][3]
        salida.setdefault((jueves + timedelta(days=1)).isoformat(),
                          {"t": "early", "n": "Viernes después de Acción de Gracias"})
        for d, nombre in ((date(anio, 7, 3), "Víspera del Día de la Independencia"),
                          (date(anio, 12, 24), "Nochebuena")):
            if d.weekday() < 4 and d.isoformat() not in salida:
                salida[d.isoformat()] = {"t": "early", "n": nombre}
    return dict(sorted(salida.items()))


FERIADOS_ES = {
    "New Year's Day": "Año Nuevo",
    "Martin Luther King Jr. Day": "Día de Martin Luther King Jr.",
    "Washington's Birthday": "Día de los Presidentes",
    "Good Friday": "Viernes Santo",
    "Memorial Day": "Día de los Caídos",
    "Juneteenth National Independence Day": "Juneteenth",
    "Independence Day": "Día de la Independencia",
    "Labor Day": "Día del Trabajo",
    "Thanksgiving Day": "Día de Acción de Gracias",
    "Christmas Day": "Navidad",
}


def traducir_feriado(nombre: str) -> str:
    observado = "(observed)" in nombre.lower() or "observed" in nombre.lower()
    base = nombre.replace(" (observed)", "").replace(" (Observed)", "").strip()
    es = FERIADOS_ES.get(base, base)
    return f"{es} (observado)" if observado else es


# ---------------------------------------------------------------- principal
def generar() -> dict:
    return {
        "actualizado": datetime.now(UTC).isoformat(timespec="seconds"),
        "cripto": {"monedas": cripto_precios() or [], "global": cripto_global()},
        "miedo_codicia": miedo_codicia(),
        "btc_niveles": niveles_btc(),
        "futuros": lista([
            ("NQ=F", "NQ", "Futuros Nasdaq-100"),
            ("ES=F", "ES", "Futuros S&P 500"),
            ("^N225", "Nikkei", "Japón"),
            ("^HSI", "Hang Seng", "Hong Kong"),
            ("^STOXX", "Stoxx 600", "Europa"),
        ]),
        "tasas": lista([
            ("^TNX", "US10Y", "Bono a 10 años (%)"),
            ("DX-Y.NYB", "DXY", "Índice dólar"),
            ("^VIX", "VIX", "Volatilidad"),
        ]),
        "megacaps": lista([
            ("NVDA", "NVDA", "Nvidia"), ("AAPL", "AAPL", "Apple"), ("MSFT", "MSFT", "Microsoft"),
            ("AMZN", "AMZN", "Amazon"), ("META", "META", "Meta"), ("GOOGL", "GOOGL", "Alphabet"),
            ("TSLA", "TSLA", "Tesla"),
        ], prepost=True),
        "petroleo": lista([
            ("BZ=F", "Brent", "Referencia internacional"),
            ("CL=F", "WTI", "Referencia de EE. UU."),
        ]),
        "nq_niveles": niveles_nq(),
        "calendario": calendario() or [],
        "feriados": feriados(),
    }


def main():
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "datos.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = generar()
    principales = [datos["cripto"]["monedas"], datos["futuros"], datos["megacaps"], datos["miedo_codicia"]]
    if not any(principales):
        # Si fallaron todas las fuentes, no se publica nada y se conserva el archivo anterior
        sys.exit("Todas las fuentes principales fallaron; no se actualiza datos.json.")
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    vacias = [k for k, v in datos.items() if v in (None, [], {})]
    print(f"Escrito {destino} ({destino.stat().st_size} bytes). Secciones vacías: {vacias or 'ninguna'}")


if __name__ == "__main__":
    main()
