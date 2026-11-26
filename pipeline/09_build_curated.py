#!/usr/bin/env python3
"""Modo CURADO: vocabulário e semântica escritos à mão (curated/<modo>.txt), sem modelo de linguagem.

Cada linha:  Palavra | tag, tag*2, ...      (peso padrão 1; '~' antes da palavra = só pode ser digitada, nunca é resposta)
A semelhança entre duas palavras é o cosseno entre seus vetores de tags (multi-hot ponderado) + ruído
determinístico mínimo só para desempatar. Os rankings continuam pré-calculados e completos.
uso: python 09_build_curated.py <id-do-modo>
"""
import sys, os, json, re, hashlib, random, base64, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import key as _key
key = lambda w: re.sub(r"[\s\-.'’:]+", "", _key(w))   # palavras compostas: 'Fairy Tail' = 'fairytail' = 'fairy-tail'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "pipeline", "modes.json"), encoding="utf-8"))
mode = sys.argv[1]; cfg = next(m for m in CFG["modes"] if m["id"] == mode)
BUILD = os.path.join(ROOT, "build", mode); OUT = os.path.join(ROOT, "data", mode)
shutil.rmtree(BUILD, ignore_errors=True); shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(BUILD, "bin")); os.makedirs(os.path.join(OUT, "r"))

words, tags, noans, seen = [], [], set(), {}
alias_of = {}   # apelidos: '=apelido' na linha da palavra → leva à palavra (não entra no vocabulário)
for ln, raw in enumerate(open(os.path.join(ROOT, "curated", mode + ".txt"), encoding="utf-8"), 1):
    raw = raw.strip()
    if not raw or raw.startswith("#") or "|" not in raw: continue
    w, t = [x.strip() for x in raw.split("|", 1)]
    no = w.startswith("~"); w = w.lstrip("~").strip()
    assert re.fullmatch(r"[^\W_]+(?: [^\W_]+)*", w), f"linha {ln}: palavra inválida {w!r}"
    k = key(w)
    if k in seen: print(f"  aviso: duplicada {w} (linha {ln}); ignorada"); continue
    al = [x.strip()[1:] for x in t.split(",") if x.strip().startswith("=")]
    t = ", ".join(x for x in t.split(",") if not x.strip().startswith("="))
    for a in al: alias_of[key(a.replace("-", ""))] = k
    seen[k] = len(words); words.append(w); tags.append(t); 
    if no: noans.add(len(words) - 1)
N = len(words)
# ---- camadas extras opcionais (curated/<modo>_extra_*.txt: 'Nome | habilidades | golpes' e <modo>_dex.txt: número da Pokédex) ----
import glob
extra_hab, extra_mv, dexnum = {}, {}, {}
for f in sorted(glob.glob(os.path.join(ROOT, "curated", mode + "_extra_*.txt"))):
    for raw in open(f, encoding="utf-8"):
        raw = raw.strip()
        if not raw or raw.startswith("#"): continue
        p = [x.strip() for x in raw.split("|")]
        if len(p) < 3: continue
        extra_hab[key(p[0])] = [x.strip().lower() for x in p[1].split(",") if x.strip()]
        extra_mv[key(p[0])] = [x.strip().lower() for x in p[2].split(",") if x.strip()]
dp = os.path.join(ROOT, "curated", mode + "_dex.txt")
if os.path.exists(dp):
    for raw in open(dp, encoding="utf-8"):
        p = raw.split()
        if not p: continue
        for j, nm in enumerate(p[1:]): dexnum[key(nm)] = int(p[0]) + j
# pesos por bloco (cada bloco é normalizado em separado; o cosseno final é a média ponderada dos cossenos dos blocos)
BW = {"": 1.0, "mv:": float(os.environ.get("W_MV", 0.7)), "hab:": float(os.environ.get("W_HAB", 0.45)), "dex:": float(os.environ.get("W_DEX", 0.22))}
tv = {}
rows = []
for wi, t in enumerate(tags):
    d = {}
    kk = key(words[wi])
    ex = [("hab:" + a, 1.0) for a in extra_hab.get(kk, [])] + [("mv:" + m, 1.0) for m in extra_mv.get(kk, [])]
    if kk in dexnum:
        n = dexnum[kk]
        ex += [(f"dex:a{n // 6}", 1.0), (f"dex:b{(n + 3) // 6}", 1.0), (f"dex:c{n // 20}", 0.6), (f"dex:d{(n + 10) // 20}", 0.6), (f"dex:e{n // 60}", 0.4)]
    for x, wt in ex:
        d[x] = d.get(x, 0) + wt; tv.setdefault(x, len(tv))
    for x in t.split(","):
        x = x.strip()
        if not x: continue
        wt = 1.0
        if "*" in x: x, s = x.rsplit("*", 1); wt = float(s)
        d[x.strip().lower()] = d.get(x.strip().lower(), 0) + wt
        tv.setdefault(x.strip().lower(), len(tv))
    rows.append(d)
# cada palavra citada por outras (ex.: 'doflamingo' nas tags de Law) ganha a própria tag, para ligar personagem e referência
canon = {}
for t_ in tv: canon.setdefault(key(t_), []).append(t_)
for i, w in enumerate(words):
    for t_ in canon.get(key(w), []):
        if t_ not in rows[i]: rows[i][t_] = 3.0
D = len(tv); NOISE = 32
df = np.zeros(D)
for d in rows:
    for x in d: df[tv[x]] += 1
