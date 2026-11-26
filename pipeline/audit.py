#!/usr/bin/env python3
"""Auditoria: para cada palavra do modo, mostra as N mais próximas. uso: audit.py <modo> [n] [palavra...]"""
import sys, json, os, numpy as np
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 8; only = sys.argv[3:]
v = json.load(open(f"{R}/build/{m}/vocab.json", encoding="utf-8")); ans = set(json.load(open(f"{R}/build/{m}/answers.json"))["order"])
for A in range(len(v)):
    if only and v[A] not in only: continue
    if A not in ans: continue
    r = np.frombuffer(open(f"{R}/build/{m}/bin/{A}.bin", "rb").read(), dtype="<u2")
    print(v[A], "→", ", ".join(v[i] for i in np.argsort(r)[1:n + 1]))
