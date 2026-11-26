#!/usr/bin/env python3
"""Etapa 2: embeddings congelados + rankings completos pré-calculados por resposta.

Saída em data/:
  manifest.json   metadados congelados (modelo, versão, dimensão, métrica, hashes, contagens)
  vocab.json      palavras (grafia canônica) na ordem do índice
  forms.json      formas flexionadas reconhecidas -> índice (chave sem acento/minúscula)
  answers.json    índices de vocab elegíveis a resposta + ordem diária (permutação Fisher-Yates c/ seed)
  r/<idx>.bin     ranking COMPLETO da palavra idx: uint16 little-endian, posição (1..N) de cada palavra do vocab
"""
import re, json, os, sys, hashlib, random, unicodedata, time, collections
import numpy as np
import spacy
from wordfreq import zipf_frequency as zipf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
os.makedirs(os.path.join(DATA, "r"), exist_ok=True)
N_ANS_MAX = int(sys.argv[1]) if len(sys.argv) > 1 else 2200
SEED = 687195357
START = "2026-10-01"
VOCAB_VERSION = "v1"

def key(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn").lower()

V = json.load(open(os.path.join(ROOT, "vocab", "vocab_filtered.json"), encoding="utf-8"))
def _keep(w):
    d = w["d"]
    if re.search(r"(.)\1{2,}", d.lower()) or re.fullmatch(r"(?:k+|(?:ha|he|hi|rs|ah|eh)+)", d.lower()): return False   # risadas e alongamentos
    pt = zipf(d.lower(), "pt"); en = zipf(d.lower(), "en")
    if en - pt >= (0.5 if d[0].isupper() else 1.5): return False      # inglês / jargão
    return pt >= 3.6 if d[0].isupper() else pt >= 2.6               # nomes só se muito conhecidos; palavras raras fora
CHAT = set("blz tbm vlw msm bjs dps mds tst scp msn wtf hmm ctrl cmd msg".split())
V = [w for w in V if _keep(w) and w["d"].lower() not in CHAT]
# palavras comuns que faltavam (04b): entram no vocabulário; formas flexionadas levam ao lema
_cp = os.path.join(ROOT, "vocab", "vocab_common.json")
COMMON_FORMS, COMMON_KEYS = {}, set()
if os.path.exists(_cp):
    _c = json.load(open(_cp, encoding="utf-8")); _have = {w["k"] for w in V}
    for w in _c["words"]:
        if w["k"] not in _have: V.append(w); COMMON_KEYS.add(w["k"])
    COMMON_FORMS = _c["forms"]
V.sort(key=lambda w: w["k"])                     # ordem canônica e estável
N = len(V)
assert N < 65535
nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])

# --- vetores (float32, L2-normalizados) -----------------------------------
M = np.zeros((N, 300), dtype=np.float32)
for i, w in enumerate(V):
    x = nlp.vocab[w["vec_key"]].vector.astype(np.float32)
    M[i] = x / np.linalg.norm(x)
vec_hash = hashlib.sha256(M.tobytes()).hexdigest()
vocab_hash = hashlib.sha256("\n".join(w["d"] for w in V).encode()).hexdigest()

# --- formas reconhecidas ---------------------------------------------------
kidx = {key(w["d"]): i for i, w in enumerate(V)}
forms = {}
for i, w in enumerate(V):
    for f in w["forms"]:
        kf = key(f)
        if kf not in kidx:
            forms[kf] = i
# flexões verbais/nominais: formas frequentes do modelo cujo lema está no vocabulário
cand = []
for h in list(nlp.vocab.vectors.keys())[:250000]:
    s = nlp.vocab.strings[h]
    if s.isalpha() and s.islower() and len(s) >= 3 and key(s) not in kidx and key(s) not in forms:
        cand.append(s)
for s, doc in zip(cand, nlp.pipe(cand, batch_size=2048)):
    t = doc[0]
    if t.pos_ == "VERB" and t.lemma_.lower() != s:
        lk = key(t.lemma_)
        if lk in kidx and kidx[lk] is not None and V[kidx[lk]]["d"][0].islower():
            forms[key(s)] = kidx[lk]
# plurais regulares do vocabulário
def plurals(d):
    o = [d + "s"]
    if d.endswith("ão"): o += [d[:-2] + "ões", d[:-2] + "ães", d + "s"]
    elif d.endswith(("r", "z")): o.append(d + "es")
    elif d.endswith("l"): o.append(d[:-1] + "is")
    elif d.endswith("m"): o.append(d[:-1] + "ns")
    return o
for i, w in enumerate(V):
    d = w["d"]
    if d[0].islower() and not d.endswith(("ar", "er", "ir")):
        for p in plurals(d):
            kp = key(p)
            if kp not in kidx and kp not in forms:
                forms[kp] = i


for f, lem in COMMON_FORMS.items():
    kl = key(lem)
    if f not in kidx and f not in forms and kl in kidx: forms[f] = kidx[kl]

# --- conjugação regular (conj.py) (com ajustes ortográficos) -------------------------
from conj import conjugate

# conjugações regulares dos verbos do vocabulário
nverb = 0
for i, w in enumerate(V):
    d = w["d"]
    if d[0].islower() and d.endswith(("ar", "er", "ir")) and len(d) >= 5 and nlp(d)[0].pos_ == "VERB":
        nverb += 1
        for f in conjugate(d):
            kf = key(f)
            if kf not in kidx and kf not in forms:
                forms[kf] = i
print("verbos conjugados:", nverb, "| formas reconhecidas:", len(forms))

