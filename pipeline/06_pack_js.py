#!/usr/bin/env python3
"""Etapa 2b: empacota os dados para o navegador (funciona em file:// e em https).

data/meta.js        window.GAME = {manifest, vocab, forms, order}
data/r/<idx>.js     window.__R(idx,"<base64 do uint16-le>")
Os .bin originais vão para build/bin (não são publicados).
"""
import base64, json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
BIN = os.path.join(ROOT, "build", "bin")
os.makedirs(BIN, exist_ok=True)

man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
vocab = json.load(open(os.path.join(D, "vocab.json"), encoding="utf-8"))
forms = json.load(open(os.path.join(D, "forms.json"), encoding="utf-8"))
order = json.load(open(os.path.join(D, "answers.json")))["order"]

with open(os.path.join(D, "meta.js"), "w", encoding="utf-8") as f:
    f.write("window.GAME=" + json.dumps({"manifest": man, "vocab": vocab, "forms": forms, "order": order},
                                         ensure_ascii=False, separators=(",", ":")) + ";\n")

n = 0
for name in sorted(os.listdir(os.path.join(D, "r"))):
    if not name.endswith(".bin"):
        continue
    idx = int(name[:-4])
    raw = open(os.path.join(D, "r", name), "rb").read()
    open(os.path.join(D, "r", f"{idx}.js"), "w").write(f'__R({idx},"{base64.b64encode(raw).decode()}");')
    shutil.move(os.path.join(D, "r", name), os.path.join(BIN, name))
    n += 1
for name in ("vocab.json", "forms.json", "answers.json"):
    shutil.move(os.path.join(D, name), os.path.join(ROOT, "build", name))
print("empacotados:", n, "rankings")
