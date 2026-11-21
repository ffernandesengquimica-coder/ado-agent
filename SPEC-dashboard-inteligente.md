# Spec: Dashboard Inteligente v1 — o agente dentro do painel

> Origem: [docs/ideas/dashboard-inteligente.md](docs/ideas/dashboard-inteligente.md) · Sessão: RUN_LOG-Felipe-2026-11-11-20-07.md
> Status: **aprovada em 2026-11-11 · D1–D7 implementadas em 2026-11-11; falta a conferência no navegador e a revisão do apresentador (D8)**
> Reaproveita: Radar ([SPEC-radar-de-datas.md](SPEC-radar-de-datas.md)), Riscos ([SPEC-agente-de-riscos.md](SPEC-agente-de-riscos.md)) e a infraestrutura de LLM da Explicação ([SPEC-explicacao-de-indicadores.md](SPEC-explicacao-de-indicadores.md)).

## Objective

Transformar o painel semanal num dashboard que **conduz a reunião da diretoria**. O painel é
apresentado pelo usuário, que roda tudo na própria máquina. O agente faz quatro coisas:
- destaca o que pede atenção;
- explica o que se clica;
- resume o recorte filtrado;
- responde perguntas.

**Restrições mantidas:**
- MVP estático, sem servidor e sem agendamento;
- nenhuma chave no HTML;
- ADO só leitura;
- LLM só redige fatos já calculados, com pessoas anonimizadas e validador de números.

**Usuários:**
- **Apresentador:** gera o painel, conduz a reunião e usa o modo apresentador.
- **Diretoria:** vê a tela.

### Decisões fechadas (one-pager → spec)

| Questão | Decisão |
|---|---|
| Onde fica a pauta | **Fixa no topo**, acima das abas: é o roteiro da reunião |
| Histórico das perguntas | Acumulam em `relatorios/perguntas-AAAA-MM-DD.csv`. O HTML mostra as do dia; o histórico são os arquivos |
| Radar antes de 28/12 | Pode ser citado. Todo texto do LLM cuja entrada incluiu números do Radar ganha o selo **"previsão em validação"** enquanto `RADAR_APROVADO = False` |
| Crescimento de escopo | **Pré-requisito.** O motivo do Radar passa a usar a regra dos Riscos: novos ÷ itens que existiam há 4 semanas, mín. 5 itens; acima de 300% aparece "mais que quadruplicou". Só o texto do motivo muda: seção, chance e o modelo v3 ficam intactos |
| Explicar ao clicar | **Números, cartões, células e barras:** o clique continua filtrando. A caixa "Leitura do agente" da aba mostra a explicação do filtro ativo (por regra) e o resumo do recorte (LLM). **Epic:** clicar no título abre um painel lateral |

## Componentes

### 1. Pauta da semana (topo; LLM, escolha por regra)

- **Candidatos:** Epics com pelo menos um risco Escalar.
- **Pontuação** (soma):
  - +3 se algum risco do Epic está `novo` ou `piorou`;
  - +2 se há gatilho de dependência entre programas;
  - +1 por gatilho adicional.
- **Desempate:** gravidade (materializado > crítico > …), depois data alvo mais próxima.
- **Pontos:** os **5 primeiros** (ou todos, se houver menos).
- **Texto:** por ponto, o LLM escreve **1 frase de até 180 caracteres**, uma manchete do que mudou e
  por que importa. Recebe os fatos do Epic (os mesmos da causa provável) mais o movimento de cada
  risco. Não recomenda ação.
- **Fallback:** se o texto for inválido ou não houver LLM, a manchete sai por regra:
  `#id título — gatilhos`.
- **Clique:** abre a aba Riscos filtrada no Epic.

### 2. Perguntas que vocês deveriam fazer hoje (topo, recolhível; perguntas por regra, respostas pelo LLM)

São três perguntas fixas, com fatos escolhidos por regra:
1. **"Qual programa concentra mais riscos críticos?"** Fatos: ranking de programas por riscos
   Crítico, com Escalar e materializados.
