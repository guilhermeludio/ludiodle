#!/usr/bin/env python3
"""Testes de ponta a ponta no navegador (Playwright/Chromium)."""
import json, os, sys, time, threading, http.server, socketserver, functools, datetime, unicodedata
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOC = json.load(open(os.path.join(ROOT, "build", "normal", "vocab.json"), encoding="utf-8"))
ORD = json.load(open(os.path.join(ROOT, "build", "normal", "answers.json")))["order"]
def ranks(a): return np.frombuffer(open(os.path.join(ROOT, "build", "normal", "bin", f"{a}.bin"), "rb").read(), dtype="<u2")
def key(w): return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn").lower()

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

NOV25 = datetime.datetime(2026, 11, 25, 12, 0, 0)
URL = "file://" + os.path.join(ROOT, "index.html") + "#normal"

def new_page(ctx, when=NOV25, url=URL, wait=True):
    p = ctx.new_page()
    p.clock.install(time=when)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    p.goto(url)
    p.wait_for_selector("#chNum")
    if wait: p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
    else: p.wait_for_timeout(600)
    return p, errs

def send(p, w):
    p.fill("#in", w); p.press("#in", "Enter"); p.wait_for_timeout(120)

def stats(p):
    return dict(att=int(p.inner_text("#sAtt")), hints=int(p.inner_text("#sHints")), best=p.inner_text("#sBest"),
                items=p.locator("#list .g").count(), msg=p.inner_text("#msg"))

