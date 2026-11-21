# Spec: Agente de Riscos v1 — registro sintético de riscos

> Origem: [docs/ideas/agente-de-riscos.md](docs/ideas/agente-de-riscos.md) · Sessão: RUN_LOG-Felipe-2026-11-05-17-35.md
> Status: **aprovada em 2026-11-05 · v1 concluída e liberada para a diretoria em 2026-11-05 (R7)**
> Reaproveita o Radar de Datas ([SPEC-radar-de-datas.md](SPEC-radar-de-datas.md)): mesmas definições de Epic, escopo, restante, ritmo e entrada.

## Objective

Dar à diretoria um **registro de riscos do Atlas, classificado e com dono**, sem que ninguém
precise mantê-lo. Hoje não existe registro de riscos em uso no ADO: os 71 work items `Risk`
estão soltos e incompletos (confirmado pelo usuário). O agente deduz os riscos dos sinais de
entrega e mantém o próprio registro. **O ADO continua intocado.**

- **Usuário:** diretoria / executivo. Lê o painel semanal, junto com o Radar.
- **Sucesso:**
  - achar riscos que ninguém registrou;
  - todo risco com classificação e dono;
  - escalar a tempo o que precisa de decisão;
  - ver a tendência semana a semana.
- **Como:** regras explícitas sobre os CSVs do `extrator`, sem o Monte Carlo do Radar e sem
  LLM. Cada risco traz a evidência em uma frase com números.
- **MVP estático:** o painel é gerado à mão (`python -m extrator` + `radar relatorio`), sem
  nenhum agendamento. Movimento e "saíram do registro" só aparecem se alguém rodar de novo.
- **Antes de ir para a diretoria:** revisão humana do painel (ver Success Criteria 9). Esse
  portão é independente do teste do Radar em 28/12.

### Definições

| Termo | Definição |
|---|---|
| Epic avaliado | Igual ao Radar: `tipo = Epic`, estado ∉ {Done, Removed} |
| Programa | 2º nível da área (`Atlas\<programa>\...`); a raiz `Atlas` conta como programa "Atlas" |
| Epic de um item | Epic mais próximo acima do item na hierarquia (`caminho_ids`); o próprio Epic para um Epic |
| Item aberto | estado ∉ {Done, Removed, Closed} |
| Risco | Um par **Epic × categoria**, com id estável `R-<epic_id>-<CATEGORIA>` (ex.: `R-90006-PRAZO`). No máximo um risco por categoria por Epic; se várias regras da mesma categoria disparam, vale a de maior probabilidade, e a evidência lista todas |
| Estado | `aberto` (ainda evitável) ou `materializado` (já aconteceu: só Prazo com data alvo vencida) |
| Dono | `responsavel_nome` do Epic; vazio = **sem dono** |
| Dependência | Par (predecessor P, sucessor S) dado por um link `Successor` de P para S em `workitem_links.csv`, com P e S abertos e P **fora** do Epic de S. O Epic de S "depende de" P |
| Dependência entre programas | Programa de P ≠ programa de S |
| Dependentes de um Epic E | Nº de Epics distintos que dependem de algum item de E |

### Categorias e probabilidade (por regra)

Um risco só existe quando a regra da categoria dispara, e sempre com probabilidade **alta** ou
**média**. As regras de Prazo usam a razão de ritmo e o ritmo do Radar, ambos determinísticos.
A probabilidade do Monte Carlo não entra.

| Categoria | Alta | Média | Evidência (exemplo) |
|---|---|---|---|
| **PRAZO** | data alvo futura e: razão de ritmo ≥ 1,5; **ou** parado (restante > 0 e nenhuma conclusão nas últimas 4 semanas); **ou** ritmo zero na janela com restante > 0 | data alvo futura e 1,0 ≤ razão < 1,5 | "precisa entregar 2,1× mais rápido; sem entregas há 5 semanas" |
| PRAZO materializado | data alvo < hoje → estado `materializado`, probabilidade tratada como alta | — | "data alvo vencida há 6 semanas; 14 itens restantes" |
| **DEPENDENCIA** | algum P com data alvo vencida, **ou** cujo Epic tem PRAZO materializado | algum P cujo Epic tem PRAZO alta | "depende de #1234 (Feature, Obras Sul), vencida em 10/10/2026" |
| **CAPACIDADE** | restante > 0 e ≥ 50% do restante sem responsável | 20% a 50% | "12 de 14 itens restantes sem responsável" |
| **ESCOPO** | data alvo futura e escopo vazio ("sem escopo detalhado"); **ou** crescimento ≥ 50% | crescimento entre 20% e 50% | "escopo cresceu 35% nas últimas 4 semanas (+9 itens)" |
| **QUALIDADE** | Faults abertas sob o Epic + Bugs abertos do escopo ≥ 2 **e** ≥ 50% do restante | ≥ 2 e entre 20% e 50% do restante | "7 Faults e 2 Bugs abertos = 45% do restante" |
| **GOVERNANCA** | — | Epic aberto sem data alvo | "Epic sem data alvo" |

