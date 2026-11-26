import os, json, threading, http.server, socketserver, functools, datetime, time, sys
import numpy as np
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOC = json.load(open(os.path.join(ROOT,"build","normal","vocab.json"),encoding="utf-8"))
ORD = json.load(open(os.path.join(ROOT,"build","normal","answers.json")))["order"]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
class Q(H.func):
    def log_message(self,*a): pass
srv = socketserver.TCPServer(("127.0.0.1",0), functools.partial(Q, directory=ROOT)); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = []
def check(n,c,e=""): ok.append(c); print(("PASS " if c else "FAIL ")+n+(f" [{e}]" if e else ""))
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context()
    p = ctx.new_page(); p.clock.install(time=datetime.datetime(2026,11,25,12,0,0))
    errs=[]; p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(f"http://127.0.0.1:{port}/index.html"); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
    p.evaluate("navigator.serviceWorker.ready.then(()=>1)")
    p.wait_for_timeout(5000)   # precache dos próximos dias
    w = VOC[ORD[55]]
    ctx.set_offline(True)
    p.reload(); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')", timeout=15000)
    check("offline: página e dados carregam do cache", p.inner_text("#chNum")=="Normal · Desafio #56")
    p.fill("#in","casa"); p.press("#in","Enter"); p.wait_for_timeout(200)
    p.fill("#in",w); p.press("#in","Enter"); p.wait_for_timeout(200)
    check("offline: tentativa e vitória funcionam sem rede", "Você descobriu" in p.inner_text("#end"))
    p.click('#modes button[data-m="naruto"]'); p.wait_for_function("document.getElementById('chNum').textContent==='Naruto · Desafio #56'", timeout=15000)
    check("offline: troca para outro modo (dados em cache)", p.inner_text("#chNum")=="Naruto · Desafio #56")
    # dia seguinte precacheado
    p2 = ctx.new_page(); p2.clock.install(time=datetime.datetime(2026,11,27,12,0,0))
    p2.goto(f"http://127.0.0.1:{port}/index.html"); p2.wait_for_function("document.getElementById('chNum').textContent.includes('#')", timeout=15000)
    check("offline: desafios dos próximos dias já estão em cache", p2.inner_text("#chNum")=="Normal · Desafio #58")
    check("sem erros de JS offline", not errs, str(errs[:2]))
    br.close()
print(sum(ok),"/",len(ok)); sys.exit(0 if all(ok) else 1)
