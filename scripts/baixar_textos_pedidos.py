"""Baixa o PDF de cada requerimento e indicação e salva o texto extraído.

Uso: python3 -I baixar_textos_pedidos.py <propostas.json> <pasta_textos> [locais_anterior.json]
Com locais_anterior.json, baixa só os pedidos que ainda não estavam lá.
Pula o que já foi baixado (dá para rodar de novo só para os novos).
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

PROPOSTAS, PASTA = sys.argv[1], sys.argv[2]
os.makedirs(PASTA, exist_ok=True)
props = json.load(open(PROPOSTAS, encoding="utf-8"))["propostas"]
alvo = [p for p in props if p["sigla"] in ("REQ", "IND") and p["texto"]]
if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):
    ja = {q["id"] for q in json.load(open(sys.argv[3], encoding="utf-8"))["pedidos"] if q.get("tem_texto")}
    alvo = [p for p in alvo if p["id"] not in ja]
print(f"{len(alvo)} PDFs para baixar", flush=True)

ok = falha = pulou = vazio = 0
for i, p in enumerate(alvo):
    destino = os.path.join(PASTA, f"{p['id']}.txt")
    if os.path.exists(destino):
        pulou += 1
        continue
    url = p["texto"].replace("http://", "https://")
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            for tentativa in range(4):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "radar-publico/0.1"})
                    tmp.write(urllib.request.urlopen(req, timeout=60).read())
                    tmp.flush()
                    break
                except Exception:
                    if tentativa == 3:
                        raise
                    time.sleep(5 * (tentativa + 1))
            texto = subprocess.run(["pdftotext", "-layout", tmp.name, "-"],
                                   capture_output=True, text=True).stdout
        if len(texto.strip()) < 50:
            vazio += 1
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
        ok += 1
    except Exception as e:
        falha += 1
        print(f"falha {p['id']}: {e!r}", flush=True)
    if i % 100 == 0:
        print(f"{i}/{len(alvo)}", flush=True)
    time.sleep(0.5)
print(f"fim: {ok} baixados, {pulou} já existiam, {vazio} sem texto, {falha} falhas")