Os limiares de 4 semanas, 20% e 1,5× são os mesmos dos motivos do Radar.

**Crescimento** = itens de escopo criados nas últimas 4 semanas ÷ itens de escopo que já existiam
4 semanas atrás. Só vale para Epics com **≥ 5 itens** naquela época; Epic mais novo que isso
está sendo detalhado, não crescendo. _(Ajustado no planejamento em 2026-11-05: medido contra o
escopo atual, 75 Epics disparavam, a maioria Epics novos; com esta regra, 34.)_

### Impacto e criticidade

**Impacto** (por Epic, vale para todos os riscos dele):

| Impacto | Regra |
|---|---|
| alto | restante ≥ 30 **ou** dependentes ≥ 2 |
| médio | restante ≥ 10 **ou** dependentes = 1 **ou** escopo vazio (tamanho desconhecido) |
| baixo | demais |

Não há campo de valor de negócio confiável: `area_valor` = "Business" e `prioridade` = 2 em
praticamente todos os Epics. Por isso o impacto usa tamanho e dependentes.

Cortes de 30 e 10 itens **confirmados no planejamento** (2026-11-05): restante por Epic tem
mediana 7, p75 22, p90 49; 42 Epics ≥ 30 e 109 ≥ 10. Cortes 40/15 mudariam pouco o Escalar (35 → 32).

**Criticidade** (matriz probabilidade × impacto):

| | impacto alto | impacto médio | impacto baixo |
|---|---|---|---|
| **prob. alta** | Crítico | Alto | Médio |
| **prob. média** | Alto | Médio | Baixo |

### Escalar (gatilhos)

Um risco ganha a marca **Escalar** se dispara pelo menos um gatilho, e o painel lista quais:

| Gatilho | Regra |
|---|---|
| Data próxima | data alvo do Epic entre hoje e hoje + 28 dias **e** criticidade Crítico |
| Dependência entre programas | DEPENDENCIA com probabilidade alta e pelo menos um P de outro programa |
| Atraso grande | PRAZO `materializado` com data alvo < hoje − 8 semanas |
| Sem dono | Epic sem dono **e** criticidade Crítico |

Medido no planejamento (dados de 05/11/2026): **35 riscos em 26 Epics** levam a marca Escalar
(data próxima 21, dependência entre programas 7, sem dono 5, atraso grande 4). Decisão: regras
mantidas, e o painel **agrupa o Escalar por Epic** (uma linha por Epic, com os riscos e gatilhos
dele). Alvo: até cerca de 25 Epics por semana.
_Implementação (Checkpoint B, 2026-11-05): 360 riscos em 239 Epics; Escalar em **37 riscos / 26 Epics**
(data próxima 23 · dependência entre programas 7 · sem dono 5 · atraso grande 4; um risco pode ter mais de um)._

### Movimento semanal

Compara com o `relatorios/riscos-*.csv` mais recente com data anterior a `hoje`. Se não houver
nenhum, todos os riscos são "novo".

| Movimento | Regra |
|---|---|
| novo | id não estava no anterior |
| piorou | criticidade subiu, **ou** estado passou de `aberto` para `materializado` |
| melhorou | criticidade desceu |
| igual | mesma criticidade e mesmo estado |
| saiu | estava no anterior e não está mais. Motivo: "Epic fechado" (Epic Done ou Removed) ou "sinal desapareceu". Aparece numa seção própria, não no registro |

## Tech Stack

Igual ao Radar:
- Python 3.12 no `.venv`;
- `numpy` (só pelo `radar.previsao`), `pytest`;
- stdlib `csv` e `html.escape`.