def word_at(a, pos):
    r = ranks(a); return VOC[int(np.where(r == pos)[0][0])]

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context()
    p, errs = new_page(ctx)

    n = 56; A = ORD[n - 1]; ans = VOC[A]
    check("carrega via file:// sem erros", not errs, str(errs[:2]))
    check("desafio de 25/11/2026 é o #56", p.inner_text("#chNum") == "Normal · Desafio #56" and p.inner_text("#chDate") == "25/11/2026", p.inner_text("#chDate"))

    # inexistente
    before = stats(p)
    send(p, "xyzzyqqw")
    s = stats(p)
    check("palavra inexistente: mensagem correta", "não está no vocabulário" in s["msg"], s["msg"])
    check("palavra inexistente: não registra e não gasta dica", s["items"] == before["items"] == 0 and s["att"] == 0 and s["hints"] == 0)

    # válida com posição conhecida
    w300 = word_at(A, 300)
    send(p, w300); s = stats(p)
    check("palavra válida registra com a posição pré-calculada", s["items"] == 1 and p.inner_text("#list .g .r") == "300", f"{w300}")

    # sem acento / maiúscula
    w = next(x for x in VOC if key(x) != x.lower() and ranks(A)[VOC.index(x)] > 1 and x != w300)
    send(p, key(w).upper())
    check("aceita maiúscula e sem acento", stats(p)["items"] == 2, f"{w}")

    # flexão
    inf = next(x for x in ["jogar", "cantar", "comer"] if x in VOC and x != ans and ranks(A)[VOC.index(x)] > 1)
    form = {"jogar": "joguei", "cantar": "cantei", "comer": "comeu"}[inf]
    n0 = stats(p)["items"]; send(p, form)
    rk = int(ranks(A)[VOC.index(inf)])
    row = p.locator('#list .g', has_text=inf)
    check("flexão reconhecida e mapeada ao lema", stats(p)["items"] == n0 + 1 and row.count() == 1 and row.locator(".r").inner_text().replace(".", "").replace(" ", "") == str(rk), f"{form}->{inf} pos {rk}")
    send(p, inf)
    check("lema após flexão é duplicata (não registra)", stats(p)["items"] == n0 + 1 and "já tentou" in stats(p)["msg"])

    # duplicada
    n1 = stats(p)["items"]; send(p, w300)
    check("palavra duplicada não é registrada", stats(p)["items"] == n1 and "já tentou" in stats(p)["msg"])

    # ordenação
    rs = [int(x.replace(".", "").replace(" ", "").replace("★ ", "")) for x in p.locator("#list .g .r").all_inner_texts()]
    check("lista ordenada por proximidade", rs == sorted(rs), str(rs))

    # dicas: sempre melhores que a SUA MELHOR posição
    num = lambda t: int(t.replace(".", "").replace("\u00a0", "").replace("★ ", ""))
    ok = True; det = []
    check("antes de terminar não há botão das 200 mais próximas", p.locator(".closeBtn").count() == 0)
    for _ in range(6):
        best = min(num(x) for x in p.locator("#list .g .r").all_inner_texts())
        if best <= 3: break
        p.click("#hint"); p.wait_for_timeout(100)
        new = num(p.locator("#last .g .r").inner_text())
        det.append((best, new))
        if not (2 <= new < best): ok = False
    check("dicas: sempre melhores que a melhor posição e nunca a 1 (exceto a partir da 2)", ok and len(det) > 0, str(det))
    words = p.locator("#list .g .w").all_inner_texts()
    check("dicas não repetem palavras", len(words) == len(set(words)))

    # cenário relatado: melhor = 300, última tentativa pior -> dica tem que ser melhor que 300
    ctxr = br.new_context(); pr, _ = new_page(ctxr)
    send(pr, word_at(A, 300)); send(pr, word_at(A, 5000))
    got = []
    for _ in range(3):
        pr.click("#hint"); pr.wait_for_timeout(90)
        got.append(num(pr.locator("#last .g .r").inner_text()))
    check("melhor=300 e última pior: dica é melhor que 300 e vai se aproximando", got[0] < 300 and got[0] >= 2 and got[1] < got[0] and got[2] < got[1], str(got))
    check("primeira dica com melhor=300 fica entre ~90 e ~210", 90 <= got[0] <= 210, str(got[0]))
    pr.close()

    # regra: a dica nunca entrega a #1; da melhor=2 em diante entrega #3, #4...
    ctxg = br.new_context()
    pg, _ = new_page(ctxg)
    send(pg, word_at(A, 3))
    pg.click("#hint"); pg.wait_for_timeout(100)
    nl = pg.locator("#last .g .r").inner_text()
    check("a partir da posição 3, dica entrega a 2 (nunca a 1)", nl == "2" and not pg.locator("#in").is_disabled(), nl)
    got2 = []
    for _ in range(3):
        pg.click("#hint"); pg.wait_for_timeout(100)
        got2.append(num(pg.locator("#last .g .r").inner_text()))
    check("com a #2 já na lista, a dica segue com #4, #5... e nunca a 1; jogo continua aberto",
          all(x >= 2 for x in got2) and got2 == sorted(set(got2)) and not pg.locator("#in").is_disabled() and pg.inner_text("#end").strip() == "", str(got2))
    # desistir é a única forma de ver a #1
    pg.on("dialog", lambda d: d.accept())
    pg.click("#giveup"); pg.wait_for_timeout(150)
    check("desistir revela a #1", "A palavra era" in pg.inner_text("#end") and VOC[A] in pg.inner_text("#end"))
    ctxh = br.new_context()
    ph, _ = new_page(ctxh)
    send(ph, word_at(A, 10)); bad = False
    for _ in range(30):
        ph.click("#hint"); ph.wait_for_timeout(40)
        if ph.locator("#end").inner_text().strip() or (ph.locator("#last .g .r").count() and ph.locator("#last .g .r").inner_text()=="1"): bad = True
    check("mesmo apertando a dica 30 vezes, a #1 nunca aparece", not bad)
    ph.close(); pg.close()

    # estado final determinístico em p: desistir
    p.on("dialog", lambda d: d.accept())
    p.click("#giveup"); p.wait_for_timeout(150)

    # 200 mais próximas depois do fim
    check("fim da partida: botão das 200 mais próximas aparece", p.locator(".closeBtn").count() >= 1)
    p.locator(".closeBtn").first.click(); p.wait_for_timeout(150)
    cl = p.locator("#closest .g")
    rr = [num(x) for x in p.locator("#closest .g .r").all_inner_texts()]
    ws = p.locator("#closest .g .w").all_inner_texts()
    check("lista mostra exatamente 200 palavras em ordem 1..200", cl.count() == 200 and rr == list(range(1, 201)), f"{cl.count()}")
    r_ = ranks(A)
    exp = [VOC[int(i)] for i in np.argsort(r_)[:200]]
    check("lista corresponde ao ranking pré-calculado (1ª é a resposta)", all(w.strip().startswith(e) and w.strip()[len(e):].strip() in ("", "sua tentativa", "dica", "dica revelada", "revelada") for w, e in zip(ws, exp)) and len(ws) == len(exp) and exp[0] == VOC[A])
    check("tentativas do jogador aparecem marcadas na lista", p.locator("#closest .g .tag", has_text="sua tentativa").count() >= 1)
    p.locator(".closeBtn").first.click(); p.wait_for_timeout(100)
    check("lista pode ser ocultada", p.locator("#closest .g").count() == 0)

    # persistência
    snap = stats(p)
    p.reload(); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
    s2 = stats(p)
    check("persistência ao recarregar (tentativas, dicas, estado)", s2["items"] == snap["items"] and s2["hints"] == snap["hints"] and "A palavra era" in p.inner_text("#end"))

    # histórico
    p.click("#tabHist"); p.wait_for_timeout(200)
    t = p.inner_text("#hlist")
    check("histórico mostra #56 como desistência e lista só até hoje", "#56" in t and "desistiu" in t and "#57" not in t, t[:80].replace("\n", " "))
    p.locator('.hist-item[data-n="55"]').click(); p.wait_for_timeout(300)
    A24 = ORD[54]
    check("desafio anterior abre com outra palavra e vazio", p.inner_text("#chNum") == "Normal · Desafio #55" and stats(p)["items"] == 0 and A24 != A)
    # vitória no #55
    send(p, VOC[A24]); p.wait_for_timeout(150)
    check("acertar a palavra exibe vitória", "Você descobriu" in p.inner_text("#end") and p.locator("#list .g.k1").count() == 1)
    p.click("#tabHist"); p.wait_for_timeout(200)
    check("histórico marca #55 como acertou", "acertou" in p.locator('.hist-item[data-n="55"]').inner_text())
    check("sem erros de JS durante o uso", not errs, str(errs[:2]))
    p.close()

    # determinismo por data
    ctxb = br.new_context()
    pb, _ = new_page(ctxb, datetime.datetime(2026, 10, 1, 9, 0, 0))
    check("01/10/2026 é o desafio #1", pb.inner_text("#chNum") == "Normal · Desafio #1", pb.inner_text("#chNum"))
    send(pb, VOC[ORD[0]]); pb.wait_for_timeout(150)
    check("resposta do dia 1 corresponde à ordem congelada", "Você descobriu" in pb.inner_text("#end"))
    pb.close()
    ctxc = br.new_context()
    pc, _ = new_page(ctxc, datetime.datetime(2026, 11, 25, 23, 50, 0))
    send(pc, VOC[ORD[55]]); pc.wait_for_timeout(150)
    check("outro navegador/contexto na mesma data recebe a mesma palavra", "Você descobriu" in pc.inner_text("#end"))
    pc.close()
    ctxd = br.new_context()
    pd, _ = new_page(ctxd, datetime.datetime(2026, 9, 30, 12, 0, 0), wait=False)
    send(pd, "casa")
    check("antes de 01/10/2026 não há desafio disponível", "começa em" in pd.inner_text("#msg") or pd.locator("#list .g").count() == 0, pd.inner_text("#msg"))
    pd.close()

    # desistir manual
    ctxe = br.new_context()
    pe, _ = new_page(ctxe)
    pe.on("dialog", lambda d: d.accept())
    send(pe, word_at(ORD[55], 50))
    pe.click("#giveup"); pe.wait_for_timeout(150)
    check("desistir manual revela a resposta", "A palavra era" in pe.inner_text("#end") and VOC[ORD[55]] in pe.inner_text("#end"))
    pe.close()

    # desempenho
    ctxf = br.new_context()
    pf, _ = new_page(ctxf)
    t0 = time.time()
    for w in [word_at(ORD[55], k) for k in (10, 100, 1000, 5000, 9000)]:
        send(pf, w)
    dt = (time.time() - t0) / 5
    pt = pf.evaluate("(()=>{const t=performance.now();for(let i=0;i<2000;i++){document.getElementById('in').value;}return 0})()")
    check("5 tentativas consecutivas rápidas (<400 ms cada, incl. espera de 120 ms)", dt < 0.4, f"{dt*1000:.0f} ms")
    pf.close()
    br.close()

# dados congelados
check("sequência diária sem repetições (respostas únicas)", len(set(ORD)) == len(ORD) >= 2000, f"{len(ORD)}")
r = ranks(ORD[0]); check("ranking é permutação completa 1..N", sorted(r.tolist()) == list(range(1, len(VOC) + 1)))
check("resposta ocupa posição 1", r[ORD[0]] == 1)

print("\n%d/%d testes passaram" % (sum(ok for _, ok in results), len(results)))
sys.exit(0 if all(ok for _, ok in results) else 1)