2. **"Quais dependências entre programas estão travando Epics?"** Fatos: riscos DEPENDENCIA com
   gatilho entre programas, com as evidências. Se não houver nenhum, a resposta é fixa:
   "Nenhuma nesta semana".
3. **"O que piorou desde o último registro?"** Fatos: riscos `novo` e `piorou`, com criticidade e
   evidência (no máximo 15, os mais graves).

O LLM escreve de 2 a 4 frases, até 600 caracteres, por resposta.

### 3. Leitura do agente (uma caixa por aba, abaixo dos cartões)

Reage aos filtros da aba, sem LLM em tempo de uso: os textos vêm prontos no HTML, num
`<script type="application/json">`. A caixa tem duas partes:
- **Significado (por regra):** uma linha por filtro ativo. Exemplo para o filtro "Crítico":
  "45 riscos Críticos = probabilidade alta × impacto alto; 20 com Escalar". Há textos prontos
  para todos os valores de filtro que existem no painel.
  - *Radar:* seção, programa, mês.
  - *Riscos:* criticidade, Escalar, materializado, célula da matriz, categoria, programa, Epic.
- **Resumo do recorte (LLM):** com programa ativo, o resumo do programa; com categoria ativa e
  sem programa, o resumo da categoria; senão, o resumo geral.
  - São 1 resumo geral + 1 por programa + 1 por categoria (18 em 11/11).
  - Cada resumo tem de 2 a 4 frases, até 600 caracteres.
  - **Fatos do recorte:** riscos por criticidade, Escalar, materializados, movimento e seções do
    Radar dos Epics do recorte, mais os 3 Epics mais graves com as evidências.

### 4. Painel lateral do Epic

Clicar no título de um Epic, em qualquer aba, abre um painel à direita com:
- título, área e data alvo;
- dono;
- situação no Radar (seção e chance, com selo);
- riscos do Epic (criticidade e evidência);
- **causa provável**, quando existe.

O painel fecha com Esc ou ×. Os dados vêm do mesmo JSON embutido.

### 5. Modo apresentador

```powershell
.venv\Scripts\python -m radar perguntar "por que Obras Sul piorou?" [--hoje AAAA-MM-DD] [--extracao ...]
```

1. Lê os `radar-`/`riscos-AAAA-MM-DD.csv` do dia (padrão: hoje). Se não existirem, pede para
   rodar `radar relatorio` antes.
2. **Recorte por regra**, sem acento e sem diferenciar maiúsculas, nesta ordem:
   - `#id` ou número que seja um Epic aberto → fatos do Epic;
   - nome ou sigla de programa (iniciais, ex.: "PDB") → fatos do programa;
   - nome de categoria → fatos da categoria;
   - senão → fatos gerais.
3. Anonimiza os fatos e também a pergunta (qualquer dono ou responsável conhecido vira "Pessoa X").
   Chama o LLM, sem cache, porque cada pergunta é única, e valida. A resposta tem de 1 a 5 frases,
   até 700 caracteres. Se os fatos não respondem, o LLM diz "Os dados do painel não respondem a isso".
4. Imprime a resposta no terminal (com nomes reais) e acrescenta uma linha em
   `perguntas-AAAA-MM-DD.csv` com:
   - `hora`, `pergunta` (anonimizada) e `recorte`;
   - `status`, `motivo` e `resposta` (anonimizada);
   - `tokens`.
5. Gera o painel de novo (`radar relatorio` interno, que só reaproveita o cache), e a seção
   **"Perguntas desta reunião"** mostra as válidas do dia, a mais recente primeiro.

Uma resposta rejeitada ou com erro aparece só no terminal, com o motivo, e não entra no HTML.

_Ajustes da implementação (2026-11-11):_
- O CSV de perguntas guarda a pergunta e a resposta como o apresentador as viu, com os nomes reais. É um
  arquivo local, como o `riscos-*.csv`, que já tem os donos. Para a OpenAI vai só a versão anonimizada.
