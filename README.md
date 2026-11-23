# Contribuinte Arcoense

Site independente que mostra, com dados oficiais, o que fazem os vereadores de Arcos-MG: presença, votos, propostas, pedidos por rua e bairro, salários e despesas da Câmara.

Não tem ligação com a Câmara Municipal nem com a Prefeitura.

## Fontes

| Dado | Fonte |
|---|---|
| Sessões, presença, votos, proposições | API pública do SAPL da Câmara: https://sapl.arcos.mg.leg.br/api/ |
| Texto dos requerimentos e indicações | PDFs publicados no SAPL |
| Salário dos vereadores | Resoluções 901/2023 e 916/2026, publicadas no SAPL |
| Despesas da Câmara e diárias | Portal da transparência de Arcos: https://webapp1-arcos.cidade360.cloud/pronimtb/ |
| Resumo das reuniões | Transcrição automática do YouTube da Câmara. Não é registro oficial e vem marcado como tal no site |

Os dados do SAPL estão sob licença Creative Commons 4.0, Atribuição-CompartilhaIgual.

## Estrutura

- `index.html`: o site inteiro, em uma página com três abas.
- `data/sessoes.json`: sessões da legislatura 2025–2028, com pauta, presença e votos.
- `data/propostas.json`: todas as proposições, classificadas em grupos.
- `data/locais.json`: requerimentos e indicações ligados a ruas e bairros, e os pedidos repetidos.
- `data/resumos.json`: resumos das reuniões feitos a partir da transcrição.
- `scripts/`: os programas que baixam e montam os dados.

## Como atualizar

Requer Python 3 e `pdftotext` (poppler-utils).

```bash
python3 -I scripts/baixar_sapl.py raw/
python3 -I scripts/gerar_dados_semanais.py raw/ data/sessoes.json AAAA-MM-DD
python3 -I scripts/classificar_proposicoes.py raw/ data/propostas.json
python3 -I scripts/baixar_textos_pedidos.py data/propostas.json textos/ data/locais.json
python3 -I scripts/extrair_locais.py data/propostas.json textos/ data/locais.json data/locais.json
```

Para paginar corretamente, a API do SAPL precisa de ordenação explícita (`o=id`). Sem ela, a API repete registros entre páginas e perde outros. O `baixar_sapl.py` já usa essa ordenação e confere que cada lista veio completa.

## Regras

- **Classificação das propostas:** usa só o tipo oficial e as palavras da ementa, a mesma regra para todos os autores. A regra está explicada na aba "Propostas por tipo".
- **Pedidos por lugar:** um pedido repetido não prova que a Prefeitura ignorou o pedido anterior.
- **Contadores ao vivo:** são estimativas a partir dos valores oficiais. A forma de cálculo está no rodapé do site.
