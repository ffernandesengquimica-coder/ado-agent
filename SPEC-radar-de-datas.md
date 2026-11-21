# Spec: Radar de Datas — Agente de Insights v1

> Origem: [docs/ideas/radar-de-datas.md](docs/ideas/radar-de-datas.md) · Sessão: RUN_LOG-Felipe-2026-11-04-21-40.md
> Status: **v3 — aprovada em 2026-11-04, modelo congelado para teste prospectivo** (ver "Histórico de versões" no fim)
> ✅ **Radar validado em 2026-11-21** (`RADAR_APROVADO = True`): o aviso "uso interno" saiu do painel. As menções a "uso interno" e ao teste de 28/12 abaixo descrevem o portão como foi planejado.

## Objective

Avisar a diretoria, semanas antes, quais **Epics** do projeto Atlas não vão cumprir
a **data alvo**, com evidência suficiente para agir.

- **Usuário:** diretoria / executivo. Lê um relatório semanal, não explora dados.
- **Sucesso:** antecipar atrasos. O relatório aponta Epics que vão estourar a data
  enquanto ainda há tempo de reagir.
- **Como:** para cada Epic aberto com data alvo, uma simulação Monte Carlo sobre o
  ritmo semanal de entrega do próprio Epic estima a probabilidade de cumprir a data.
  O executivo vê farol + probabilidade + motivos calculados por regra.
- **Antes de ir para a diretoria**, o modelo precisa passar no portão em um **teste
  prospectivo** (dados que ele nunca viu). Até lá, o relatório é de uso interno e diz isso no topo.

### Definições

| Termo | Definição |
|---|---|
| Epic avaliado | `tipo = Epic`, estado ∉ {Done, Removed} |
| Escopo do Epic | Todos os descendentes (qualquer nível, via `workitem_hierarquia.caminho_ids`) dos tipos **Product Backlog Item, Bug, Habilitator, Spike**, cujo Epic mais próximo acima é este. Tasks e Test Cases ficam de fora (são subdivisões ou artefatos de teste) |
| Removed | Fora de tudo: não conta no escopo nem no ritmo |
| Concluído | Estado `Done`; data da conclusão = `fechado_em` |
| Restante | Itens do escopo não concluídos |
| Data alvo | `data_alvo` do Epic (TargetDate). Datas alvo são compromissos reais (confirmado) |
| Ritmo | Itens do escopo concluídos por semana (segunda a domingo), nas últimas **12 semanas** completas, nunca antes de **2026-03-02** (fevereiro/2026 = migração). Semanas sem entrega contam como 0 |
| Entrada | Itens do escopo **criados** por semana, na mesma janela do ritmo. Mede quanto o escopo cresce |
| Probabilidade de cumprir | Fração de 10.000 simulações (semente fixa) em que o trabalho zera até a data alvo. Cada semana simulada sorteia, com reposição, uma semana do histórico e usa **o par** (entregues, criados) dela. Itens novos só entram até a semana da data alvo. Termina na primeira semana em que entregas acumuladas ≥ restante + entradas acumuladas |
| P50 / P85 | Data em que 50% / 85% das simulações terminam |
| Razão de ritmo | ((restante + entrada média × semanas até a data alvo) ÷ semanas até a data alvo) ÷ ritmo médio. > 1 = precisa acelerar |

### Classificação (cada Epic avaliado cai em exatamente uma seção)

1. **Já atrasado:** data alvo < hoje.
2. **Sem como prever:** sem data alvo, OU nenhuma conclusão na janela do ritmo (com restante > 0).
3. **Vermelho por falta de escopo:** data alvo no futuro e **escopo vazio** (nenhum item detalhado). Sem probabilidade; motivo "sem escopo detalhado".
4. **Farol** (demais), pela probabilidade de cumprir:
   **vermelho** < 40% · **amarelo** 40–70% · **verde** ≥ 70%.
   Cortes provisórios: podem ser ajustados **uma vez**, com base no backtest, e a mudança é registrada nesta spec.

### Motivos (por regra, sem LLM)

Cada Epic vermelho ou amarelo lista os motivos que se aplicam:

| Motivo | Regra |
|---|---|
| Precisa acelerar | razão de ritmo ≥ 1,5 → "precisa entregar N,N× mais rápido" |
| Parado | nenhuma conclusão nas últimas 4 semanas |
| Escopo crescendo | itens criados nas últimas 4 semanas ≥ 20% do escopo atual |
| Sem responsável | ≥ 20% do restante sem `responsavel_nome` |
| Features vencidas | Features filhas abertas com data alvo vencida (quantidade) |
| Sem escopo detalhado | escopo vazio (regra 3 da classificação) |

### Backtest

Para cada data de corte T (padrão: 2026-07-06, 2026-08-03, 2026-08-31, as segundas mais próximas de 01/07, 01/08 e 01/09):

- **Reconstrução em T:** um item existia se `criado_em < T`; estava concluído se `fechado_em < T`. O ritmo usa só as conclusões antes de T.
- **Epics avaliáveis:** não Removed, abertos em T (criados antes de T, sem `fechado_em < T`), com data alvo entre T e hoje e com escopo não vazio na data alvo.
- **Verdade (pela entrega):** escopo na data alvo = itens de escopo criados até a data alvo. O Epic **cumpriu** se todos esses itens estão Done com `fechado_em ≤ data_alvo`; caso contrário, **atrasou**. O estado do próprio Epic não importa: fechar o Epic no ADO é burocracia, não entrega.
- **Previsão do modelo:** "vai atrasar" = vermelho em T.
- **Baseline ingênuo:** "vai atrasar" se % concluído do escopo em T < % do tempo decorrido entre `data_inicio` e `data_alvo`.
- **Baseline trivial:** "todos atrasam".
- **Métricas** por corte e agregadas: n, Epics únicos, taxa base, precisão, recall, F1 do modelo e dos dois baselines.

**Limitações aceitas:** usa a data alvo *atual* (não há histórico de datas); itens Removed somem da reconstrução (inclusive da entrada, que fica levemente subestimada).

## Tech Stack

- Python **3.12** (já instalado), em `.venv` próprio do projeto. O `python` padrão do terminal é o venv do hermes-agent e **não** deve ser usado.
- `numpy` (Monte Carlo). Dev: `pytest`. (pandas foi previsto e dispensado: a stdlib `csv` bastou.)
- HTML gerado com a stdlib (`html.escape` + templates em string). Sem Jinja e sem JS externo.
- Entrada: CSVs do `extrator` (`workitems.csv`, `workitem_hierarquia.csv`). **Nenhuma chamada ao ADO.**

## Commands

```powershell
# ambiente (uma vez)
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt

# backtest (antes do primeiro relatório)
.venv\Scripts\python -m radar backtest
.venv\Scripts\python -m radar backtest --cortes 2026-07-06,2026-08-03,2026-08-31

# relatório semanal
.venv\Scripts\python -m radar relatorio
.venv\Scripts\python -m radar relatorio --extracao out\Atlas\20261105T003131Z --hoje 2026-11-05

# testes
.venv\Scripts\python -m pytest -q
```

Padrões: `--extracao` = pasta mais recente em `out/<ADO_PROJECT>/`; `--hoje` = data atual; `--semente 42`.

## Project Structure

```
extrator/            → (existente) extração somente leitura do ADO
radar/
  __init__.py
  __main__.py        → CLI: subcomandos `relatorio` e `backtest`
  dados.py           → carrega CSVs; monta Epics e itens de escopo (com epic_id)
  previsao.py        → ritmo semanal, Monte Carlo, classificação/farol
  motivos.py         → regras de motivos
  backtest.py        → reconstrução em T, baseline, métricas
  relatorio.py       → HTML autocontido
  narrativa.py       → interface `Narrador` (v1: só `NarradorNulo`; LLM na etapa 2)
tests/
  conftest.py        → fábrica de dados sintéticos (poucos itens, datas fixas)
  test_dados.py
  test_previsao.py
  test_motivos.py
  test_backtest.py
  test_relatorio.py
relatorios/          → saída (fora do git)
  radar-YYYY-MM-DD.html     → relatório para a diretoria
  radar-YYYY-MM-DD.csv      → uma linha por Epic com todos os números (vira histórico semanal)
  backtest-YYYY-MM-DD.csv   → métricas por corte
docs/ideas/          → one-pagers
```