# --- elegíveis a resposta --------------------------------------------------
# Regra: qualquer palavra comum, minúscula, de conteúdo (substantivo, adjetivo, verbo no infinitivo) do vocabulário;
# fora: raras, em inglês, siglas, nomes próprios, formas flexionadas, nomes de cidades/gentílicos regionais e a lista
# revisada à mão em vocab/answer_exclude.txt (palavras técnicas, difíceis ou impróprias para ser a resposta do dia).
BLOCK = set("caralho porra buceta puta foda foder cu cuzão viado bicha cacete merda punheta xoxota pau piroca boquete cuceta cagar cuzinho tesão".split())
EXC = set(l.split("#")[0].strip().lower() for l in open(os.path.join(ROOT, "vocab", "answer_exclude.txt"), encoding="utf-8")) - {""} if os.path.exists(os.path.join(ROOT, "vocab", "answer_exclude.txt")) else set()
WL = set("rosa macaco baunilha panda folha serra cachoeira castanho supremo figueira cruz internet".split())
COH = {r["k"]: r["coh"] for r in json.load(open(os.path.join(ROOT, "vocab", "analysis.json"), encoding="utf-8"))}
vs = {w["d"].lower() for w in V}
lows = [w["d"] for w in V]
docs = dict(zip(lows, nlp.pipe(lows, batch_size=1024)))
ctx = {}
for w in V:   # classe gramatical em contexto neutro: pega verbos conjugados que parecem substantivo isolados
    if w["k"] in COMMON_KEYS: ctx[w["d"]] = None
cl = list(ctx)
for d, dd in zip(cl, nlp.pipe([f"Ele disse que {d} agora." for d in cl], batch_size=1024)):
    ctx[d] = dd[3].pos_ if len(dd) > 3 else None
elig = []; why = collections.Counter()
for i, w in enumerate(V):
    d = w["d"]; low = d.lower(); t = docs[d][0]
    def no(r): why[r] += 1
    if d[0].isupper(): no("maiuscula"); continue
    if len(d) < 3 or key(d) in BLOCK or low in EXC: no("bloqueada"); continue
    if not re.search("[aeiouáéíóúâêôãõ]", d) or re.search(r"(.)\1{2,}", low): no("sigla"); continue
    z_pt, z_en = zipf(low, "pt"), zipf(low, "en")
    if z_pt < 3.5: no("rara"); continue
    if z_en - z_pt >= 0.3: no("ingles"); continue
    if len(d) > 12: no("longa"); continue
    if t.pos_ == "PROPN" and low not in WL: no("nome"); continue
    if t.lemma_.lower() != low and t.lemma_.lower() in vs and t.pos_ in ("VERB", "AUX", "ADJ"): no("flexao"); continue
    if w["k"] in COMMON_KEYS:
        if z_pt < 3.8 or ctx.get(d) not in ("NOUN", "ADJ", "VERB") or (ctx.get(d) == "VERB" and not low.endswith(("ar", "er", "ir", "or"))): no("comum-duvidosa"); continue
    else:
        c = COH.get(w["k"])
        if nlp.vocab[w["vec_key"]].rank >= 60000 or (c is not None and c < 0.30): no("vetor/coerencia"); continue
    elig.append(i)
print("elegíveis a resposta:", len(elig), dict(why))
if os.environ.get("DRYRUN"):
    json.dump([V[i]["d"] for i in elig], open("/tmp/elig.json", "w"), ensure_ascii=False); sys.exit(0)
elig_sorted = sorted(elig)
rng = random.Random(SEED)
order = elig_sorted[:]
for i in range(len(order) - 1, 0, -1):            # Fisher-Yates com seed fixa
    j = rng.randint(0, i)
    order[i], order[j] = order[j], order[i]
order = order[:N_ANS_MAX]
print(f"vocab={N}  elegíveis={len(elig)}  respostas usadas={len(order)}")

# --- rankings completos ---------------------------------------------------
t0 = time.time()
idx_all = np.arange(N)
# penaliza vizinhos que só dividem a terminação (-mento, -dade…) ou a grafia (caverna/taverna), sem serem da mesma família
_n = [key(w["d"]) for w in V]
_suf = np.array([x[-4:] if len(x) >= 6 else "" for x in _n]); _pre = np.array([x[:4] for x in _n])
SUF_PEN = 0.07
for n, a in enumerate(order):
    sims = M @ M[a]
    if _suf[a]: sims -= SUF_PEN * ((_suf == _suf[a]) & (_pre != _pre[a]))
    sims[a] = 2.0                                 # a resposta é sempre a posição 1
    o = np.lexsort((idx_all, -sims))              # desempate estável por índice
    r = np.empty(N, dtype=np.uint16)
    r[o] = np.arange(1, N + 1, dtype=np.uint16)
    open(os.path.join(DATA, "r", f"{a}.bin"), "wb").write(r.tobytes())
    if n % 500 == 0:
        print(" ", n, f"{time.time()-t0:.1f}s")
print(f"rankings: {len(order)} arquivos de {N*2/1024:.1f} KB em {time.time()-t0:.1f}s")

json.dump([w["d"] for w in V], open(os.path.join(DATA, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(forms, open(os.path.join(DATA, "forms.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump({"order": order, "eligible": len(elig)}, open(os.path.join(DATA, "answers.json"), "w"), separators=(",", ":"))
json.dump({
    "vocab_version": VOCAB_VERSION, "vocab_size": N, "vocab_sha256": vocab_hash,
    "embedding_model": "spaCy pt_core_news_lg", "model_version": nlp.meta["version"],
    "embedding_dim": 300, "vectors_sha256": vec_hash, "vector_normalization": "L2",
    "similarity": "cosine", "ranking_dtype": "uint16-le", "ties": "estável por índice do vocabulário",
    "daily_start": START, "daily_seed": SEED, "daily_shuffle": "Fisher-Yates (random.Random, seed fixa)",
    "answers": len(order), "forms_count": len(forms),
}, open(os.path.join(DATA, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
