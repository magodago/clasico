#!/usr/bin/env python3
"""Añade a la app el resultado de un Clásico ya jugado (fuente: ESPN).

Uso:
  python3 actualizar.py            # busca hoy y ayer
  python3 actualizar.py 20261025   # fecha concreta (YYYYMMDD)

Si no hay Clásico terminado nuevo, no imprime nada (sirve para cron silencioso).
Si lo hay: actualiza datos.py + index.html, hace commit y push (GitHub Pages).
"""
import json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "/home/dorti/apps/clasico"
DATOS = "/home/dorti/informes/clasico_2021_2026/datos.py"
TZ = ZoneInfo("Europe/Madrid")
LIGAS = [("esp.1", "LaLiga"), ("esp.copa_del_rey", "Copa"), ("esp.supercopa", "Supercopa")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def minuto(disp):
    m = (disp or "").replace("'", "").strip()
    m = m.replace("+", "+")
    m = re.sub(r"\s+", "", m)
    return m


def nombres_conocidos():
    txt = open(DATOS, encoding="utf-8").read()
    return set(re.findall(r'\("([^"]+)", "[^"]*"\)', txt))


def normalizar(nombre, conocidos):
    for c in sorted(conocidos, key=len, reverse=True):
        if nombre == c or nombre.endswith(" " + c):
            return c
    return nombre


def parse_goles(event_id, liga):
    conocidos = nombres_conocidos()
    s = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/summary?event={event_id}")
    gb, gm = {}, {}
    for ev in s.get("keyEvents", []):
        txt = ev.get("text") or ""
        if "Goal!" not in txt and "Own Goal" not in txt:
            continue
        mm = minuto(ev.get("clock", {}).get("displayValue", ""))
        propio = "Own Goal by" in txt
        g = re.search(r"\(([^)]+)\)", txt)
        equipo = g.group(1) if g else ""
        autor = re.search(r"\.\s*([^.]+?)\s*\(", txt)
        nombre = autor.group(1).strip() if autor else "?"
        nombre = normalizar(nombre, conocidos)
        if propio:
            equipo = "Real Madrid" if equipo == "Barcelona" else "Barcelona"
            nombre = nombre + " (p.p.)"
        destino = gb if equipo == "Barcelona" else gm
        destino.setdefault(nombre, []).append(mm)
    fmt = lambda d: [[k, ", ".join(v)] for k, v in d.items()]
    return fmt(gb), fmt(gm)


def ya_existe(fecha):
    txt = open(DATOS, encoding="utf-8").read()
    return f'f="{fecha}"' in txt


def anadir(entry):
    txt = open(DATOS, encoding="utf-8").read()
    # construir literales python limpios
    def lit(arr):
        return "[" + ", ".join(f'("{p}", "{t}")' for p, t in arr) + "]"
    linea = (f' dict(f="{entry["f"]}", comp="{entry["comp"]}", j="{entry["j"]}", sede="{entry["sede"]}", '
             f'casa="{entry["casa"]}", marc="{entry["marc"]}", '
             f'gb={lit(entry["gb"])}, gm={lit(entry["gm"])}, nota="{entry["nota"]}"),\n')
    i = txt.rfind("\n]")
    if i < 0:
        raise SystemExit("no se pudo localizar el final de M en datos.py")
    nuevo = txt[:i + 1] + linea + txt[i + 1:]
    open(DATOS, "w", encoding="utf-8").write(nuevo)


def commit_push(msg):
    subprocess.run(["git", "-C", BASE, "add", "-A"], check=True)
    subprocess.run(["git", "-C", BASE, "-c", "user.name=magodago",
                    "-c", "user.email=dortizs76@gmail.com", "commit", "-q", "-m", msg], check=True)
    subprocess.run(["git", "-C", BASE, "push", "-q", "origin", "main"], check=True)


def main():
    fechas = []
    if len(sys.argv) > 1:
        fechas = [sys.argv[1]]
    else:
        hoy = datetime.now(TZ)
        fechas = [hoy.strftime("%Y%m%d"), (hoy - timedelta(days=1)).strftime("%Y%m%d")]

    for fecha in fechas:
        for liga, comp in LIGAS:
            try:
                d = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard?dates={fecha}")
            except Exception:
                continue
            for ev in d.get("events", []):
                nombre = ev.get("name", "")
                if "Barcelona" not in nombre or "Madrid" not in nombre:
                    continue
                st = ev.get("status", {}).get("type", {})
                if not (st.get("completed") or st.get("description") == "Full Time"):
                    continue
                comps = ev["competitions"][0]["competitors"]
                casa = next((c for c in comps if c.get("homeAway") == "home"), None)
                fuera = next((c for c in comps if c.get("homeAway") == "away"), None)
                if not casa or not fuera:
                    continue
                fecha_local = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(TZ)
                f = fecha_local.strftime("%Y-%m-%d")
                if ya_existe(f):
                    continue
                goles_b, goles_m = parse_goles(ev["id"], liga)
                semana = ev.get("week", {}).get("number")
                inst = f"J{semana}" if (comp == "LaLiga" and semana) else ""
                entry = {
                    "f": f, "comp": comp, "j": inst,
                    "sede": ev["competitions"][0].get("venue", {}).get("fullName", ""),
                    "casa": casa["team"]["displayName"], "marc": f'{casa.get("score")}-{fuera.get("score")}',
                    "gb": goles_b, "gm": goles_m, "nota": "",
                }
                anadir(entry)
                out = subprocess.run([sys.executable, f"{BASE}/build.py"], capture_output=True, text=True)
                if out.returncode != 0:
                    print("ERROR build:", out.stderr[-300:])
                    return 1
                commit_push(f'Clásico {f}: {entry["marc"]} ({comp})')
                gl = lambda a: ", ".join(f"{p} {t}" for p, t in a) or "—"
                print(f"Actualizado: {f} · {comp} {inst} · {entry['sede']}")
                print(f"Barça {entry['marc'].split('-')[0]}–{entry['marc'].split('-')[1]} Madrid")
                print(f"Barça: {gl(goles_b)} | Madrid: {gl(goles_m)}")
                print("https://magodago.github.io/clasico/")
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
