from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br=pw.chromium.launch(); p=br.new_context().new_page(); errs=[]
    p.on("pageerror",lambda e:errs.append(str(e)))
    p.goto("file://"+__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))+"/index.html"); p.wait_for_selector(".menu-card")
    print("raiz hash:",repr(p.evaluate("location.hash")),"menu:",p.locator("#menu").is_visible(),"play:",p.locator("#play").is_visible(),"tabs:",p.locator("#tabPlay").is_visible(),"cards:",p.locator(".menu-card").count())
    p.click('.menu-card[data-m=lol]'); p.wait_for_function("document.getElementById('chNum').textContent.includes('League')")
    print("jogo hash:",p.evaluate("location.hash"),"play:",p.locator("#play").is_visible(),"tabs:",p.locator("#tabPlay").is_visible())
    p.click("#logo"); p.wait_for_selector(".menu-card em")
    print("menu hash:",repr(p.evaluate("location.hash")),"menu:",p.locator("#menu").is_visible(),"tabs:",p.locator("#tabPlay").is_visible())
    p.go_back(); p.wait_for_timeout(400)
    print("voltar hash:",p.evaluate("location.hash"),"play:",p.locator("#play").is_visible())
    p.go_back(); p.wait_for_timeout(400)
    print("voltar2 hash:",repr(p.evaluate("location.hash")),"menu:",p.locator("#menu").is_visible())
    p.goto("file://"+__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))+"/index.html#onepiece/3"); p.wait_for_timeout(800); p.reload(); p.wait_for_timeout(800)
    print("deep:",p.inner_text("#chNum"),"errs",errs)
    br.close()
