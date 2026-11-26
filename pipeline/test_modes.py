import re
#!/usr/bin/env python3
"""Testes dos modos (Normal + temáticos): troca de modo, jogo completo, histórico separado, migração."""
import json, os, sys, datetime, unicodedata
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "pipeline", "modes.json"), encoding="utf-8"))
MODES = [m for m in CFG["modes"] if m["id"] != "normal" and os.path.exists(os.path.join(ROOT, "data", m["id"], "meta.js"))]
NAME = {m["id"]: m["name"] for m in CFG["modes"]}
URL = "file://" + os.path.join(ROOT, "index.html")
NOV25 = datetime.datetime(2026, 11, 25, 12, 0, 0)       # desafio #56 (início em 01/10/2026)

def load(mode):
    B = os.path.join(ROOT, "build", mode)
    voc = json.load(open(os.path.join(B, "vocab.json"), encoding="utf-8"))
    ans = json.load(open(os.path.join(B, "answers.json")))
    return voc, ans["order"], set(ans.get("derived", []))
def ranks(mode, a): return np.frombuffer(open(os.path.join(ROOT, "build", mode, "bin", f"{a}.bin"), "rb").read(), dtype="<u2")
num = lambda t: int(t.replace(".", "").replace(" ", "").replace("★ ", ""))

results = []
def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

def new_page(ctx, init=None):
    p = ctx.new_page(); p.clock.install(time=NOV25)
    errs = []; p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    if init: p.add_init_script(init)
    p.goto(URL); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
    return p, errs
def send(p, w): p.fill("#in", w); p.press("#in", "Enter"); p.wait_for_timeout(120)
def go_mode(p, mode, n=56):
    p.click(f'#modes button[data-m="{mode}"]')
    p.wait_for_function(f"document.getElementById('chNum').textContent==={json.dumps(NAME[mode]+' · Desafio #'+str(n))}", timeout=15000)

