"""Baixa endpoints da API pública do SAPL da Câmara de Arcos-MG para JSON bruto.

Uso: python3 -I baixar_sapl.py <pasta_saida>
A API só pagina de forma estável com ordenação explícita (o=id); sem ela,
registros se repetem e outros somem entre páginas.
Salva um arquivo <app>__<modelo>.json por endpoint, com todos os registros
e metadados (total informado pela API, data da coleta).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = "https://sapl.arcos.mg.leg.br/api/"
PAGE_SIZE = 100
PAUSA = 1.0  # segundos entre requisições, para não sobrecarregar o servidor

ENDPOINTS = [
    # vereadores e mandatos
    "parlamentares/parlamentar", "parlamentares/legislatura",
    "parlamentares/sessaolegislativa", "parlamentares/mandato",
    "parlamentares/filiacao", "parlamentares/partido",
    "parlamentares/composicaomesa", "parlamentares/cargomesa",
    # autores
    "base/autor", "base/tipoautor",
    # sessões e presença
    "sessao/tiposessaoplenaria", "sessao/sessaoplenaria",
    "sessao/sessaoplenariapresenca", "sessao/presencaordemdia",
    "sessao/justificativaausencia", "sessao/tipojustificativa",
    # pauta e votações
    "sessao/expedientemateria", "sessao/ordemdia",
    "sessao/tiporesultadovotacao", "sessao/registrovotacao",
    "sessao/votoparlamentar", "sessao/retiradapauta",
    # proposições
    "materia/tipomaterialegislativa", "materia/materialegislativa",
    "materia/autoria",
]


def get(url, tentativas=6):
    espera = 5
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "radar-publico/0.1 (coleta de dados abertos)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tentativas - 1:
                time.sleep(espera); espera *= 2; continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i < tentativas - 1:
                time.sleep(espera); espera *= 2; continue
            raise


def baixar(endpoint, saida):
    destino = os.path.join(saida, endpoint.replace("/", "__") + ".json")
    if os.path.exists(destino):
        print(f"{endpoint}: já baixado, pulando", flush=True)
        return
    registros, page, total = [], 1, None
    while True:
        d = get(f"{BASE}{endpoint}/?page_size={PAGE_SIZE}&page={page}&o=id")
        pag = d["pagination"]
        total = pag["total_entries"]
        registros.extend(d["results"])
        if not pag.get("next_page"):
            break
        page = pag["next_page"]
        time.sleep(PAUSA)
    ids = [r["id"] for r in registros]
    if len(set(ids)) != len(ids) or len(ids) != total:
        raise RuntimeError(f"paginação inconsistente: {len(set(ids))} ids únicos, {len(ids)} baixados, {total} informados")
    with open(destino + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"endpoint": endpoint, "total_informado": total,
                   "total_baixado": len(registros),
                   "coletado_em": datetime.now(timezone.utc).isoformat(),
                   "registros": registros}, f, ensure_ascii=False)
    os.replace(destino + ".tmp", destino)
    print(f"{endpoint}: {len(registros)}/{total}", flush=True)
    time.sleep(PAUSA)


if __name__ == "__main__":
    saida = sys.argv[1]
    os.makedirs(saida, exist_ok=True)
    for ep in ENDPOINTS:
        try:
            baixar(ep, saida)
        except Exception as e:  # registra e segue para o próximo
            print(f"{ep}: ERRO {e!r}", flush=True)