IDF = 1.0 + 0.35 * np.log(max(len(rows), 2) / np.maximum(df, 1))
M = np.zeros((N, D + NOISE), dtype=np.float32)
for i, d in enumerate(rows):
    for x, wt in d.items(): M[i, tv[x]] = wt * IDF[tv[x]]
    for pre, bw in BW.items():
        idx = [tv[x] for x in d if (x.startswith(pre) if pre else not re.match(r"^(mv|hab|dex):", x))]
        if idx:
            nb = np.linalg.norm(M[i, idx]) or 1.0; M[i, idx] *= np.sqrt(bw) / nb
    g = np.random.default_rng(int(hashlib.sha256(key(words[i]).encode()).hexdigest()[:8], 16)).standard_normal(NOISE).astype(np.float32)
    M[i, D:] = 0.03 * g / np.linalg.norm(g)
M /= np.linalg.norm(M, axis=1, keepdims=True)
# ---- semelhança: tags (S0) + segunda ordem (vizinhos dos vizinhos) para desempatar com sentido ----
Mt = M[:, :D] / np.maximum(np.linalg.norm(M[:, :D], axis=1, keepdims=True), 1e-9)
S0 = Mt @ Mt.T
GAMMA = float(os.environ.get("GAMMA", 0.5)); KNN = int(os.environ.get("KNN", 12))
def second_order(S):
    P = np.zeros_like(S)
    for i in range(len(S)):
        row = S[i].copy(); row[i] = -1
        nb = np.argpartition(-row, min(KNN, len(S) - 2))[:KNN]
        w = np.maximum(row[nb], 0) ** 2
        if w.sum() > 0: P[i, nb] = w / w.sum()
    S2 = P @ S
    return (S2 + S2.T) / 2
S1 = S0 + GAMMA * second_order(S0) if GAMMA > 0 else S0
S1 = S1 / (1 + GAMMA if GAMMA > 0 else 1)
def quality(S, name):
    n = len(S); T = S.copy(); np.fill_diagonal(T, -9)
    top = np.argsort(-T, axis=1)[:, :30]; sv = np.take_along_axis(T, top, 1)
    ties = float(np.mean(np.abs(np.diff(sv, axis=1)) < 1e-4))
    sym = []
    for a in range(n):
        for b in top[a, :5]:
            sym.append(a in set(np.argsort(-T[b])[:25]))
    hub = np.bincount(top[:, :10].ravel(), minlength=n)
    h = np.argsort(-hub)[:4]
    print(f"   [{name}] empates no top-30: {ties:.0%} | vizinhança recíproca (top5→top25): {np.mean(sym):.0%} | maior hub: " + ", ".join(f"{words[i]}({hub[i]})" for i in h))
if os.environ.get("QUALITY", "1") == "1":
    quality(S0, "só tags"); quality(S1, "tags + 2ª ordem")
S = S1 + (M[:, D:] @ M[:, D:].T) * 0.05            # ruído mínimo, só para desempate final
vec_hash = hashlib.sha256(M.tobytes()).hexdigest(); vocab_hash = hashlib.sha256("\n".join(words).encode()).hexdigest()
forms = {}
for i, w in enumerate(words):
    for f in {key(w), key(w.replace("-", ""))}:
        if f not in {key(x) for x in words[:0]} and f != key(w): forms[f] = i
for a, k in alias_of.items():
    if a not in seen and k in seen: forms[a] = seen[k]
    elif a in seen: print(f"  aviso: apelido {a} já é palavra; ignorado")
order = [i for i in range(N) if i not in noans]
rng = random.Random(cfg["seed"])
for i in range(len(order) - 1, 0, -1):
    j = rng.randint(0, i); order[i], order[j] = order[j], order[i]
idx_all = np.arange(N)
for a in order:
    s = S[a].copy(); s[a] = 9.0
    o = np.lexsort((idx_all, -s)); r = np.empty(N, dtype=np.uint16); r[o] = np.arange(1, N + 1, dtype=np.uint16)
    b = r.tobytes()
    open(os.path.join(BUILD, "bin", f"{a}.bin"), "wb").write(b)
    open(os.path.join(OUT, "r", f"{a}.js"), "w").write(f'__R({a},"{base64.b64encode(b).decode()}");')
man = {"mode": mode, "mode_name": cfg["name"], "themes": cfg.get("themes", []), "vocab_version": "v2", "vocab_size": N, "vocab_sha256": vocab_hash,
       "embedding_model": "curadoria manual (características)", "model_version": "v2", "embedding_dim": D + NOISE, "vectors_sha256": vec_hash,
       "vector_normalization": "L2", "similarity": "cosine", "derived_vectors": 0, "ranking_dtype": "uint16-le", "ties": "estável por índice do vocabulário",
       "daily_start": CFG["start"], "daily_seed": cfg["seed"], "daily_shuffle": "Fisher-Yates (random.Random, seed fixa)", "answers": len(order), "forms_count": len(forms)}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(OUT, "meta.js"), "w", encoding="utf-8").write('(window.GAMES=window.GAMES||{})["%s"]=' % mode + json.dumps({"manifest": man, "vocab": words, "forms": forms, "order": order, "derived": []}, ensure_ascii=False, separators=(",", ":")) + ";\n")
json.dump(words, open(os.path.join(BUILD, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"order": order, "derived": []}, open(os.path.join(BUILD, "answers.json"), "w"))
json.dump([], open(os.path.join(BUILD, "derived_words.json"), "w"))
print(f"[{mode}] curado: vocab={N} respostas={len(order)} tags={D}")
