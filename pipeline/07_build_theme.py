#!/usr/bin/env python3
"""Constrói um modo temático: vocabulário, vetores congelados, rankings completos e pacote JS.

uso: python 07_build_theme.py <id-do-modo>        (ids em modes.json)

Diferença para o modo Normal: palavras sem vetor no modelo (nomes de personagens etc.) NÃO são
descartadas; recebem um vetor DERIVADO = centroide das palavras da mesma linha da árvore que têm
vetor real (+ ruído determinístico pequeno). Essas palavras ficam marcadas em manifest.derived.
Elas podem ser digitadas, mas nunca são resposta do dia.
"""
import sys, os, json, glob, re, collections, hashlib, random, base64, time, shutil
import numpy as np
import spacy
from wordfreq import zipf_frequency as zipf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import key, plural_targets, plurals, conjugate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "pipeline", "modes.json"), encoding="utf-8"))
mode = sys.argv[1]
cfg = next(m for m in CFG["modes"] if m["id"] == mode)
THEMES = set(cfg["themes"]); EN_TOL = cfg.get("en_tolerance", 1.6); MAXA = cfg.get("max_answers", 1500); SEED = cfg["seed"]
START = CFG["start"]; VOCAB_VERSION = "v1"
BUILD = os.path.join(ROOT, "build", mode); OUT = os.path.join(ROOT, "data", mode)
shutil.rmtree(BUILD, ignore_errors=True); shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(BUILD, "bin")); os.makedirs(os.path.join(OUT, "r"))

LETTERS = re.compile(r"^[^\W\d_]+$", re.UNICODE)
nlp = spacy.load("pt_core_news_lg", exclude=["parser", "ner"])
stop = {s.lower() for s in nlp.Defaults.stop_words}
EXTRA_FUNC = set("nas nos numa numas nesta neste nessa nesse pelo pela pelos pelas dum duma estou está estão era eram sou são foi pro pra".split())
CLOSED = {"ADP", "DET", "PRON", "CCONJ", "SCONJ", "AUX", "PART", "ADV"}
BLOCK = set("caralho porra buceta puta foda foder cu cuzão viado bicha cacete merda punheta xoxota pau piroca boquete cuceta".split())

# 1) leitura das árvores do modo -------------------------------------------------------------
words = {}; lines = []
for path in sorted(glob.glob(os.path.join(ROOT, "vocab", "raw", "*.txt"))):
    for raw in open(path, encoding="utf-8"):
        if "|" not in raw: continue
        head, body = raw.split("|", 1)
        parts = [p.strip() for p in head.split(">")]
        if parts[0] not in THEMES: continue
        ks = []
        for tok in body.split(","):
            tok = tok.strip()
            if not tok or not LETTERS.match(tok) or len(tok) < 3: continue
            k = key(tok)
            w = words.setdefault(k, {"forms": collections.Counter(), "lines": []})
            w["forms"][tok] += 1; w["lines"].append(len(lines)); ks.append(k)
        lines.append(ks)
print(f"[{mode}] linhas da árvore: {len(lines)} | candidatos únicos: {len(words)}")

def lookup(f):
    for v in (f, f.lower(), f.capitalize()):
        if nlp.vocab.has_vector(v): return v
    return None

recs = {}
for k, w in words.items():
    d = w["forms"].most_common(1)[0][0]
    recs[k] = {"k": k, "d": d, "vk": lookup(d), "lines": w["lines"]}
docs = list(nlp.pipe([r["d"] for r in recs.values()], batch_size=512))
for r, doc in zip(recs.values(), docs):
    r["pos"] = doc[0].pos_; r["lemma"] = doc[0].lemma_

unit = lambda x: x / (np.linalg.norm(x) or 1.0)
vec = {k: unit(nlp.vocab[r["vk"]].vector.astype(np.float32)) for k, r in recs.items() if r["vk"]}

def mates(k, li):
    return [x for x in lines[li] if x in vec and x != k]

for k, r in recs.items():                       # coerência (só palavras com vetor real)
    r["coh"] = None
    if k in vec:
        best = -1.0
        for li in r["lines"]:
            ms = mates(k, li)
            if len(ms) >= 3:
                c = unit(np.mean([vec[x] for x in ms], axis=0)); best = max(best, float(vec[k] @ c))
        r["coh"] = best if best > -1 else None

