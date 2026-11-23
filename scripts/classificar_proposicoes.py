"""Classifica as proposições da Câmara de Arcos-MG em grupos fáceis de entender.

Uso: python3 -I classificar_proposicoes.py <pasta_raw> <saida.json>

A mesma regra vale para todas as proposições, qualquer que seja o autor.
As regras são testadas em ordem; a primeira que se aplica decide o grupo.
Cada proposição guarda o número da regra e a palavra que a decidiu.
Só se usam o TIPO oficial da proposição (dado pelo SAPL) e o texto da EMENTA.
"""
import json
import os
import re
import sys
import unicodedata

RAW, SAIDA = sys.argv[1], sys.argv[2]
SAPL = "https://sapl.arcos.mg.leg.br"


def L(nome):
    with open(os.path.join(RAW, nome + ".json"), encoding="utf-8") as f:
        return json.load(f)["registros"]


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").split())


# ---------------------------------------------------------------- grupos
GRUPOS = {
    "bairros": "Pedidos de melhoria nos bairros",
    "perguntas": "Perguntas e cobranças",
    "homenagens": "Homenagens",
    "leis": "Propostas de lei",
    "outros": "Outros",
}

TIPOS_LEI = {"PLOL", "PLOE", "PLCE", "PLCL", "PLS", "PELO", "PRE"}
TIPOS_EMENDA = {"Em", "EMD", "EPL", "ES", "DEST."}
TIPOS_TRAMITE = {"RV", "RFPL"}
TIPOS_PEDIDO = {"REQ", "IND"}

# palavras (sem acento, minúsculas) — a ementa é comparada já sem acentos
P_PESAR = r"\b(voto de pesar|mocao de pesar|nota de pesar|condolencias?)\b"
P_PARABENS = r"\b(honrosa|mocao honrosa|mocao de aplauso|aplausos?|parabeniza|congratula|honra ao merito|medalha|honraria|boina de ouro|merito)\b"
P_TITULO = r"\b(cidada[o]? honorari[oa]|titulo de cidad)"
P_NOME = r"\b(denominacao|denomina|da nome|nome a rua|nome de rua)\b(?!.*\b(cargo|carreira|cargos)\b)"
P_DATA = r"\b(institui|instituir|insere|inclui)\b.*\b(dia|semana|mes|campanha|calendario)\b|\b(dia|semana) municipal\b|\bcalendario oficial\b|\bcampanha municipal\b"
P_MOCAO_POSICAO = r"\bmocao de (apelo|apoio|repudio)\b"

P_PERGUNTA_INICIO = (r"^(informacoes?|esclarecimentos?|copias?|relacao|relatorios?|cronogramas?|gastos|valor(es)?|"
                     r"previsao|saldo|prestacao de contas|cumprimento|convocacao|notificacao|ilegalidade|criterios|"
                     r"situacao|listagem|despesas com|levantamento|quantitativo|dados|andamento|explicac|questionamento|fiscalizacao|"
                     r"apuracao|providencias sobre|posicionamento|justificativa|detalhamento|demonstrativo|"
                     r"pedido de informac|solicitacao de informac|solicitacao de copia|solicitacao de esclarec)")
P_PERGUNTA_MEIO = r"\b(informacoes|esclarecimentos|copias? d[aoe]s?|prestacao de contas|pedido de informac)\b"

P_LEI_PEDIDO = r"\b(projeto de lei|legislacao|\blei\b|regulamentacao|regulamentar|estatuto)"

