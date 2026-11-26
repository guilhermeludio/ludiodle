#!/usr/bin/env python3
"""Gera data/modes.js (catálogo de modos lido pelo jogo, funciona em file://)."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = json.load(open(os.path.join(ROOT, "pipeline", "modes.json"), encoding="utf-8"))
out = {"start": c["start"], "modes": [{"id": m["id"], "name": m["name"], "desc": m["desc"]} for m in c["modes"]]}
open(os.path.join(ROOT, "data", "modes.js"), "w", encoding="utf-8").write("window.MODES=" + json.dumps(out, ensure_ascii=False) + ";\n")
print(open(os.path.join(ROOT, "data", "modes.js"), encoding="utf-8").read())