- `#id` explícito vale para qualquer Epic. Número solto só vale com 3 dígitos ou mais. Sigla de programa
  só vale com 3 letras ou mais ("os" não é Obras Sul).
- O selo "previsão em validação" só aparece se o texto **usa** termos do Radar (chance, vão atrasar,
  término…), e não apenas porque a entrada tinha o Radar. Sem isso, "Os dados do painel não respondem a
  isso" saía com selo.
- Recorte sem movimento manda `"sem mudanças"`, em vez de omitir o campo (o LLM escrevia "os fatos não
  informam o movimento"). Com isso, o prompt de resumo foi para a versão `d2`.

### Garantias herdadas (valem para todo texto do LLM)

- Fatos anonimizados.
- Validador: números, datas, `#id` e pessoas precisam estar nos fatos; limites de tamanho por tipo.
- Cache por hash (tipo + versão do prompt + modelo + fatos) para a pauta, as perguntas sugeridas
  e os resumos. As chaves da causa provável não mudam.
- Falha → fallback (pauta por regra) ou texto omitido. O painel sempre sai.

## Tech Stack

O mesmo: Python 3.12, `requests`, stdlib e `pytest`. **Nenhuma dependência nova.** O JS é
inline e sem bibliotecas: estende o script atual de filtros e abas.

## Commands

```powershell
.venv\Scripts\python -m radar relatorio [--sem-llm]          # painel + textos do agente (cache primeiro)
.venv\Scripts\python -m radar perguntar "pergunta" [--hoje AAAA-MM-DD]
.venv\Scripts\python -m pytest -q
```

Arquivos novos em `relatorios/`:
- `textos-AAAA-MM-DD.csv`: pauta, perguntas sugeridas e resumos. Colunas: `data, tipo, alvo,
  chave, modelo, prompt_versao, status, motivo, tokens_entrada, tokens_saida, texto`;
- `perguntas-AAAA-MM-DD.csv`.

O `narrativas-*.csv` continua igual.

## Project Structure

```
radar/
  motivos.py          → crescimento de escopo alinhado aos Riscos (pré-requisito)
  relatorio.py        → pauta + perguntas sugeridas + "Perguntas desta reunião" no topo; caixa
                        "Leitura do agente" na aba Radar; painel lateral; JSON embutido; JS estendido
  __main__.py         → `relatorio` gera os textos; novo subcomando `perguntar`
explicacao/
  llm.py              → núcleo genérico: pedido (tipo, alvo, sistema, fatos, limites) → cache → cliente → validador
  narrativas.py       → causa provável passa a usar o núcleo (chaves e CSV iguais)
  recortes.py         → fatos por recorte (geral, programa, categoria) e por Epic (qualquer Epic aberto)
  pauta.py            → escolha por regra + fatos dos pontos + manchete de fallback
  sugeridas.py        → as 3 perguntas e seus fatos
  leitura.py          → textos por regra do significado de cada filtro (Radar e Riscos)
  perguntar.py        → recorte da pergunta, chamada, CSV de perguntas
  prompt.py           → + prompts e versões por tipo (pauta, sugerida, resumo, pergunta)
  validador.py        → limites por tipo
riscos/
  painel.py           → caixa "Leitura do agente" na aba Riscos; título do Epic abre o painel lateral
tests/
  test_explicacao_recortes.py, test_explicacao_pauta.py, test_explicacao_leitura.py,
  test_explicacao_perguntar.py, test_explicacao_llm.py, test_relatorio.py (+), test_motivos.py (+)
```

## Code Style

O mesmo das entregas anteriores. Textos por regra são funções puras sobre as linhas. Todo
texto exibido passa por `html.escape`, e o JSON embutido usa `json.dumps` com `<` escapado.

```python
@dataclass(frozen=True)
class Pedido:
    tipo: str            # "pauta" | "sugerida" | "resumo" | "pergunta" | "causa"
    alvo: str            # "90004", "programa:Rede Norte", "geral", ...
    fatos: dict
    usa_radar: bool      # True → selo "previsão em validação" enquanto RADAR_APROVADO = False
```

## Testing Strategy

Tudo sem rede, com o cliente falso.
- **pauta:** pontuação, desempate, limite de 5, fallback por regra.
- **recortes:** contagens de um cenário sintético por programa e categoria; Epic qualquer.
- **leitura:** um texto por valor de filtro existente; números batem com a tabela.
- **perguntar:**
  - recorte por `#id`, nome de programa, sigla, categoria e caso geral;
  - pergunta com nome de pessoa sai anonimizada;
  - CSV acumula;
  - rejeitada não entra no HTML.
- **llm:** a chave da causa provável é idêntica à de antes (as narrativas atuais continuam no
  cache); tipos diferentes com os mesmos fatos dão chaves diferentes.
- **relatorio:**
  - pauta no topo;
  - JSON embutido válido e com `<` escapado;
  - selo só onde `usa_radar`;
  - "Perguntas desta reunião" só com as válidas;
  - painel sai sem LLM.
- **motivos:** a regra de crescimento é a mesma dos Riscos (o caso 90011 dá o mesmo % nas duas abas).
- Os 209 testes atuais continuam passando, com ajuste só nos que testam o texto antigo do motivo.

## Boundaries

- **Always:**
  - painel sai sem LLM;
  - todo texto do LLM validado e escapado;
  - pessoas anonimizadas, inclusive na pergunta;
  - selo quando a entrada usou o Radar.
- **Ask first:**
  - servidor ou chat ao vivo;
  - mandar à OpenAI campos novos (descrição, comentários);
  - expandir a causa provável além do Escalar;
  - tirar o selo do Radar (só depois da T8).
- **Never:**
  - chave no HTML;
  - escrita no ADO;
  - agendamento;
  - LLM decidindo pauta, cor, chance ou criticidade;
  - mudar o modelo v3 do Radar.

## Success Criteria

1. O motivo de crescimento de escopo do Radar e a evidência ESCOPO dos Riscos dão o mesmo % para
   o mesmo Epic. O `radar-*.csv` muda só na coluna `motivos`. ✅ _90011: 53% nas duas abas; 44 linhas mudaram só em `motivos`._
2. O painel abre com a pauta (3 a 5 pontos) no topo. Cada ponto leva à aba Riscos filtrada no Epic.
3. As 3 perguntas sugeridas aparecem respondidas, ou com a resposta fixa quando não há dados.
4. Filtrar um programa ou categoria troca o resumo da caixa "Leitura do agente". Cada filtro ativo
   mostra o significado por regra, com números que batem com a tabela filtrada.
5. Clicar no título de um Epic abre o painel lateral, que fecha com Esc.
6. ✅ _4 perguntas reais em 2 a 4 s, recortes certos, "não respondem" para orçamento._ `radar perguntar` responde em menos de 30 s, grava o CSV e atualiza o HTML. As perguntas válidas
   do dia aparecem em "Perguntas desta reunião".
7. Sem `OPENAI_MODEL`: pauta por regra, leitura por regra, sem resumos nem respostas, e nenhum erro.
8. Segunda execução de `radar relatorio` com a mesma entrada: **zero chamadas** e mesmo HTML. ✅
9. Primeira execução com LLM: menos de 60 s extras (cerca de 26 textos novos). ✅ _33 s, 26/26 válidos._
10. Nenhum nome de pessoa em nenhum payload (teste) e nenhuma chave no HTML.
11. `pytest -q` passa inteiro, sem rede. ✅ _232 testes._
12. **Revisão humana:** o apresentador testa 10 perguntas reais e revisa pauta e resumos. Até lá, a
    pauta, as perguntas sugeridas e os resumos levam o aviso "em validação" (`AGENTE_APROVADO = False`).

## Open Questions

Nenhuma bloqueante. A ser observado na 1ª reunião: o apresentador filtra durante a reunião? A
pauta por regra bate com o que ele destacaria?