P_BAIRRO = (r"\b(rua|ruas|avenida|av\.|travessa|bairros?|praca|pracas|ponte|pontes|passarela|estrada|estradas|"
            r"calcada|calcadas|calcamento|asfalt\w*|pavimenta\w*|recapeamento|tapa.buraco|buraco|bueiro|"
            r"drenagem|esgoto|rede de agua|rede pluvial|galeria|iluminacao|poste|lampada|limpeza|capina|"
            r"roçada|rocada|poda|entulho|lixo|lixeira|conteiner|cacamba|ciclofaixa|ciclovia|faixa de pedestre|"
            r"redutor|quebra.molas|lombada|semaforo|sinalizacao|placa|abrigo|ponto de onibus|guarda.corpo|"
            r"academia ao ar livre|quadra|campo|parque|cemiterio|distrito|comunidade|zona rural|"
            r"canaletas?|pluvia\w*|escoamento|abrigos|passagem elevada|pedestres?|arboriza\w*|plantio de arvores|arvores|barraginhas?|mata.burros?|"
            r"calciolandia|ilha|corrego|rio|muro|mina d|banheiro|playground|rotatoria|trevo|via publica|"
            r"vias publicas|espaco publico|terreno|lote vago|matagal|caixa d.agua|reservatorio|poco artesiano)\b")

ORCAMENTO = r"\b(credito|orcament|diretrizes orcamentarias|plano plurianual|estima a receita|suplementar|lei orcamentaria|ldo|loa|ppa)\b"


def norm_com_mapa(s):
    """Texto sem acentos, minúsculo, espaços simples; e a posição original de cada caractere."""
    out, mapa, ant_esp = [], [], True
    for i, ch in enumerate(s):
        for c in unicodedata.normalize("NFD", ch.lower()):
            if unicodedata.category(c) == "Mn":
                continue
            if c.isspace():
                if ant_esp:
                    continue
                c, ant_esp = " ", True
            else:
                ant_esp = False
            out.append(c); mapa.append(i)
    return "".join(out), mapa


def classificar(sigla, ementa):
    """Devolve (grupo, subgrupo, regra, palavra) — a palavra como está escrita na ementa."""
    e, mapa = norm_com_mapa(ementa)

    def acha(padrao):
        m = re.search(padrao, e)
        if not m:
            return None
        a, b = m.start(), m.end()
        trecho = ementa[mapa[a]:mapa[b - 1] + 1] if b > a else m.group(0)
        trecho = " ".join(trecho.split()).strip(" ,.;:")
        return trecho if len(trecho) <= 60 else trecho[:57] + "…"

    # 1. Tramitação interna: emendas, vetos e redação final -> Outros
    if sigla in TIPOS_EMENDA:
        sub = "Emendas ao orçamento (destino de verba)" if sigla == "EMD" else "Emendas a projetos"
        return "outros", sub, 1, f"tipo {sigla}"
    if sigla in TIPOS_TRAMITE:
        return "outros", "Vetos e redação final", 1, f"tipo {sigla}"

    # 2. Requerimentos e indicações que pedem informação vêm antes de tudo
    if sigla in TIPOS_PEDIDO and ((w := acha(P_PERGUNTA_INICIO)) or (w := acha(P_PERGUNTA_MEIO))):
        return "perguntas", "Perguntas e cobranças à Prefeitura", 2, w

    # 3. Homenagens (qualquer tipo)
    if (w := acha(P_PESAR)):
        return "homenagens", "Pesar", 3, w
    if (w := acha(P_TITULO)):
        return "homenagens", "Título de cidadão", 3, w
    if (w := acha(P_NOME)) and not (sigla in TIPOS_PEDIDO and "placa" in e):
        return "homenagens", "Nome de rua e de lugares públicos", 3, w
    if (w := acha(P_PARABENS)):
        return "homenagens", "Parabéns e reconhecimento", 3, w
    if sigla != "REQ" and (w := acha(P_DATA)):
        return "homenagens", "Data comemorativa", 3, w

    # 4. Moções de apoio ou repúdio -> Outros
    if (w := acha(P_MOCAO_POSICAO)):
        return "outros", "Moções de apoio ou de repúdio", 4, w

    # 5. Projetos de lei e de resolução (tipo oficial)
    if sigla in TIPOS_LEI:
        if sigla in ("PELO", "PRE"):
            return "leis", "Lei Orgânica e regras internas da Câmara", 5, f"tipo {sigla}"
        if (w := acha(ORCAMENTO)):
            return "leis", "Orçamento e dinheiro público", 5, w
        if (w := acha(r"\butilidade publica\b")):
            return "leis", "Utilidade pública de entidades", 5, w
        return "leis", "Novas leis e mudanças em leis", 5, f"tipo {sigla}"

    # 6. Outros decretos legislativos (ex.: contas da Prefeitura)
    if sigla == "PDL":
        if (w := acha(r"\bcontas\b")):
            return "outros", "Julgamento das contas da Prefeitura", 6, w
        return "outros", "Outros decretos legislativos", 6, "tipo PDL"

    # 7-9. Demais requerimentos e indicações: sugestão de lei, melhoria no bairro ou outro pedido
    if sigla in TIPOS_PEDIDO:
        if (w := acha(P_LEI_PEDIDO)):
            return "leis", "Sugestões de lei ao prefeito", 7, w
        if (w := acha(P_BAIRRO)):
            return "bairros", "Obras, limpeza e manutenção", 8, w
        return "outros", "Outros pedidos à Prefeitura (serviços, servidores, programas)", 9, "nenhuma das anteriores"

    return "outros", "Outros", 10, f"tipo {sigla}"