**Nenhuma dependência nova.** Entrada: os CSVs do `extrator`, agora também
`workitem_links.csv`, só as linhas `nome_rel = Successor`. **Nenhuma chamada ao ADO.**

## Commands

```powershell
# relatório semanal (Radar + Riscos, um único comando)
.venv\Scripts\python -m radar relatorio
.venv\Scripts\python -m radar relatorio --extracao out\Atlas\20261105T003131Z --hoje 2026-11-05

# testes
.venv\Scripts\python -m pytest -q
```

`radar relatorio` passa a gravar três arquivos:
- `radar-AAAA-MM-DD.csv` (como hoje);
- `riscos-AAAA-MM-DD.csv` (novo);
- `radar-AAAA-MM-DD.html`, com as abas Radar e Riscos.

## Project Structure

```
radar/
  dados.py           → + Faults por Epic, Epic de cada item, dependências (links Successor)
  relatorio.py       → painel HTML ganha abas: Radar | Riscos
  __main__.py        → `relatorio` também gera o registro de riscos
riscos/
  __init__.py
  regras.py          → as 6 categorias: Epic → riscos (probabilidade + evidência)
  classificacao.py   → impacto, matriz de criticidade, gatilhos de Escalar
  registro.py        → monta o registro, id estável, movimento vs. CSV anterior, linhas do CSV
  painel.py          → HTML da aba Riscos (usa o mesmo CSS/JS de filtros do Radar)
tests/
  test_riscos_regras.py
  test_riscos_classificacao.py
  test_riscos_registro.py
  test_riscos_painel.py
relatorios/
  riscos-AAAA-MM-DD.csv     → uma linha por risco (vira o histórico semanal)
```

Direção das dependências: `riscos` importa `radar.dados` e `radar.previsao`; `radar.relatorio`
importa `riscos.painel` só para montar a aba. `riscos` nunca importa `radar.relatorio`.

## Code Style

Igual ao Radar e ao `extrator/`:
- nomes em português;
- funções pequenas e puras;
- dataclasses para resultados;
- datas sempre `date`;
- `hoje` sempre por parâmetro.

```python
@dataclass(frozen=True)
class Risco:
    id: str                 # "R-90006-PRAZO"
    epic_id: int
    categoria: str          # "PRAZO" | "DEPENDENCIA" | "CAPACIDADE" | "ESCOPO" | "QUALIDADE" | "GOVERNANCA"
    estado: str             # "aberto" | "materializado"
    probabilidade: str      # "alta" | "media"
    impacto: str            # "alto" | "medio" | "baixo"
    criticidade: str        # "critico" | "alto" | "medio" | "baixo"
    evidencias: tuple[str, ...]
    gatilhos: tuple[str, ...]   # vazio = não escala


def risco_capacidade(epic: Item, restantes: list[Item]) -> tuple[str, str] | None:
    """(probabilidade, evidência) ou None se a regra não dispara."""
    if not restantes:
        return None
    sem_dono = sum(not i.responsavel for i in restantes)
    fracao = sem_dono / len(restantes)
    if fracao < 0.20:
        return None
    return ("alta" if fracao >= 0.50 else "media",
            f"{sem_dono} de {len(restantes)} itens restantes sem responsável")
```

## Testing Strategy

- **pytest**, só com dados sintéticos da fábrica do `tests/conftest.py`, que ganha links Successor e Faults.
- **Unidade:**
  - `regras`: cada categoria nos dois lados de cada limiar; Epic sem escopo; ritmo zero; data vencida → materializado; dependência dentro do mesmo Epic não conta; predecessor fechado não conta.
  - `classificacao`: cada célula da matriz; cada gatilho dentro e fora da janela (28 dias, 8 semanas); Epic sem dono.
  - `registro`: id estável; uma linha por Epic × categoria; movimento novo, piorou (inclui aberto → materializado), melhorou, igual e saiu, com os dois motivos de saída; sem CSV anterior, tudo é novo.
- **Integração:**
  - `radar relatorio` com dados sintéticos gera os três arquivos;
  - todo risco do CSV aparece no HTML;
  - mesma entrada = mesmo CSV;
  - HTML sem recurso externo e com títulos escapados.