## Code Style

Mesmo estilo do `extrator/`: nomes em português, funções pequenas e puras, dataclasses
para resultados, docstring curta no módulo explicando o que ele produz, comentários só
para o "porquê".

```python
@dataclass(frozen=True)
class Previsao:
    epic_id: int
    restante: int
    ritmo_medio: float
    prob_cumprir: float
    p50: date | None
    p85: date | None
    razao_ritmo: float | None
    farol: str  # "vermelho" | "amarelo" | "verde"


def simular(ritmo_semanal: np.ndarray, restante: int, semanas_ate_alvo: int,
            rng: np.random.Generator, execucoes: int = 10_000) -> np.ndarray:
    """Semanas necessárias para zerar `restante` em cada execução."""
    # Sorteia blocos de semanas do histórico até todas as execuções terminarem.
    ...
```

- Datas sempre `datetime.date` (não strings) depois de `dados.py`.
- Funções de cálculo recebem `hoje`/`T` e `rng` por parâmetro; nada lê relógio ou sorteia sem semente.

## Testing Strategy

- **pytest** em `tests/`, só com dados sintéticos montados à mão (5–30 itens). Os CSVs reais nunca entram nos testes.
- **Unidade (o grosso):**
  - `dados`: Epic mais próximo, filtro de tipos, Removed excluído, Tasks ignoradas.
  - `previsao`: ritmo com semanas zeradas, corte de 2026-03-02, Monte Carlo determinístico com semente, casos-limite (restante 0, ritmo 0, data vencida), cortes do farol.
  - `motivos`: cada regra isolada, nos dois lados do limiar.
  - `backtest`: reconstrução em T (itens criados/fechados depois de T não vazam), verdade cumpriu/atrasou, métricas num caso calculado à mão, baseline.
- **Integração:** `relatorio` gera HTML a partir dos dados sintéticos; todo Epic avaliado aparece exatamente uma vez; nada de `<script>` externo.
- **Verificação manual:** rodar `relatorio` e `backtest` nos dados reais e conferir 3 Epics à mão contra o ADO (leitura).

## Boundaries

- **Always:**
  - Somente leitura: o `radar` não importa `extrator.client` nem faz requisição de rede.
  - Semente fixa; mesma entrada + mesma semente = saída idêntica.
  - Rodar `pytest` antes de dizer que algo está pronto.
  - Usar `.venv\Scripts\python`, nunca o `python` padrão.
- **Ask first:**
  - Qualquer dependência além de numpy, pandas e pytest.
  - Mudar definições desta spec (escopo, janela, cortes do farol além do ajuste único pós-backtest).
  - Enviar qualquer dado para um LLM ou serviço externo (etapa 2).
- **Never:**
  - Escrever no Azure DevOps.
  - Mandar nomes/e-mails ou textos não anonimizados para fora da máquina.
  - Deixar um LLM calcular previsão, probabilidade ou farol.
  - Usar dados reais em testes ou versionar `relatorios/` e `out/`.

## Success Criteria

1. `radar backtest` gera `backtest-*.csv` com n, precisão, recall e F1 por corte e agregado, para modelo e baseline.
2. **Portão para a diretoria:** no agregado, recall ≥ 70%, **precisão ≥ taxa base + 10 p.p.** (taxa base = fração de Epics avaliáveis que atrasaram, ~63% → ~73%), e F1 do modelo > F1 do baseline ingênuo **e** > F1 do baseline trivial "todos atrasam". Se não passar, o relatório não vai para a diretoria e voltamos à spec.
   _(Revisado em 2026-11-04 no planejamento: com taxa base de ~63%, o portão original deixava passar o preditor trivial.)_