# 2) filtros ---------------------------------------------------------------------------------
rep = collections.Counter(); kept = {}; why = {}
for k, r in recs.items():
    d = r["d"]; low = d.lower()
    if low in EXTRA_FUNC or (low in stop and r["pos"] in CLOSED): rep["funcional"] += 1; why[k] = "funcional"; continue
    en, pt = zipf(low, "en"), zipf(low, "pt")
    if en - pt >= EN_TOL: rep["ingles"] += 1; why[k] = "ingles"; continue
    if r["vk"]:
        common = nlp.vocab.has_vector(low) and nlp.vocab[low].rank < 30000 and pt >= 3.5
        if d[0].isupper() and common: d = low; r["d"] = low; r["vk"] = low
        rare_name = d[0].isupper() and not common
        rank = nlp.vocab[r["vk"]].rank
        c = r["coh"]
        if c is not None:
            if rare_name:
                if c < 0.0: rep["baixa_coerencia"] += 1; why[k] = "baixa_coerencia"; continue
            elif c < 0.12 or (c < 0.20 and rank > 150000): rep["baixa_coerencia"] += 1; why[k] = "baixa_coerencia"; continue
        r["derived"] = False
    else:                                         # sem vetor: precisa de >= 3 colegas de linha com vetor real
        if not any(len(mates(k, li)) >= 3 for li in r["lines"]): rep["sem_vetor_sem_contexto"] += 1; why[k] = "sem_vetor_sem_contexto"; continue
        r["derived"] = True
    kept[k] = r

# 3) fusão de flexões (plural regular e verbo conjugado; nunca gênero/particípio) -------------
final = {}; merged = {}
for k, r in kept.items():
    d = r["d"]; target = None
    if d[0].islower() and not r["derived"]:
        for cand in plural_targets(d):
            ck = key(cand)
            if ck in kept and ck != k and kept[ck]["d"][0].islower() and not kept[ck]["derived"]:
                target = ck; break
        if target is None:
            lem = r["lemma"]
            if (r["pos"] == "VERB" and lem and lem.lower() != d.lower() and lem.endswith(("ar", "er", "ir", "or"))
                    and not d.endswith(("ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas"))
                    and nlp.vocab.has_vector(lem) and nlp.vocab[lem].rank < 120000):
                lk = key(lem); target = lk if (lk in kept and lk != k) else ("NEW", lem)
    if target is None: final[k] = {"d": d, "vk": r["vk"], "derived": r["derived"], "forms": {d}, "lines": list(r["lines"]), "coh": r["coh"]}
    else: merged[k] = target
for k, t in merged.items():
    r = kept[k]
    if isinstance(t, tuple):
        lk = key(t[1])
        e = final.setdefault(lk, {"d": t[1], "vk": t[1], "derived": False, "forms": set(), "lines": [], "coh": None})
    else:
        e = final.get(t)
        if e is None: continue
    e["forms"].add(r["d"]); e["lines"] += r["lines"]

V = sorted(final.items(), key=lambda kv: kv[0])
keys = [k for k, _ in V]; N = len(V)
assert N < 65535
kidx = {k: i for i, k in enumerate(keys)}

# 4) vetores (reais + derivados) --------------------------------------------------------------
M = np.zeros((N, 300), dtype=np.float32); derived = []
for i, (k, e) in enumerate(V):
    if not e["derived"]:
        M[i] = unit(nlp.vocab[e["vk"]].vector.astype(np.float32))
for i, (k, e) in enumerate(V):
    if e["derived"]:
        cs = []
        for li in set(e["lines"]):
            ms = [x for x in lines[li] if x in vec and x != k]
            if len(ms) >= 3: cs.append(unit(np.mean([vec[x] for x in ms], axis=0)))
        c = unit(np.mean(cs, axis=0))
        g = np.random.default_rng(int(hashlib.sha256(k.encode()).hexdigest()[:8], 16)).standard_normal(300).astype(np.float32)
        M[i] = unit(c + 0.10 * unit(g)); derived.append(i)
vec_hash = hashlib.sha256(M.tobytes()).hexdigest()
vocab = [e["d"] for _, e in V]
vocab_hash = hashlib.sha256("\n".join(vocab).encode()).hexdigest()

# 5) formas reconhecidas -----------------------------------------------------------------------
forms = {}
for i, (k, e) in enumerate(V):
    for f in e["forms"]:
        kf = key(f)
        if kf not in kidx: forms[kf] = i
vdocs = {}
for i, d in enumerate(vocab):
    if d[0].islower() and d.endswith(("ar", "er", "ir")) and len(d) >= 5: vdocs[i] = d
for i, doc in zip(vdocs, nlp.pipe(list(vdocs.values()), batch_size=512)):
    if doc[0].pos_ == "VERB":
        for f in conjugate(vocab[i]):
            kf = key(f)
            if kf not in kidx and kf not in forms: forms[kf] = i
