#!/usr/bin/env python3
"""Reconstruye la app (index.html) a partir del dataset canónico del informe.
Uso: python3 build.py   ->  inyecta const DATA = [...] en index.html
"""
import json, re, sys

sys.path.insert(0, "/home/dorti/informes/clasico_2021_2026")
from datos import M  # noqa: E402

APP = "/home/dorti/apps/clasico/index.html"

data = []
for m in M:
    data.append({
        "f": m["f"], "comp": m["comp"], "inst": m["j"], "sede": m["sede"],
        "casa": m["casa"], "marc": m["marc"],
        "gb": [[p, t] for p, t in m["gb"]],
        "gm": [[p, t] for p, t in m["gm"]],
        "nota": m.get("nota", ""),
    })

data.sort(key=lambda x: x["f"])
js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

html = open(APP, encoding="utf-8").read()
nuevo, n = re.subn(r"const DATA = \[.*?\];", "const DATA = " + js + ";", html, count=1, flags=re.S)
if n != 1:
    raise SystemExit("no se encontró const DATA en index.html")
open(APP, "w", encoding="utf-8").write(nuevo)

print(f"app actualizada: {len(data)} partidos · {len(nuevo)} bytes")
