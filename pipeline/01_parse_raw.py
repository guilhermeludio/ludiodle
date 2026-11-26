#!/usr/bin/env python3
"""Etapa 1a: lê vocab/raw/*.txt, valida formato e extrai candidatos.

Saída: vocab/candidates.json  (lista de {w, themes[], lines[]}) e relatório.
Regras: palavra única (somente letras), sem hífen/espaço/apóstrofo/dígito.
"""
import glob, json, os, re, sys, unicodedata, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "vocab", "raw")
OUT = os.path.join(ROOT, "vocab", "candidates.json")

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def key(w):
    return strip_accents(w).lower()

LETTERS = re.compile(r"^[^\W\d_]+$", re.UNICODE)

cands = {}                     # key -> dict
stats = collections.Counter()
bad_lines = 0
line_id = 0
lines = []                     # cada linha da árvore: (tema, caminho, [keys])

for path in sorted(glob.glob(os.path.join(RAW, "*.txt"))):
    for raw in open(path, encoding="utf-8"):
        raw = raw.strip()
        if not raw:
            continue
        if "|" not in raw:
            bad_lines += 1
            continue
        head, body = raw.split("|", 1)
        parts = [p.strip() for p in head.split(">")]
        theme = parts[0]
        ks = []
        for tok in body.split(","):
            tok = tok.strip()
            stats["tokens"] += 1
            if not tok:
                continue
            if not LETTERS.match(tok):
                stats["rejeitado_formato"] += 1
                continue
            if len(tok) < 3:
                stats["rejeitado_curto"] += 1
                continue
            k = key(tok)
            c = cands.setdefault(k, {"forms": collections.Counter(), "themes": set(), "lines": []})
            c["forms"][tok] += 1
            c["themes"].add(theme)
            c["lines"].append(line_id)
            ks.append(k)
        lines.append({"theme": theme, "path": " > ".join(parts), "keys": ks})
        line_id += 1

out = []
for k, c in cands.items():
    out.append({"k": k, "forms": dict(c["forms"]), "themes": sorted(c["themes"]), "lines": c["lines"]})
json.dump({"words": out, "lines": lines}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

themes = collections.Counter()
for w in out:
    for t in w["themes"]:
        themes[t] += 1
print("linhas inválidas (sem '|'):", bad_lines)
print("tokens lidos:", stats["tokens"], "| rejeitados formato:", stats["rejeitado_formato"], "| curtos:", stats["rejeitado_curto"])
print("candidatos únicos (sem acento/caixa):", len(out))
print("temas encontrados:", len(themes))
for t, n in sorted(themes.items(), key=lambda x: -x[1]):
    print(f"  {t:20s} {n}")
