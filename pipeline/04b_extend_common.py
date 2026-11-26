#!/usr/bin/env python3
"""Etapa 1e: palavras comuns que faltavam no vocabulário (modo Normal).

Pega as palavras mais frequentes do português que o jogo ainda não reconhece, leva cada uma ao seu lema
(plural/feminino/verbo conjugado -> forma-base) e acrescenta o lema ao vocabulário quando é palavra de conteúdo
(substantivo, adjetivo, verbo). A forma original passa a ser reconhecida e vale a posição do lema.
Saída: vocab/vocab_common.json  {"words":[{k,d,vec_key,forms}], "forms":{forma: lema}}
"""
import json, os, re, unicodedata, collections
import spacy, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conj import conjugate
from wordfreq import top_n_list, zipf_frequency as z
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
key = lambda w: "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn").lower()
V = json.load(open(os.path.join(ROOT, "vocab", "vocab_filtered.json"), encoding="utf-8"))
have = {w["k"]: w for w in V}
nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])
stop = {x.lower() for x in nlp.Defaults.stop_words}
pool = {}
for i, h in enumerate(nlp.vocab.vectors.keys()):
    if i >= 80000: break
    pool[nlp.vocab.strings[h]] = i
PT_EU = {"projecto", "registo", "actualmente", "actividades", "contacto", "voces", "facto", "equipa", "ecrã", "telemóvel", "autocarro", "comboio", "miúdo"}  # grafias de Portugal ficam de fora
cand = [w for w in top_n_list("pt", 60000) if w.isalpha() and len(w) >= 3 and w.islower() and w in pool and w not in stop and key(w) not in have and w not in PT_EU]
cand = [w for w in cand if z(w, "pt") >= 3.4 and z(w, "en") - z(w, "pt") < 0.3]
# formas conjugadas (regulares) dos infinitivos que o jogo já tem: nunca viram palavra própria
INF = {w["d"].lower() for w in V if w["d"][0].islower() and w["d"].endswith(("ar", "er", "ir")) and len(w["d"]) >= 5}
CONJ = {}
for inf in INF:
    for f in conjugate(inf): CONJ.setdefault(key(f), inf)
words = {}; forms = {}
OPEN = ("NOUN", "ADJ", "VERB")
ctxd = list(nlp.pipe([f"Ele disse que {w} agora." for w in cand], batch_size=1024))
for w, d, cd in zip(cand, nlp.pipe(cand, batch_size=1024), ctxd):
    t = cd[3] if len(cd) > 3 and cd[3].text.lower() == w else d[0]   # lema/classe em contexto (mais confiável que a palavra isolada)
    if key(w) in CONJ:
        if CONJ[key(w)] in have or key(CONJ[key(w)]) in have: forms[key(w)] = CONJ[key(w)]
        continue
    ct = cd[3].pos_ if len(cd) > 3 else None
    if ct in ("VERB", "AUX") and not w.endswith(("ar", "er", "ir", "or")): continue   # verbo conjugado em contexto: não entra como palavra
    if t.pos_ not in OPEN or ct == "PROPN" or (len(w) < 4 and z(w, "pt") < 4.5): continue
    lem = t.lemma_.lower()
    if not (lem.isalpha() and lem in pool and len(lem) >= 3) or lem in stop or lem in PT_EU: lem = w
    if t.pos_ == "VERB" and not lem.endswith(("ar", "er", "ir", "or")): lem = w
    if z(lem, "pt") < 3.4 or z(lem, "en") - z(lem, "pt") >= 0.3: continue
    kl = key(lem)
    if kl in have:
        if key(w) != kl: forms[key(w)] = have[kl]["d"]
        continue
    words[kl] = {"k": kl, "d": lem, "vec_key": lem, "forms": [lem], "themes": ["Comum"]}
    if key(w) != kl: forms[key(w)] = lem
# -mente e diminutivos viram forma do adjetivo/substantivo-base quando a base existe
allk = set(have) | set(words)
for w in top_n_list("pt", 60000):
    if not w.isalpha() or not w.islower() or key(w) in allk or key(w) in forms: continue
    k = key(w)
    if k.endswith("mente") and len(k) > 8:
        b = k[:-5]
        for c in (b, b[:-1] + "o", b[:-1] + "e"):
            if c in allk: forms[k] = (have.get(c) or words[c])["d"]; break
    for suf in ("zinho", "zinha", "inho", "inha", "zito", "zita"):
        if k.endswith(suf) and len(k) > len(suf) + 3:
            b = k[:-len(suf)]
            for c in (b, b + "o", b + "a", b + "e", b[:-1] + "o"):
                if c in allk and c not in forms: forms[k] = (have.get(c) or words[c])["d"]; break
            else: continue
            break
# plurais cujo singular existe: viram forma do singular, não palavra
def _sing(k):
    o = []
    if k.endswith("s"): o.append(k[:-1])
    if k.endswith("es"): o.append(k[:-2])
    if k.endswith(("ões", "ães")): o.append(k[:-3] + "ão")
    if k.endswith("ais"): o.append(k[:-2] + "l")
    return o
for k in list(words):
    for sg in _sing(k):
        tgt = (have.get(sg) or words.get(sg))
        if tgt and sg != k:
            forms[k] = tgt["d"]; words.pop(k); break
json.dump({"words": sorted(words.values(), key=lambda x: x["k"]), "forms": forms}, open(os.path.join(ROOT, "vocab", "vocab_common.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"palavras novas: {len(words)} | formas novas: {len(forms)}")
