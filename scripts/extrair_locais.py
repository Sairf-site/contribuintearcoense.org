"""Extrai ruas, bairros e outros lugares citados em requerimentos e indicações,
classifica o tipo de pedido e cruza pedidos repetidos.

Uso: python3 -I extrair_locais.py <propostas.json> <pasta_textos> <saida.json> [locais_anterior.json]
Sem o texto de um pedido na pasta, reaproveita locais, tipo e marcas do locais_anterior.json.

Regras (iguais para todos os autores):
- Fonte: a ementa e o texto do requerimento/indicação (PDF publicado no SAPL),
  do vocativo "Senhor Prefeito" até o fecho ("Solicita-se resposta", "Termos em que").
- Local: expressão iniciada por Rua, Avenida, Travessa, Alameda, Praça, Bairro,
  Comunidade, Distrito, Residencial, Loteamento, Estrada, Rodovia ou Vila,
  seguida de um nome com iniciais maiúsculas.
- Tipo de pedido: primeira categoria cujas palavras aparecem na ementa; se nenhuma,
  no início do texto.
- Repetição: o mesmo tipo de pedido para o mesmo local em proposições diferentes.
"""
import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

PROPOSTAS, PASTA, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    return " ".join(sem_acento(s).lower().split())


MAI = "A-ZÁÉÍÓÚÂÊÔÃÕÇÀ0-9"
PAL = rf"[{MAI}][\wÁÉÍÓÚÂÊÔÃÕÇÀáéíóúâêôãõçà'’\.-]*"
LIG = r"(?:d[aeo]s?|de|e|dos|das)"
NOME = rf"(?:{LIG}\s+)?{PAL}(?:\s+(?:{LIG}\s+)?{PAL}){{0,5}}"
TIPOS_LOCAL = {
    "rua": "Rua", "r.": "Rua", "avenida": "Avenida", "av.": "Avenida", "travessa": "Travessa",
    "alameda": "Alameda", "praca": "Praça", "bairro": "Bairro", "bairros": "Bairro",
    "comunidade": "Comunidade", "distrito": "Distrito", "residencial": "Residencial",
    "loteamento": "Loteamento", "estrada": "Estrada", "rodovia": "Rodovia", "vila": "Vila",
}
PAD = re.compile(
    r"\b(Rua|R\.|Avenida|Av\.|Travessa|Alameda|Praça|Praca|Bairros?|Comunidade|Distrito|Residencial|Loteamento|Estrada|Rodovia|Vila)\s+(" + NOME + ")")
# palavras que encerram um nome de lugar (o resto da frase não é parte do nome)
CORTE = re.compile(r"\s+(?:Bairro|Excelent|Senhor|Senhora|Prefeito|Vereador|Solicit|Requer|Ressalt|Tendo|Diante|Arcos|Considerando|CEP|Centro\b|Nº|No\b|N\.|Em\b|Por\b|Para\b|Com\b|Que\b|Onde\b|Bem\b|Na\b|No\b|Nas\b|Nos\b|Até\b|Entre\b|Próxim|Altura|Esquina|Sentido)").search
NAO_LUGAR = {"municipal", "municipais", "publica", "publicas", "federal", "estadual", "industrial i e iii"}
# endereço do timbre da Câmara e nomes genéricos que não indicam um lugar específico
IGNORAR = {("rua", "25 de dezembro"), ("bairro", "centro")}