- **Manual:** rodar nos dados reais; conferir 3 riscos (um de cada: PRAZO, DEPENDENCIA, QUALIDADE) contra o ADO, só leitura.

## Boundaries

- **Always:**
  - Somente leitura: nem `riscos` nem `radar` importam `extrator.client` ou fazem requisição de rede.
  - Toda regra produz a evidência com números; nenhum risco sem evidência.
  - Rodar `pytest` antes de dizer que algo está pronto; usar `.venv\Scripts\python`.
- **Ask first:**
  - Mudar regras, limiares, matriz ou gatilhos desta spec, fora o ajuste único previsto.
  - Nova categoria ou nova fonte de dados (ex.: textos, Issues, Risks existentes).
  - Qualquer dependência nova.
- **Never:**
  - Escrever no Azure DevOps (criar ou alterar Risks, Actions ou qualquer item).
  - Usar a probabilidade do Monte Carlo para classificar riscos (até a T8 do Radar passar e esta spec mudar).
  - Mandar dados para LLM ou serviço externo.
  - Usar dados reais em testes ou versionar `relatorios/` e `out/`.

## Success Criteria

1. `radar relatorio` grava `riscos-AAAA-MM-DD.csv` com uma linha por risco e as colunas:
   `regras_versao`, `data`, `risco_id`, `epic_id`, `titulo`, `programa`, `area`, `categoria`,
   `estado`, `probabilidade`, `impacto`, `criticidade`, `evidencia`, `dono`, `data_alvo`,
   `escalar`, `gatilhos`, `movimento`, `criticidade_anterior`.
2. Cada Epic avaliado tem no máximo um risco por categoria; ids estáveis entre execuções.
3. As 6 categorias, a matriz e os 4 gatilhos se comportam exatamente como nas tabelas acima, com testes dos dois lados de cada limiar.
4. Movimento contra o CSV anterior correto nos 5 casos; na primeira execução, tudo é "novo".
5. O HTML ganha a aba **Riscos**, com:
   - cartões: Escalar, Crítico, Alto, Médio, Baixo, Materializados;
   - matriz probabilidade × impacto clicável;
   - gráfico por categoria;
   - busca e filtros;
   - tabela com evidência, dono e movimento;
   - seção "Saíram do registro".

   A aba Radar continua igual.
6. Reconciliação no topo da aba: nº de riscos = soma por criticidade, e nº de Epics com pelo menos um risco.
7. Execução completa (Radar + Riscos) em < 60 s nos dados reais; mesma entrada = CSVs idênticos.
8. `pytest -q` passa.
9. **Portão para a diretoria:** a aba Riscos tem o aviso "uso interno — regras em revisão" até o usuário revisar o painel (bloco Escalar) e 3 riscos conferidos contra o ADO baterem. A aprovação é registrada nesta spec. O aviso do Radar segue o portão próprio dele (28/12).
   _(Revisado em 2026-11-05: o MVP é estático, sem execuções agendadas; o portão de "2 execuções semanais" virou a revisão de um único painel.)_
   **✅ Aprovado pelo usuário em 2026-11-05** (painel de 05/11; 3 riscos conferidos no ADO): `RISCOS_APROVADOS = True`, aba Riscos sem o aviso.
10. **Valores extremos só na frase:** razão acima de 10× aparece como "mais de 10×" e crescimento acima de 300% como "mais que quadruplicou"; a regra e a classificação usam o valor exato. _(Decidido em 2026-11-05.)_

## Open Questions

1. ~~Calibragem~~ — resolvido no planejamento (2026-11-05): cortes de impacto mantidos; crescimento medido contra o escopo de 4 semanas atrás; Escalar agrupado por Epic (26 hoje). Registro nos dados reais: 401 riscos em 240 dos 242 Epics.
2. **Riscos saídos por fechamento:** um Epic fechado com risco aberto foi mitigado ou entregue com atraso? Na v1 só dizemos "Epic fechado". Cruzar com a verdade pela entrega do Radar fica para depois.
3. **Issues e Blockers do ADO** (30 Issues e 3 Blockers em aberto): ficam fora da v1, pela regra de não usar o registro manual. Reavaliar depois das 2 semanas de revisão.
4. **Etapa 2 (LLM):** riscos citados só em texto (descrições e comentários) ficam fora, até haver anonimização definida.
