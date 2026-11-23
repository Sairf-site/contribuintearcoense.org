"""Gera data/sessoes.json para a página semanal da Câmara de Arcos-MG.

Uso: python3 -I gerar_dados_semanais.py <pasta_raw> <arquivo_saida.json> <data_hoje AAAA-MM-DD>
Lê o JSON bruto baixado por baixar_sapl.py (só dados oficiais do SAPL) e monta,
para cada sessão da 20ª legislatura, presença, pauta, resultados e votos nominais.
"""
import json
import os
import sys
from collections import defaultdict

RAW, SAIDA, HOJE = sys.argv[1], sys.argv[2], sys.argv[3]
SAPL = "https://sapl.arcos.mg.leg.br"
DESDE = "2025-01-01"  # 20ª legislatura


def L(nome):
    with open(os.path.join(RAW, nome + ".json"), encoding="utf-8") as f:
        return json.load(f)["registros"]


par = {p["id"]: p["nome_parlamentar"] for p in L("parlamentares__parlamentar")}
tipo_sessao = {t["id"]: t["nome"] for t in L("sessao__tiposessaoplenaria")}
tipo_mat = {t["id"]: t for t in L("materia__tipomaterialegislativa")}
tipo_res = {t["id"]: t["nome"] for t in L("sessao__tiporesultadovotacao")}
autores = {a["id"]: a["nome"] for a in L("base__autor")}
materias = {m["id"]: m for m in L("materia__materialegislativa")}
leg = {x["id"]: x["numero"] for x in L("parlamentares__legislatura")}

sessoes = [s for s in L("sessao__sessaoplenaria") if s["data_inicio"] >= DESDE]
ids = {s["id"] for s in sessoes}

# vereadores da 20ª legislatura (ordem alfabética do nome parlamentar)
mandatos20 = sorted({m["parlamentar"] for m in L("parlamentares__mandato") if leg[m["legislatura"]] == 20},
                    key=lambda i: par[i])
vereadores = [par[i] for i in mandatos20]

presenca = defaultdict(set)
for p in L("sessao__sessaoplenariapresenca"):
    if p["sessao_plenaria"] in ids:
        presenca[p["sessao_plenaria"]].add(par[p["parlamentar"]])

# votação por item de pauta (expediente ou ordem do dia)
votacao_por_item = {}
votacao_por_id = {}
for r in L("sessao__registrovotacao"):
    chave = ("E", r["expediente"]) if r["expediente"] else ("O", r["ordem"]) if r["ordem"] else None
    reg = {"res": tipo_res.get(r["tipo_resultado_votacao"], ""), "sim": r["numero_votos_sim"],
           "nao": r["numero_votos_nao"], "abs": r["numero_abstencoes"], "votos": {}}
    votacao_por_id[r["id"]] = reg
    if chave:
        votacao_por_item[chave] = reg
COD = {"Sim": "S", "Não": "N", "Abstenção": "A", "Não Votou": "-"}
for v in L("sessao__votoparlamentar"):
    if v["votacao"] in votacao_por_id:
        votacao_por_id[v["votacao"]]["votos"][par[v["parlamentar"]]] = COD.get(v["voto"], v["voto"])


def descreve(mid):
    m = materias.get(mid)
    if not m:
        return {"materia": f"matéria {mid}", "ementa": "", "autores": "", "url": f"{SAPL}/materia/{mid}"}
    t = tipo_mat[m["tipo"]]
    return {"materia": f"{t['descricao']} nº {m['numero']}/{m['ano']}", "sigla": t["sigla"],
            "ementa": " ".join(m["ementa"].split()),
            "autores": "; ".join(autores.get(a, "") for a in m["autores"]),
            "url": f"{SAPL}/materia/{mid}", "texto": m["texto_original"] or ""}


itens = defaultdict(list)
for fase, nome in (("E", "sessao__expedientemateria"), ("O", "sessao__ordemdia")):
    for it in L(nome):
        if it["sessao_plenaria"] not in ids:
            continue
        d = descreve(it["materia"])
        d.update({"fase": "Expediente" if fase == "E" else "Ordem do Dia", "ordem": it["numero_ordem"],
                  "resultado": it["resultado"] or ""})
        v = votacao_por_item.get((fase, it["id"]))
        if v:
            d.update({"resultado": v["res"] or d["resultado"], "placar": [v["sim"], v["nao"], v["abs"]],
                      "votos": v["votos"]})
        itens[it["sessao_plenaria"]].append(d)

saida = []
for s in sorted(sessoes, key=lambda s: s["data_inicio"], reverse=True):
    its = sorted(itens[s["id"]], key=lambda d: (d["fase"] != "Expediente", d["ordem"]))
    realizada = s["data_inicio"] <= HOJE
    pres = sorted(presenca[s["id"]])
    saida.append({
        "id": s["id"], "data": s["data_inicio"], "hora": s.get("hora_inicio") or "",
        "nome": s["__str__"], "tipo": tipo_sessao.get(s["tipo"], ""),
        "realizada": realizada, "presenca_registrada": bool(pres),
        "presentes": pres,
        "ausentes": [v for v in vereadores if v not in pres] if pres else [],
        "video": s["url_video"] or "", "ata": s["upload_ata"] or "",
        "pauta": s.get("upload_pauta") or "",
        "url": f"{SAPL}/sessao/{s['id']}", "itens": its})

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump({"gerado_em": HOJE, "fonte": SAPL + "/api/", "vereadores": vereadores,
               "sessoes": saida}, f, ensure_ascii=False, separators=(",", ":"))
print(f"{len(saida)} sessões, {sum(len(s['itens']) for s in saida)} itens -> {SAIDA} "
      f"({os.path.getsize(SAIDA) // 1024} KB)")
