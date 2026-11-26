from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br=pw.chromium.launch(); p=br.new_context(viewport={"width":390,"height":780}).new_page(); errs=[]
    p.on("pageerror",lambda e:errs.append(str(e)))
    p.goto("file://"+__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))+"/index.html#lol"); p.wait_for_function("document.getElementById('chNum').textContent.includes('#')")
    for w in ["ahri","jinx","lux","zed","yasuo","garen","teemo","vi","ekko","jax","nami","sona"]:
        p.fill("#in",w); p.press("#in","Enter"); p.wait_for_timeout(60)
    p.evaluate("window.scrollTo(0,0)"); y0=p.evaluate("scrollY")
    p.fill("#in","jinx"); p.press("#in","Enter"); p.wait_for_timeout(300)
    print("scrollY antes/depois:",y0,p.evaluate("scrollY"))
    print("ultima:",p.inner_text("#last").replace("\n"," "),"| tentativas:",p.inner_text("#sAtt"),"| input vazio:",p.input_value("#in")=="" ,"| msg:",repr(p.inner_text("#msg")))
    p.fill("#in","ahri"); p.press("#in","Enter"); p.wait_for_timeout(200)
    print("outra repetida:",p.inner_text("#last").replace("\n"," "),errs)
    br.close()
