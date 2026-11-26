#!/usr/bin/env python3
"""Etapa 1b: análise dos candidatos com o modelo spaCy congelado.

Para cada candidato calcula: forma de exibição, vetor disponível?, rank de frequência,
stopword?, lema, e "coerência" = similaridade com o centroide das linhas (árvore) onde aparece.
Saída: vocab/analysis.json
"""
import json, os, collections, unicodedata
import numpy as np
import spacy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(ROOT, "vocab", "candidates.json"), encoding="utf-8"))
words, lines = data["words"], data["lines"]

nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])
stop = {unicodedata.normalize("NFC", s.lower()) for s in nlp.Defaults.stop_words}

def display(forms):
    # forma mais frequente; empate -> a que tem acento/maiúscula conforme aparece
    return sorted(forms.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

def lookup(form):
    for v in (form, form.lower(), form.capitalize()):
        if nlp.vocab.has_vector(v):
            return v
    return None

recs = {}
for w in words:
    d = display(w["forms"])
    v = lookup(d)
    recs[w["k"]] = {"k": w["k"], "d": d, "vec_key": v, "themes": w["themes"], "lines": w["lines"],
                    "stop": d.lower() in stop,
                    "rank": nlp.vocab[v].rank if v else None}

# lema (contexto isolado; usado só para fundir flexões quando o lema já é candidato)
lc = {}
docs = nlp.pipe([r["d"] for r in recs.values()], batch_size=512)
for r, doc in zip(recs.values(), docs):
    r["lemma"] = doc[0].lemma_ if len(doc) else r["d"]
    r["pos"] = doc[0].pos_ if len(doc) else ""

# vetores normalizados
vecs = {}
for k, r in recs.items():
    if r["vec_key"]:
        x = nlp.vocab[r["vec_key"]].vector.astype(np.float32)
        n = np.linalg.norm(x)
        if n > 0:
            vecs[k] = x / n

# coerência: máx. sobre linhas do cos(palavra, centroide leave-one-out da linha)
for k, r in recs.items():
    r["coh"] = None
    if k not in vecs:
        continue
    best = -1.0
    for li in r["lines"]:
        ks = [x for x in lines[li]["keys"] if x in vecs and x != k]
        if len(ks) < 3:
            continue
        c = np.mean([vecs[x] for x in ks], axis=0)
        c /= (np.linalg.norm(c) + 1e-9)
        best = max(best, float(vecs[k] @ c))
    r["coh"] = best if best > -1 else None

json.dump(list(recs.values()), open(os.path.join(ROOT, "vocab", "analysis.json"), "w", encoding="utf-8"), ensure_ascii=False)

n = len(recs)
oov = [r for r in recs.values() if not r["vec_key"]]
print("candidatos:", n)
print("sem vetor no modelo:", len(oov), f"({100*len(oov)/n:.1f}%)")
print("stopwords:", sum(r["stop"] for r in recs.values()))
fl = [r for r in recs.values() if r["lemma"].lower() != r["d"].lower()]
print("lema diferente da forma:", len(fl))
cohs = np.array([r["coh"] for r in recs.values() if r["coh"] is not None])
print("coerência percentis 1/5/10/25/50:", np.round(np.percentile(cohs, [1, 5, 10, 25, 50]), 3))
print("exemplos sem vetor:", ", ".join(r["d"] for r in oov[:60]))