TIPOS_PEDIDO = [
    ("Limpeza, capina e lotes", r"limpeza|capina|rocada|rocagem|entulho|lotes? (vago|sujo)|terreno baldio|mato\b|lixo"),
    ("Asfalto, buracos e calçamento", r"asfalt|pavimenta|recapeamento|tapa.buraco|buraco|calcamento|bloquete|cascalh|patrolamento|massa asfaltica"),
    ("Iluminação pública", r"iluminacao|lampada|poste|luminaria"),
    ("Trânsito e sinalização", r"sinalizacao|faixas? (de|para) pedestres?|quebra.molas|redutor|lombada|semaforo|placa|estacionamento|mao unica|rotatoria|transito"),
    ("Água, esgoto e drenagem", r"esgoto|drenagem|pluvia|bueiro|canaleta|boca de lobo|rede de agua|abastecimento|alagamento|enchente"),
    ("Árvores e poda", r"\bpoda|arvore|arboriza"),
    ("Praças, quadras e parques", r"praca|quadra|academia|parque|playground|campo de futebol|area de lazer"),
    ("Pontes e estradas rurais", r"\bponte|estrada|mata.burro|vicinal|zona rural"),
    ("Segurança e câmeras", r"camera|monitoramento|seguranca|guarda.corpo|passarela"),
    ("Saúde", r"posto de saude|unidade basica|\bubs\b|\bpsf\b|hospital|atendimento medico"),
    ("Escolas e creches", r"escola|creche|cmei|ensino"),
]


def tipo_pedido(ementa, corpo):
    for alvo in (norm(ementa), norm(corpo[:700])):
        for nome, padrao in TIPOS_PEDIDO:
            if re.search(padrao, alvo):
                return nome
    return "Outros pedidos"


def trecho_util(texto):
    t = " ".join(texto.split())
    i = t.find("Senhor Prefeito")
    if i < 0:
        i = t.find("Prefeito Municipal")
    t = t[i:] if i >= 0 else t
    for fim in ("Solicita-se resposta", "Solicita-se a resposta", "Termos em que", "Nestes termos", "Sala das Sess"):
        j = t.find(fim)
        if j > 0:
            t = t[:j]
    return t


def locais(texto):
    achados = []
    # "Rua X e Rua Y" são dois lugares
    texto = re.sub(r"\s+e\s+(?=(?:Rua|Avenida|Av\.|Travessa|Alameda|Praça|Bairro|Comunidade)\b)", " ; ", texto)
    for m in PAD.finditer(texto):
        tipo = TIPOS_LOCAL.get(norm(m.group(1)).rstrip("s") if norm(m.group(1)) == "bairros" else norm(m.group(1)), "Local")
        if norm(m.group(1)) == "bairros":
            tipo = "Bairro"
        nome = m.group(2)
        c = CORTE(nome)
        if c:
            nome = nome[:c.start()]
        nome = re.sub(r"[\s\.,;:’'-]+$", "", nome).strip()
        nome = re.sub(r"^(?:d[aeo]s?|de)\s+", "", nome, flags=re.I)
        if len(nome) < 3 or norm(nome) in NAO_LUGAR or norm(nome).startswith("federal") or re.fullmatch(r"[\d\s]+", nome):
            continue
        if (norm(tipo), norm(nome)) in IGNORAR:
            continue
        if re.match(r"bairro\b", norm(nome)):      # "Praça do Bairro X": o bairro já é capturado sozinho
            continue
        if tipo == "Vila":                          # "Vila Boa Vista" e "Bairro Vila Boa Vista" são o mesmo bairro
            tipo, nome = "Bairro", "Vila " + nome
        if norm(nome) in ("calciolandia", "calcilandia") or tipo in ("Comunidade", "Bairro") and norm(nome) == "calciolandia":
            tipo, nome = "Distrito", "Calciolândia"
        if tipo == "Bairro" and " e " in nome:          # "Bairro Novo São Judas e Juá" = dois bairros
            for parte in nome.split(" e "):
                if parte[:1].isupper() and len(parte) >= 3:
                    achados.append(("Bairro", parte.strip()))
            continue
        achados.append((tipo, nome))
    # nomes conhecidos citados sem "Bairro" ou "Distrito" antes
    if re.search(r"calciol[aâ]ndia", texto, re.I):
        achados.append(("Distrito", "Calciolândia"))
    return achados


props = json.load(open(PROPOSTAS, encoding="utf-8"))["propostas"]
pedidos = [p for p in props if p["sigla"] in ("REQ", "IND")]
ANTERIOR = {}
if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
    ANT = json.load(open(sys.argv[4], encoding="utf-8"))
    ANTERIOR = {q["id"]: q for q in ANT["pedidos"]}


