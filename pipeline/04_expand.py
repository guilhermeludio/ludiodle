#!/usr/bin/env python3
"""Etapa 1d: expansão por vizinhança semântica no modelo congelado.

Para cada tema: centroide dos vetores das palavras já filtradas do tema; candidatas =
palavras comuns do português (rank<80000, zipf_pt>=3.0, não inglês, lema==forma, sem stopword)
mais próximas do centroide (cos >= TAU, no máx. K por tema). Marcadas src="modelo".
Saída: vocab/vocab_expanded.json
"""
import json, os, sys, collections, unicodedata
import numpy as np
import spacy
from wordfreq import zipf_frequency as zipf

K = int(sys.argv[1]) if len(sys.argv) > 1 else 350
TAU = float(sys.argv[2]) if len(sys.argv) > 2 else 0.55
POOL = 80000

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = json.load(open(os.path.join(ROOT, "vocab", "vocab_filtered.json"), encoding="utf-8"))
nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])
stop = {s.lower() for s in nlp.Defaults.stop_words}

def key(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn").lower()

have = {w["k"] for w in V}

def unit(x):
    n = np.linalg.norm(x)
    return x / n if n > 0 else x

# pool
strings = nlp.vocab.strings
pool = []
for i, h in enumerate(nlp.vocab.vectors.keys()):
    if i >= POOL: break
    s = strings[h]
    if not (s.isalpha() and s.islower() and len(s) >= 3): continue
    if s in stop or key(s) in have: continue
    pt, en = zipf(s, "pt"), zipf(s, "en")
    if pt < 3.0 or en - pt >= 1.6: continue
    pool.append(s)
print("pool bruto:", len(pool))
def plural_targets(f):
    t = []
    if f.endswith("s"):  t.append(f[:-1])
    if f.endswith("es"): t.append(f[:-2])
    if f.endswith(("ões", "ães", "ãos")): t.append(f[:-3] + "ão")
    if f.endswith("ns"): t.append(f[:-2] + "m")
    if f.endswith(("ais", "eis", "ois", "uis")): t.append(f[:-2] + "l")
    return t
poolset = set(pool) | {w["d"].lower() for w in V}
keep = []
for s, doc in zip(pool, nlp.pipe(pool, batch_size=1024)):
    tok = doc[0]
    if any(c in poolset for c in plural_targets(s)):
        continue                                   # plural de palavra existente
    if tok.pos_ == "VERB" and tok.lemma_.lower() != s:
        continue                                   # verbo conjugado
    if tok.pos_ in ("ADP", "DET", "PRON", "CCONJ", "SCONJ", "AUX", "PART", "ADV", "INTJ", "NUM"):
        continue
    if s.endswith(("mente",)):
        continue                                   # advérbios em -mente
    keep.append(s)
pool = keep
print("pool apos lema==forma:", len(pool))
P = np.stack([unit(nlp.vocab[s].vector.astype(np.float32)) for s in pool])

themes = collections.defaultdict(list)
for w in V:
    for t in w["themes"]:
        themes[t].append(unit(nlp.vocab[w["vec_key"]].vector.astype(np.float32)))

added = {}
per = {}
for t, vs in themes.items():
    c = unit(np.mean(vs, axis=0))
    sims = P @ c
    order = np.argsort(-sims)
    n = 0
    for j in order:
        if sims[j] < TAU or n >= K: break
        s = pool[j]
        e = added.setdefault(key(s), {"k": key(s), "d": s, "vec_key": s, "themes": [], "forms": [s], "src": "modelo"})
        if t not in e["themes"]:
            e["themes"].append(t); n += 1
    per[t] = n

out = [dict(w, src="agentes") for w in V] + list(added.values())
json.dump(out, open(os.path.join(ROOT, "vocab", "vocab_expanded.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("adicionadas:", len(added), "| total:", len(out))
for t, n in sorted(per.items(), key=lambda x: x[1]):
    print(f"  {t:20s} +{n}")
