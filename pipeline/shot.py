import os, json, datetime, numpy as np
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOC=json.load(open(ROOT+"/build/vocab.json",encoding="utf-8")); ORD=json.load(open(ROOT+"/build/answers.json"))["order"]
A=ORD[24]; r=np.frombuffer(open(f"{ROOT}/build/bin/{A}.bin","rb").read(),dtype="<u2")
def w(pos): return VOC[int(np.where(r==pos)[0][0])]
out="/tmp/claude-0/-home-claude/87031dea-8e1a-5bce-bdb8-99afae457c16/scratchpad"
with sync_playwright() as pw:
    br=pw.chromium.launch()
    for name,vp in [("mobile",{"width":390,"height":780}),("desktop",{"width":1000,"height":760})]:
        ctx=br.new_context(viewport=vp,device_scale_factor=1,color_scheme="dark"); p=ctx.new_page()
        p.clock.install(time=datetime.datetime(2026,11,25,12,0,0)); p.goto("file://"+ROOT+"/index.html")
        p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
        for pos in (12000,3000,800,120,18,4000):
            p.fill("#in",w(pos)); p.press("#in","Enter"); p.wait_for_timeout(80)
        p.click("#hint"); p.wait_for_timeout(100)
        p.screenshot(path=f"{out}/shot_{name}.png")
    br.close()
print(out)