3. `radar relatorio` gera `radar-*.html` com seções Vermelho, Amarelo, Já atrasados, Sem como prever e Verde (recolhida); cada Epic mostra id, título, área, data alvo, probabilidade, P50, P85, restante, ritmo, razão e motivos.
4. Reconciliação: nº de Epics avaliados = soma das seções, exibido no topo do relatório.
5. `radar-*.csv` tem uma linha por Epic avaliado com todos os números do HTML.
6. Execução completa (relatório) em < 60 s nos dados reais.
7. Duas execuções com a mesma entrada e semente produzem CSVs idênticos.
8. `pytest -q` passa; todas as regras de `previsao`, `motivos` e `backtest` têm teste.
9. 3 Epics conferidos manualmente batem com o ADO (restante e data alvo).

## Open Questions

1. ~~Tamanho da amostra do backtest~~ — resolvido no planejamento: 67/71/69 Epics por corte.
2. ~~Epics fechados administrativamente~~ — resolvido: só 3 de 111 Epics Done têm < 90% do escopo; regra mantida.
3. **Escopo que cresce:** a previsão usa o escopo atual (otimista). O CSV semanal começa a guardar histórico; basta isso para a v1?
4. **Etapa 2 (LLM):** provedor e regras de anonimização ficam para depois da aprovação do portão.

## Histórico de versões

### v1 → v2 (2026-11-04, Checkpoint B)

O backtest da v1 **não passou** no portão (agregado: precisão 58%, recall 30%, F1 0,40
contra ingênuo 0,49 e trivial 0,77). O diagnóstico mostrou três coisas:

1. **A verdade media burocracia.** "Epic Done até a data alvo" marcava como atrasados
   Epics com o trabalho entregue e o Epic fechado depois (em 21% dos Epics concluídos
   o fechamento veio mais de 14 dias após o último item). Pela entrega, a taxa base cai
   de 63% para 31%.
2. **Pela entrega, a probabilidade ordena bem** (atrasou: 43% na faixa < 40%, 12% na faixa ≥ 70%),
   mas o vermelho ainda não bate o ingênuo (F1 0,46 contra 0,50).
3. **O escopo cresce depois do corte:** mediana de +23% de itens criados entre o corte
   e a data alvo; em 31% dos Epics, mais de 50%. O modelo v1 só via o escopo do corte.

Mudanças: verdade pela entrega do escopo criado até a data alvo; Monte Carlo com
entrada de itens novos (pares entregues/criados por semana); razão de ritmo inclui a
entrada esperada. Portão inalterado.

### v2 → v3 (2026-11-04, Checkpoint B)

O backtest v2 também **não passou** (precisão 67%, recall 58%, F1 0,62 > ingênuo 0,55,
< trivial 0,73; AUC 0,66; nenhum corte de farol passa). Os 14 Epics com escopo vazio no
corte atrasaram todos (100%). Decisão do usuário: **1 + 3**.

1. **v3 congelada:** escopo vazio com data alvo futura → vermelho ("sem escopo detalhado").
   Nada mais muda no modelo. Como essa regra saiu da mesma amostra do backtest, ela só vale
   depois do teste prospectivo.
2. **Teste prospectivo** _(MVP estático desde 2026-11-05: sem agendamento; o `radar-2026-11-05.csv` já tem previsões para 62 Epics com data alvo até 28/12, e basta uma extração manual em 28/12)_: cada execução grava `relatorios/radar-AAAA-MM-DD.csv` com a
   versão do modelo. Em **2026-12-28** (8 semanas), as previsões feitas para Epics cuja data
   alvo caiu entre a previsão e a avaliação são comparadas com a verdade pela entrega,
   **com o mesmo portão** (recall ≥ 70%, precisão ≥ base + 10 p.p., F1 > ingênuo e > trivial).
   Cada Epic conta uma vez, pela primeira previsão feita para ele.
   **Data alvo remarcada** _(decidido em 2026-11-11)_: vale a `data_alvo` gravada no CSV da
   previsão, não a data atual do ADO. Remarcar sem entregar conta como atraso (ex.: Epics 90008
   e 90009, de 06/11 para 30/11).
3. **Relatório de uso interno:** T5–T7 seguem, com aviso no topo do HTML até o portão passar.