for i, d in enumerate(vocab):
    if d[0].islower() and not d.endswith(("ar", "er", "ir")) and i not in derived:
        for p in plurals(d):
            kp = key(p)
            if kp not in kidx and kp not in forms: forms[kp] = i

# 6) elegíveis a resposta: vetor real, coerentes e ESPECÍFICAS do tema --------------------------
real = [i for i in range(N) if i not in set(derived)]
cen = unit(np.mean(M[real], axis=0))
spec = M @ cen                                       # similaridade ao centro do tema
A_SIM = float(os.environ.get("ANS_SIM", cfg.get("ans_sim", 0.35))); A_ZIPF = float(os.environ.get("ANS_ZIPF", cfg.get("ans_zipf", 3.6))); A_HI = float(os.environ.get("ANS_HI", cfg.get("ans_sim_hi", 0.60)))
elig = []
for i, (k, e) in enumerate(V):
    d = e["d"]
    if e["derived"] and cfg.get("derived_answers"):
        if len(d) >= 4 and key(d) not in BLOCK and d.isalpha() and d[0].isupper(): elig.append(i)   # nomes próprios sem vetor no modelo (modo Pokémon)
        continue
    if e["derived"] or len(d) < 4 or key(d) in BLOCK or e["coh"] is None: continue
    if e["coh"] < 0.40 or nlp.vocab[e["vk"]].rank >= 250000: continue
    if zipf(d.lower(), "en") - zipf(d.lower(), "pt") >= cfg.get("ans_en_max", 1.0): continue   # palavras comuns em inglês não viram resposta
    if (spec[i] >= A_SIM and zipf(d.lower(), "pt") <= A_ZIPF) or spec[i] >= A_HI: elig.append(i)
rng = random.Random(SEED); order = sorted(elig)
for i in range(len(order) - 1, 0, -1):
    j = rng.randint(0, i); order[i], order[j] = order[j], order[i]
order = order[:MAXA]
print(f"[{mode}] vocab={N} (derivadas={len(derived)}) elegíveis={len(elig)} respostas={len(order)} formas={len(forms)}")
print("   removidas:", dict(rep))

# 7) rankings completos ------------------------------------------------------------------------
t0 = time.time(); idx_all = np.arange(N)
for a in order:
    sims = M @ M[a]; sims[a] = 2.0
    o = np.lexsort((idx_all, -sims))
    r = np.empty(N, dtype=np.uint16); r[o] = np.arange(1, N + 1, dtype=np.uint16)
    raw = r.tobytes()
    open(os.path.join(BUILD, "bin", f"{a}.bin"), "wb").write(raw)
    open(os.path.join(OUT, "r", f"{a}.js"), "w").write(f'__R({a},"{base64.b64encode(raw).decode()}");')
print(f"[{mode}] rankings: {len(order)} arquivos de {N*2/1024:.1f} KB em {time.time()-t0:.1f}s")

man = {
    "mode": mode, "mode_name": cfg["name"], "themes": cfg["themes"],
    "vocab_version": VOCAB_VERSION, "vocab_size": N, "vocab_sha256": vocab_hash,
    "embedding_model": "spaCy pt_core_news_lg", "model_version": nlp.meta["version"], "embedding_dim": 300,
    "vectors_sha256": vec_hash, "vector_normalization": "L2", "similarity": "cosine",
    "derived_vectors": len(derived), "derived_vector_method": "centroide das palavras da mesma linha da árvore com vetor real + ruído determinístico 0,10",
    "ranking_dtype": "uint16-le", "ties": "estável por índice do vocabulário",
    "daily_start": START, "daily_seed": SEED, "daily_shuffle": "Fisher-Yates (random.Random, seed fixa)",
    "answers": len(order), "forms_count": len(forms),
}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
payload = {"manifest": man, "vocab": vocab, "forms": forms, "order": order, "derived": derived}
open(os.path.join(OUT, "meta.js"), "w", encoding="utf-8").write(
    '(window.GAMES=window.GAMES||{})["%s"]=' % mode + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
json.dump(vocab, open(os.path.join(BUILD, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"order": order, "derived": derived}, open(os.path.join(BUILD, "answers.json"), "w"))
json.dump(vocab and sorted(w for w in (vocab[i] for i in derived)), open(os.path.join(BUILD, "derived_words.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(why, open(os.path.join(BUILD, "dropped.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"[{mode}] pronto -> data/{mode}/")