with sync_playwright() as pw:
    br = pw.chromium.launch()
    check("10 modos disponíveis no catálogo", len(CFG["modes"]) == 10 and len(MODES) == 9, f"{[m['id'] for m in MODES]}")
    for m in MODES:
        mode = m["id"]; voc, order, derived = load(mode)
        A = order[55 % len(order)]; ans = voc[A]; r = ranks(mode, A)
        ctx = br.new_context(); p, errs = new_page(ctx)
        p.on("dialog", lambda d: d.accept())
        go_mode(p, mode)
        check(f"[{mode}] troca de modo mostra nome e desafio #56", p.inner_text("#chNum") == f"{NAME[mode]} · Desafio #56" and p.inner_text("#chDate") == "25/11/2026")
        send(p, "xyzzyqqw")
        check(f"[{mode}] palavra inexistente não registra", "não está no vocabulário" in p.inner_text("#msg") and p.locator("#list .g").count() == 0)
        w20 = voc[int(np.where(r == 20)[0][0])]
        send(p, w20)
        check(f"[{mode}] posição pré-calculada exibida", p.inner_text("#list .g .r") == "20", w20)
        # você quis dizer: erro de digitação sugere a palavra certa e o clique registra a tentativa
        import unicodedata
        kk = lambda t: "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()
        vk = {kk(x) for x in voc}
        cand = [voc[int(i)] for p_ in range(25, 120) for i in np.where(r == p_)[0] if len(voc[int(i)]) >= 6 and voc[int(i)].isalpha()]
        sw = next((w for w in cand if kk(w[:3] + w[4:]) not in vk and w != ans), None)
        if sw:
            typo = sw[:3] + sw[4:]
            send(p, typo)
            sug = p.locator("#msg button.sug")
            check(f"[{mode}] erro de digitação mostra 'você quis dizer' com a palavra certa", "Você quis dizer" in p.inner_text("#msg") and sug.filter(has_text=sw).count() == 1 and p.locator("#list .g", has_text=sw).count() == 0, f"{typo}->{sw}")
            sug.filter(has_text=sw).first.click(); p.wait_for_timeout(150)
            check(f"[{mode}] clicar na sugestão registra a tentativa com a posição certa", p.locator("#list .g", has_text=sw).count() == 1 and num(p.locator("#list .g", has_text=sw).locator(".r").inner_text()) == int(r[voc.index(sw)]))
        send(p, "xyzzyqqw")
        check(f"[{mode}] palavra sem parecida não sugere nada", "Você quis dizer" not in p.inner_text("#msg") and "não está no vocabulário" in p.inner_text("#msg"))
        # dica: melhor que a melhor posição
        best = 20; ok = True
        for _ in range(3):
            if best <= 3: break
            p.click("#hint"); p.wait_for_timeout(90)
            new = num(p.locator("#last .g .r").inner_text()); ok &= (2 <= new < best); best = new
        check(f"[{mode}] dicas sempre melhoram a melhor posição", ok, str(best))
        # palavra com vetor derivado é aceita e tem posição
        dw = next((voc[i] for i in sorted(derived) if i != A and voc[i].isalpha() and voc[i].lower() not in [g.lower() for g in p.locator('#list .g .w').all_inner_texts()]), None)
        if dw:
            send(p, dw.upper())
            row = p.locator("#list .g", has_text=dw)
            check(f"[{mode}] nome com vetor derivado é aceito e ranqueado", row.count() == 1 and num(row.locator(".r").inner_text()) == int(r[voc.index(dw)]), dw)
        if not m.get("derived_answers"): check(f"[{mode}] vetores derivados nunca são resposta", not (derived & set(order)))
        # vitória + 200 mais próximas
        send(p, ans)
        check(f"[{mode}] acertar mostra vitória", "Você descobriu" in p.inner_text("#end") and p.locator("#list .g.k1").count() == 1)
        p.locator(".closeBtn").first.click(); p.wait_for_timeout(150)
        rr = [num(x) for x in p.locator("#closest .g .r").all_inner_texts()]
        exp = [voc[int(i)] for i in np.argsort(r)[:200]]; exp = exp[:min(200, len(voc))]
        ws = [re.sub(r"\s*(sua tentativa|dica|revelada)\s*$", "", x.strip()).strip() for x in p.locator("#closest .g .w").all_inner_texts()]
        check(f"[{mode}] 200 mais próximas conferem com o ranking", rr == list(range(1, len(exp) + 1)) and ws == exp)
        # histórico separado por modo
        p.click("#tabHist"); p.wait_for_timeout(200)
        check(f"[{mode}] histórico do modo marca #56 como acertou", "acertou" in p.locator('.hist-item[data-n="56"]').inner_text())
        p.click("#tabPlay")
        p.click('#modes button[data-m="normal"]'); p.wait_for_function("document.getElementById('chNum').textContent==='Normal · Desafio #56'")
        p.click("#tabHist"); p.wait_for_timeout(200)
        check(f"[{mode}] histórico do Normal não é afetado", "acertou" not in p.locator('.hist-item[data-n="56"]').inner_text())
        # persistência: recarregar mantém modo (hash) e partida
        p.click("#tabPlay"); go_mode(p, mode)
        p.reload(); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
        check(f"[{mode}] recarregar volta ao mesmo modo com a partida salva", p.inner_text("#chNum") == f"{NAME[mode]} · Desafio #56" and "Você descobriu" in p.inner_text("#end"))
        # desafios diferentes por dia
        p.click("#tabHist"); p.wait_for_timeout(150); p.locator('.hist-item[data-n="55"]').click(); p.wait_for_timeout(300)
        A55 = order[54 % len(order)]
        check(f"[{mode}] dia anterior é outro desafio vazio", p.inner_text("#chNum") == f"{NAME[mode]} · Desafio #55" and p.locator("#list .g").count() == 0 and A55 != A)
        check(f"[{mode}] sem erros de JS", not errs, str(errs[:2]))
        # dados congelados
        rk = ranks(mode, A)
        check(f"[{mode}] ranking é permutação completa e resposta é a posição 1", sorted(rk.tolist()) == list(range(1, len(voc) + 1)) and rk[A] == 1)
        check(f"[{mode}] sequência diária sem repetições", len(set(order)) == len(order), f"{len(order)} respostas · vocab {len(voc)}")
        p.close(); ctx.close()

    # migração dos jogos salvos antes da existência dos modos (IndexedDB v1 -> v2)
    voc, order, _ = load("normal"); a3 = order[2]
    seed = """
    (()=>{ if(localStorage.getItem('seeded'))return; localStorage.setItem('seeded','1');
      const rq=indexedDB.open('palavrorio',1);
      rq.onupgradeneeded=()=>{const s=rq.result.createObjectStore('games',{keyPath:'n'});
        s.put({n:3,date:'03/10/2026',idx:%d,word:%s,v:'v1',guesses:[{idx:5,word:'casa',rank:12,t:1}],hints:0,best:12,solved:false,gaveUp:false,elapsed:5000,started:1,finished:null});};
      rq.onsuccess=()=>rq.result.close(); })();
    """ % (a3, json.dumps(voc[a3]))
    ctx = br.new_context(); p, errs = new_page(ctx, init=seed)
    p.click("#tabHist"); p.wait_for_timeout(300)
    p.click("#more"); p.wait_for_timeout(200)
    t = p.locator('.hist-item[data-n="3"]').inner_text()
    check("recomeço: jogos salvos do banco antigo são ignorados (sequência nova)", "não jogado" in t, t.replace("\n", " "))
    check("migração sem erros de JS", not errs, str(errs[:2]))
    br.close()

print("\n%d/%d testes passaram" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
