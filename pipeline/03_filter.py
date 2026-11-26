#!/usr/bin/env python3
"""Etapa 1c: filtra, funde flexões e gera o vocabulário final (antes dos embeddings).

Regras (todas registradas com contagem em vocab/filter_report.json):
  - sem vetor no modelo congelado        -> removida (lista separada em vocab/oov.txt)
  - stopword / classe fechada            -> removida
  - inglês (zipf_en - zipf_pt >= 1.6)    -> removida
  - baixa coerência com a árvore         -> removida
  - flexão cujo lema já é candidato      -> fundida no lema (nunca inventa lema novo)
  - verbo conjugado (lema em -ar/-er/-ir/-or, com vetor) -> trocado pelo infinitivo
Deduplicação final por chave (minúscula sem acento).
"""
import json, os, collections, unicodedata
import numpy as np
import spacy
from wordfreq import zipf_frequency as zipf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = json.load(open(os.path.join(ROOT, "vocab", "analysis.json"), encoding="utf-8"))
nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])

def key(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn").lower()

CLOSED = {"ADP", "DET", "PRON", "CCONJ", "SCONJ", "AUX", "PART", "ADV"}
by_k = {r["k"]: r for r in A}
removed = collections.defaultdict(list)
EXTRA_FUNC = set("nas nos numa numas nesta neste nessa nesse pelo pela pelos pelas dum duma estou está estão era eram sou são foi pro pra".split())

def drop(r, why):
    removed[why].append(r["d"])

kept = {}
for r in A:
    d = r["d"]
    if not r["vec_key"]:
        drop(r, "sem_vetor"); continue
    if (r["stop"] and r["pos"] in CLOSED) or (d.lower() in EXTRA_FUNC):
        drop(r, "stopword_classe_fechada"); continue
    en, pt = zipf(d.lower(), "en"), zipf(d.lower(), "pt")
    if en - pt >= 1.6:
        drop(r, "ingles"); continue
    coh, rank = r["coh"], r["rank"]
    low = d.lower()
    common = nlp.vocab.has_vector(low) and nlp.vocab[low].rank < 30000 and pt >= 3.5
    if d[0].isupper() and common:
        d = low; r["d"] = low; r["vec_key"] = low        # fragmento comum capitalizado -> minúscula
    rare_name = d[0].isupper() and not common
    if coh is not None:
        if rare_name:
            if coh < 0.0:
                drop(r, "baixa_coerencia"); continue
        elif coh < 0.12 or (coh < 0.20 and rank is not None and rank > 150000):
            drop(r, "baixa_coerencia"); continue
    kept[r["k"]] = r

# fusão de flexões
def plural_targets(f):
    t = []
    if f.endswith("s"):  t.append(f[:-1])
    if f.endswith("es"): t.append(f[:-2])
    if f.endswith(("ões", "ães", "ãos")): t.append(f[:-3] + "ão")
    if f.endswith("ns"): t.append(f[:-2] + "m")
    if f.endswith(("ais", "eis", "ois", "uis")): t.append(f[:-2] + "l")
    return t

merged = {}                      # k_forma -> k_lema | ("NEW", infinitivo)
final = {}
for k, r in kept.items():
    d = r["d"]
    target = None
    if d[0].islower():
        for cand in plural_targets(d):
            ck = key(cand)
            if ck in kept and ck != k and kept[ck]["d"][0].islower():
                target = ck; break
        if target is None:
            lem = r["lemma"]
            if (r["pos"] == "VERB" and lem and lem.lower() != d.lower()
                    and lem.endswith(("ar", "er", "ir", "or"))
                    and not d.endswith(("ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas"))
                    and nlp.vocab.has_vector(lem) and nlp.vocab[lem].rank < 120000):
                lk = key(lem)
                target = lk if (lk in kept and lk != k) else ("NEW", lem)
    if target is None:
        final.setdefault(k, {"d": d, "vec_key": r["vec_key"], "themes": set(r["themes"]), "forms": {d}})
    else:
        merged[k] = target

new_inf = 0
for k, t in merged.items():
    r = kept[k]
    if isinstance(t, tuple):
        lem = t[1]; lk = key(lem)
        e = final.setdefault(lk, {"d": lem, "vec_key": lem, "themes": set(), "forms": set()})
        if not e["forms"]: new_inf += 1
    else:
        lk = t
        e = final.get(lk)
        if e is None:                                      # lema também foi fundido adiante; segue a cadeia
            continue
    e["themes"].update(r["themes"]); e["forms"].add(r["d"])

out = []
for k, e in sorted(final.items()):
    out.append({"k": k, "d": e["d"], "vec_key": e["vec_key"], "themes": sorted(e["themes"]), "forms": sorted(e["forms"])})
json.dump(out, open(os.path.join(ROOT, "vocab", "vocab_filtered.json"), "w", encoding="utf-8"), ensure_ascii=False)

oov = sorted({r["d"] for r in A if not r["vec_key"]})
open(os.path.join(ROOT, "vocab", "oov.txt"), "w", encoding="utf-8").write("\n".join(oov))
rep = {why: len(v) for why, v in removed.items()}
rep.update({"fundidas_em_lema": len(merged), "infinitivos_novos": new_inf, "final": len(out)})
json.dump({"contagens": rep, "amostras": {w: v[:80] for w, v in removed.items()}},
          open(os.path.join(ROOT, "vocab", "filter_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(rep, indent=1, ensure_ascii=False))
