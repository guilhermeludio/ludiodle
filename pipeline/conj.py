"""Conjugação regular do português (compartilhada por 04b e 05)."""
TAB = {
 "ar": dict(pres="o as a amos ais am", pret="ei aste ou amos astes aram", imp="ava avas ava ávamos áveis avam",
            mqp="ara aras ara áramos áreis aram", subp="e es e emos eis em", subi="asse asses asse ássemos ásseis assem",
            subf="ar ares ar armos ardes arem", ger="ando", par="ado ada ados adas"),
 "er": dict(pres="o es e emos eis em", pret="i este eu emos estes eram", imp="ia ias ia íamos íeis iam",
            mqp="era eras era êramos êreis eram", subp="a as a amos ais am", subi="esse esses esse êssemos êsseis essem",
            subf="er eres er ermos erdes erem", ger="endo", par="ido ida idos idas"),
 "ir": dict(pres="o es e imos is em", pret="i iste iu imos istes iram", imp="ia ias ia íamos íeis iam",
            mqp="ira iras ira íramos íreis iram", subp="a as a amos ais am", subi="isse isses isse íssemos ísseis issem",
            subf="ir ires ir irmos irdes irem", ger="indo", par="ido ida idos idas"),
}
FUT = "ei ás á emos eis ão".split(); CON = "ia ias ia íamos íeis iam".split()
def adj(stem, ending, cls):
    c = ending[0]
    if cls == "ar":
        if c in "eé" and stem.endswith("c"): return stem[:-1] + "qu"
        if c in "eé" and stem.endswith("g"): return stem + "u"
        if c in "eé" and stem.endswith("ç"): return stem[:-1] + "c"
    else:
        if c in "oa" and stem.endswith("g") and cls in ("er", "ir") and not stem.endswith("gu"): return stem[:-1] + "j"
        if c in "oa" and stem.endswith("c") and cls == "er": return stem[:-1] + "ç"
        if c in "oa" and stem.endswith("gu") and cls == "ir": return stem[:-2] + "g"
    return stem
def conjugate(inf):
    cls = inf[-2:]; stem = inf[:-2]; t = TAB[cls]; out = set()
    for k in ("pres", "pret", "imp", "mqp", "subp", "subi", "subf", "par"):
        for e in t[k].split():
            out.add(adj(stem, e, cls) + e)
    out.add(stem + t["ger"])
    for e in FUT: out.add(inf + e)
    for e in CON: out.add(inf + e)
    return out