tipo_mat = {t["id"]: t for t in L("materia__tipomaterialegislativa")}
autores = {a["id"]: a for a in L("base__autor")}
par = {p["id"]: p["nome_parlamentar"] for p in L("parlamentares__parlamentar")}
leg = {x["id"]: x["numero"] for x in L("parlamentares__legislatura")}
v20 = sorted({par[m["parlamentar"]] for m in L("parlamentares__mandato") if leg[m["legislatura"]] == 20})
v19 = sorted({par[m["parlamentar"]] for m in L("parlamentares__mandato") if leg[m["legislatura"]] == 19})


tipo_autor = {t["id"]: norm(t["descricao"]) for t in L("base__tipoautor")}


def origem(aid):
    a = autores.get(aid)
    if not a:
        return "Autor não registrado"
    if a["tipo"] == 2:
        return "Vereador"
    t, nome = tipo_autor.get(a["tipo"], ""), norm(a["nome"])
    if "executivo" in t or "executivo" in nome or "prefeit" in nome:
        return "Prefeitura"
    return "Mesa, comissões e órgãos da Câmara"


props = []
for m in L("materia__materialegislativa"):
    if "treinamento de votacao" in norm(m["ementa"]):  # registros de teste do sistema, de 2013
        continue
    t = tipo_mat[m["tipo"]]
    g, sub, regra, palavra = classificar(t["sigla"], m["ementa"])
    vers = [par[autores[a]["object_id"]] for a in m["autores"]
            if a in autores and autores[a]["tipo"] == 2 and autores[a]["object_id"] in par]
    props.append({
        "id": m["id"], "sigla": t["sigla"], "tipo": t["descricao"], "numero": m["numero"], "ano": m["ano"],
        "data": m["data_apresentacao"] or "", "ementa": " ".join(m["ementa"].split()),
        "autores": [autores[a]["nome"] if a in autores else "" for a in m["autores"]],
        "vereadores": vers, "origem": sorted({origem(a) for a in m["autores"]}) or ["Autor não registrado"],
        "grupo": g, "sub": sub, "regra": regra, "palavra": palavra,
        "url": f"{SAPL}/materia/{m['id']}", "texto": m["texto_original"] or ""})

props.sort(key=lambda p: (p["data"], p["id"]), reverse=True)
with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump({"grupos": GRUPOS, "vereadores20": v20, "vereadores19": v19, "propostas": props},
              f, ensure_ascii=False, separators=(",", ":"))

from collections import Counter
print(Counter(GRUPOS[p["grupo"]] for p in props))
for (g, s), n in sorted(Counter((p["grupo"], p["sub"]) for p in props).items()):
    print(f"  {GRUPOS[g]:32s} {s:60s} {n}")