grafias = defaultdict(Counter)   # chave -> grafias vistas
saida_pedidos = []
for p in pedidos:
    arq = os.path.join(PASTA, f"{p['id']}.txt")
    if not os.path.exists(arq) and p["id"] in ANTERIOR and ANTERIOR[p["id"]].get("tem_texto"):
        q = dict(ANTERIOR[p["id"]])
        q.update({k: p[k] for k in ("ementa", "vereadores", "autores", "grupo", "url", "texto", "data")})
        for k in q["locais"]:
            grafias[k][q.get("_nome_" + k, "")] += 0
        saida_pedidos.append(q)
        continue
    corpo = trecho_util(open(arq, encoding="utf-8").read()) if os.path.exists(arq) else ""
    texto = p["ementa"] + " . " + corpo
    vistos = {}
    for tipo, nome in locais(texto):
        chave = f"{norm(tipo)}|{norm(nome)}"
        grafias[chave][f"{tipo} {nome}"] += 1
        vistos[chave] = True
    na_ementa = sorted({f"{norm(t)}|{norm(n)}" for t, n in locais(p["ementa"])})
    reitera = bool(re.search(r"\breiter", norm(corpo)))
    saida_pedidos.append({
        "id": p["id"], "sigla": p["sigla"], "numero": p["numero"], "ano": p["ano"], "data": p["data"],
        "ementa": p["ementa"], "vereadores": p["vereadores"], "autores": p["autores"],
        "grupo": p["grupo"], "tipo": tipo_pedido(p["ementa"], corpo), "reitera": reitera,
        "locais": sorted(vistos), "na_ementa": na_ementa, "url": p["url"], "texto": p["texto"], "tem_texto": bool(corpo)})

nome_ant = {l["chave"]: l["nome"] for l in (ANT["lugares"] if ANTERIOR else [])}
nome_local = {}
for k in {k for q in saida_pedidos for k in q["locais"]}:
    c = Counter({g: n for g, n in grafias.get(k, Counter()).items() if g and n > 0})
    nome_local[k] = c.most_common(1)[0][0] if c else nome_ant.get(k, k.split("|", 1)[1].title())

# repetições: mesmo tipo de pedido para o mesmo local em proposições diferentes
grupos = defaultdict(list)
for q in saida_pedidos:
    if q["grupo"] == "perguntas" or q["tipo"] == "Outros pedidos":
        continue  # repetição conta só pedidos de providência com tipo identificado
    for k in q["locais"]:
        if k.startswith("bairro|") or k.split("|")[0] in ("rua", "avenida", "travessa", "alameda", "praca", "comunidade", "distrito", "residencial", "loteamento", "estrada", "vila"):
            grupos[(k, q["tipo"])].append(q)
repeticoes = []
for (k, tipo), qs in grupos.items():
    if len({q["id"] for q in qs}) >= 2:
        qs = sorted(qs, key=lambda q: q["data"])
        repeticoes.append({"local": k, "nome": nome_local[k], "tipo": tipo, "vezes": len(qs),
                           "pedidos": [q["id"] for q in qs],
                           "primeiro": qs[0]["data"], "ultimo": qs[-1]["data"]})
repeticoes.sort(key=lambda r: (-r["vezes"], r["ultimo"]), reverse=False)

uso = Counter(k for q in saida_pedidos for k in q["locais"])
lugares = sorted(({"chave": k, "nome": nome_local[k], "pedidos": n} for k, n in uso.items()),
                 key=lambda x: (-x["pedidos"], x["nome"]))

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump({"pedidos": saida_pedidos, "lugares": lugares, "repeticoes": repeticoes},
              f, ensure_ascii=False, separators=(",", ":"))

com_local = sum(1 for q in saida_pedidos if q["locais"])
print(f"{len(saida_pedidos)} pedidos; {com_local} com local; {len(lugares)} lugares; {len(repeticoes)} repetições")
print("tipos:", Counter(q["tipo"] for q in saida_pedidos).most_common())
