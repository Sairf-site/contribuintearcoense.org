"""Monta tabelas CSV por vereador a partir do JSON bruto do SAPL de Arcos-MG.

Uso: python3 -I montar_tabelas.py <pasta_raw> <pasta_saida> <data_corte AAAA-MM-DD>
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

RAW, OUT, CORTE = sys.argv[1], sys.argv[2], sys.argv[3]
SAPL = "https://sapl.arcos.mg.leg.br"
os.makedirs(OUT, exist_ok=True)


def L(nome):
    with open(os.path.join(RAW, nome + ".json"), encoding="utf-8") as f:
        return json.load(f)["registros"]


def grava(nome, cab, linhas):
    with open(os.path.join(OUT, nome + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)
    print(f"{nome}.csv: {len(linhas)} linhas")


leg = {x["id"]: x for x in L("parlamentares__legislatura")}
par = {p["id"]: p for p in L("parlamentares__parlamentar")}
partido = {p["id"]: p for p in L("parlamentares__partido")}
tipo_sessao = {t["id"]: t["nome"] for t in L("sessao__tiposessaoplenaria")}
tipo_mat = {t["id"]: t for t in L("materia__tipomaterialegislativa")}
tipo_res = {t["id"]: t["nome"] for t in L("sessao__tiporesultadovotacao")}
autores = {a["id"]: a for a in L("base__autor")}
sessoes = {s["id"]: s for s in L("sessao__sessaoplenaria")}
materias = {m["id"]: m for m in L("materia__materialegislativa")}
expediente = {e["id"]: e for e in L("sessao__expedientemateria")}
ordem = {o["id"]: o for o in L("sessao__ordemdia")}

# --- vereadores com mandato nas legislaturas cobertas pelo SAPL (19ª e 20ª)
mandatos = defaultdict(list)  # parlamentar -> [numero legislatura]
for m in L("parlamentares__mandato"):
    mandatos[m["parlamentar"]].append(leg[m["legislatura"]]["numero"])

filiacao_atual = {}
for f in sorted(L("parlamentares__filiacao"), key=lambda f: f["data"] or ""):
    if not f.get("data_desfiliacao"):
        filiacao_atual[f["parlamentar"]] = partido.get(f["partido"], {}).get("sigla", "")

LEGS = (19, 20)
vereadores = sorted(
    [p for p in par.values() if set(mandatos[p["id"]]) & set(LEGS)],
    key=lambda p: p["nome_parlamentar"])
grava("vereadores",
      ["parlamentar_id", "nome_parlamentar", "nome_completo", "partido_atual",
       "legislaturas", "ativo", "url_sapl", "foto"],
      [[p["id"], p["nome_parlamentar"], p.get("nome_completo", ""),
        filiacao_atual.get(p["id"], ""),
        ";".join(str(n) for n in sorted(set(mandatos[p["id"]]))),
        p["ativo"], f"{SAPL}/parlamentar/{p['id']}", p.get("fotografia") or ""]
       for p in vereadores])

# --- sessões
def leg_num(s):
    return leg[s["legislatura"]]["numero"]

grava("sessoes",
      ["sessao_id", "data", "numero", "tipo", "legislatura", "descricao",
       "url_video", "url_ata", "url_sapl"],
      [[s["id"], s["data_inicio"], s["numero"], tipo_sessao.get(s["tipo"], ""),
        leg_num(s), s["__str__"], s["url_video"] or "", s["upload_ata"] or "",
        f"{SAPL}/sessao/{s['id']}"]
       for s in sorted(sessoes.values(), key=lambda s: s["data_inicio"])])

# --- presença (sem duplicatas)
pres = sorted({(p["sessao_plenaria"], p["parlamentar"]) for p in L("sessao__sessaoplenariapresenca")})
grava("presenca_sessao",
      ["sessao_id", "data", "tipo_sessao", "legislatura", "parlamentar_id", "nome_parlamentar"],
      [[s, sessoes[s]["data_inicio"], tipo_sessao.get(sessoes[s]["tipo"], ""), leg_num(sessoes[s]),
        p, par[p]["nome_parlamentar"]] for s, p in pres])

pres_od = sorted({(p["sessao_plenaria"], p["parlamentar"]) for p in L("sessao__presencaordemdia")})
grava("presenca_ordem_do_dia",
      ["sessao_id", "data", "legislatura", "parlamentar_id", "nome_parlamentar"],
      [[s, sessoes[s]["data_inicio"], leg_num(sessoes[s]), p, par[p]["nome_parlamentar"]]
       for s, p in pres_od])

# --- proposições e autoria
def nome_autor(aid):
    return autores[aid]["nome"] if aid in autores else f"autor {aid}"

def autor_parlamentar(aid):
    a = autores.get(aid)
    return a["object_id"] if a and a["tipo"] == 2 else None

grava("proposicoes",
      ["materia_id", "sigla", "tipo", "numero", "ano", "data_apresentacao", "ementa",
       "autores", "em_tramitacao", "url_texto", "url_sapl"],
      [[m["id"], tipo_mat[m["tipo"]]["sigla"], tipo_mat[m["tipo"]]["descricao"],
        m["numero"], m["ano"], m["data_apresentacao"], " ".join(m["ementa"].split()),
        "; ".join(nome_autor(a) for a in m["autores"]), m["em_tramitacao"],
        m["texto_original"] or "", f"{SAPL}/materia/{m['id']}"]
       for m in sorted(materias.values(), key=lambda m: (m["data_apresentacao"] or "", m["id"]))])

autoria_ver = []
for a in L("materia__autoria"):
    pid = autor_parlamentar(a["autor"])
    if pid is None or a["materia"] not in materias:
        continue
    m = materias[a["materia"]]
    autoria_ver.append([a["materia"], tipo_mat[m["tipo"]]["sigla"], m["numero"], m["ano"],
                        m["data_apresentacao"], pid, par[pid]["nome_parlamentar"], a["primeiro_autor"]])
autoria_ver.sort(key=lambda r: (r[4] or "", r[0], r[6]))
grava("autoria_vereador",
      ["materia_id", "sigla", "numero", "ano", "data_apresentacao", "parlamentar_id",
       "nome_parlamentar", "primeiro_autor"], autoria_ver)

# --- votações
def item_pauta(r):
    if r["expediente"]:
        return "Expediente", expediente.get(r["expediente"])
    if r["ordem"]:
        return "Ordem do Dia", ordem.get(r["ordem"])
    return "", None


sessao_por_nome = {s["__str__"]: s["id"] for s in sessoes.values()}


def sessao_pelo_texto(r):
    # Alguns itens de pauta citados na votação não aparecem na API; o nome da
    # sessão vem no texto do registro: "... em <sessão> - Votação: ..."
    txt = r["__str__"].rsplit(" - Votação", 1)[0]
    if " em " in txt:
        return sessao_por_nome.get(txt.rsplit(" em ", 1)[1].strip())
    return None


votacoes = {}
sem_sessao = 0
for r in L("sessao__registrovotacao"):
    fase, item = item_pauta(r)
    sid = item["sessao_plenaria"] if item else sessao_pelo_texto(r)
    if not fase:
        fase = ""
    if not sid:
        sem_sessao += 1
    m = materias.get(r["materia"], {})
    votacoes[r["id"]] = {
        "id": r["id"], "data": r["data_hora"][:10], "sessao_id": sid or "", "fase": fase,
        "materia_id": r["materia"],
        "materia": f"{tipo_mat[m['tipo']]['sigla']} {m['numero']}/{m['ano']}" if m else "",
        "ementa": " ".join(m.get("ementa", "").split()),
        "resultado": tipo_res.get(r["tipo_resultado_votacao"], ""),
        "sim": r["numero_votos_sim"], "nao": r["numero_votos_nao"], "abst": r["numero_abstencoes"]}

print("votacoes sem sessao identificada:", sem_sessao)
grava("votacoes",
      ["votacao_id", "data", "sessao_id", "fase", "materia_id", "materia", "ementa",
       "resultado", "votos_sim", "votos_nao", "abstencoes"],
      [list(v.values()) for v in sorted(votacoes.values(), key=lambda v: (v["data"], v["id"]))])

votos = []
for x in L("sessao__votoparlamentar"):
    v = votacoes.get(x["votacao"])
    if not v:
        continue
    votos.append([x["votacao"], v["data"], v["sessao_id"], v["materia_id"], v["materia"],
                  x["parlamentar"], par[x["parlamentar"]]["nome_parlamentar"], x["voto"]])
votos.sort(key=lambda r: (r[1], r[0], r[6]))
grava("votos",
      ["votacao_id", "data", "sessao_id", "materia_id", "materia", "parlamentar_id",
       "nome_parlamentar", "voto"], votos)

# --- resumo por vereador e legislatura
sessoes_validas = defaultdict(set)  # legislatura -> sessões realizadas com presença registrada
com_presenca = {s for s, _ in pres}
for s in sessoes.values():
    if s["data_inicio"] <= CORTE and s["id"] in com_presenca:
        sessoes_validas[leg_num(s)].add(s["id"])

pres_por = Counter((leg_num(sessoes[s]), p) for s, p in pres)
autoria_por = defaultdict(Counter)
for r in autoria_ver:
    ano_leg = 20 if (r[4] or "") >= "2025-01-01" else 19
    autoria_por[(ano_leg, r[5])][r[1]] += 1
votos_por = defaultdict(Counter)
for r in votos:
    votos_por[(20 if r[1] >= "2025-01-01" else 19, r[5])][r[7]] += 1

resumo = []
for p in vereadores:
    for n in sorted(set(mandatos[p["id"]]) & set(LEGS)):
        total = len(sessoes_validas[n])
        presentes = pres_por[(n, p["id"])]
        a = autoria_por[(n, p["id"])]
        v = votos_por[(n, p["id"])]
        resumo.append([p["id"], p["nome_parlamentar"], n, presentes, total,
                       f"{100 * presentes / total:.1f}" if total else "",
                       sum(a.values()), a["REQ"], a["IND"],
                       sum(c for s, c in a.items() if s.startswith("PL") or s in ("PDL", "PRE", "PELO")),
                       sum(v.values()), v["Sim"], v["Não"], v["Abstenção"], v["Não Votou"]])
grava("resumo_por_vereador",
      ["parlamentar_id", "nome_parlamentar", "legislatura", "sessoes_presente",
       "sessoes_com_presenca_registrada", "presenca_pct", "proposicoes_autor_ou_coautor",
       "requerimentos", "indicacoes", "projetos", "votos_registrados", "sim", "nao",
       "abstencao", "nao_votou"], resumo)
