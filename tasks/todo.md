# Tarefas: Radar de Datas v1

> Plano: [plan.md](plan.md) · Spec: [SPEC-radar-de-datas.md](../SPEC-radar-de-datas.md)
> Comando de teste: `.venv\Scripts\python -m pytest -q`

---

## Fase 1: Fundação

### T1: Ambiente, dependências e esqueleto do CLI

**Descrição:** Criar o `.venv` com Python 3.12, os arquivos de dependências e o pacote
`radar/` com um CLI que já aceita os subcomandos `relatorio` e `backtest` (ainda sem
lógica), além da base de testes com uma fábrica de dados sintéticos.

**Critérios de aceite:**
- [x] `.venv` com Python 3.12; `requirements.txt` ganha `numpy` e `pandas`; `requirements-dev.txt` com `pytest`
- [x] `python -m radar --help` lista `relatorio` e `backtest`, com `--extracao`, `--hoje`, `--semente` (e `--cortes` no backtest)
- [x] `tests/conftest.py` oferece uma fábrica de work items sintéticos (id, tipo, estado, datas, pai)

**Verificação:**
- [x] `.venv\Scripts\python -m pytest -q` roda (1 teste de fumaça do CLI)
- [x] `.venv\Scripts\python -m radar --help`
- [x] `.gitignore` inclui `.venv/` e `relatorios/`

**Dependências:** nenhuma
**Arquivos:** `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `radar/__init__.py`, `radar/__main__.py`, `tests/conftest.py`
**Tamanho:** S

---

### T2: Carga dos dados: Epics e escopo com datas tipadas

**Descrição:** `dados.py` lê `workitems.csv` e `workitem_hierarquia.csv` da extração
(padrão: a mais recente em `out/<projeto>/`) e devolve os Epics e os itens de escopo
já ligados ao Epic mais próximo acima, com datas como `date`.

**Critérios de aceite:**
- [x] Escopo = descendentes PBI/Bug/Habilitator/Spike, não Removed, ligados ao Epic **mais próximo** (Epic dentro de Epic não conta duas vezes)
- [x] Tasks, Test Cases e itens sem Epic acima ficam de fora; datas vazias viram `None`
- [x] `ultima_extracao(out_dir, projeto)` encontra a pasta mais recente

**Verificação:**
- [x] `tests/test_dados.py`: Epic aninhado, Removed, Task, item órfão, datas vazias
- [x] Manual: nos CSVs reais, 242 Epics abertos e 200 com escopo (bate com a investigação do plano)

**Dependências:** T1
**Arquivos:** `radar/dados.py`, `tests/test_dados.py`, `tests/conftest.py`
**Tamanho:** S

---

## Checkpoint A: Fundação
- [x] `pytest -q` passa
- [x] Contagens reais conferidas
- [x] Seguir para a Fase 2

---

## Fase 2: Provar o modelo

### T3: Previsão: ritmo semanal, Monte Carlo e farol

**Descrição:** `previsao.py` calcula, para um Epic em uma data `hoje`, o ritmo semanal
(12 semanas, segunda a domingo, nunca antes de 2026-03-02, semanas zeradas incluídas),
roda o Monte Carlo vetorizado e classifica o Epic (já atrasado / sem como prever /
farol), devolvendo um `Previsao`.

**Critérios de aceite:**
- [x] Mesma entrada + mesma semente → resultado idêntico; probabilidade, P50, P85 e razão de ritmo conforme a spec
- [x] Casos-limite: restante 0 (cumpre), ritmo todo zero (sem como prever), data vencida (já atrasado), sem data alvo (sem como prever)
- [x] Cortes do farol (40% / 70%) parametrizáveis, com padrão da spec

**Verificação:**
- [x] `tests/test_previsao.py`: semanas zeradas, corte de março, determinismo, cada caso-limite, fronteiras do farol
- [x] Teste com ritmo constante (ex.: 2/semana, restante 10, alvo em 6 semanas → probabilidade 1,0)

**Dependências:** T2
**Arquivos:** `radar/previsao.py`, `tests/test_previsao.py`
**Tamanho:** M

---

### T4: Backtest e comando `radar backtest`

**Descrição:** `backtest.py` reconstrói os itens como eram em cada corte T, chama a
mesma `prever()` do relatório, compara com o que aconteceu e mede modelo, baseline
ingênuo e baseline trivial ("todos atrasam"). O CLI grava `relatorios/backtest-*.csv`
e imprime a tabela.

**Critérios de aceite:**
- [x] Reconstrução sem vazamento: item criado ou fechado depois de T não afeta a previsão em T
- [x] Métricas por corte e agregadas (n, Epics únicos, precisão, recall, F1) para modelo, ingênuo e trivial
- [x] Indicação explícita de passou/não passou no portão vigente da spec

**Verificação:**
- [x] `tests/test_backtest.py`: vazamento, verdade cumpriu/atrasou, métricas num caso calculado à mão, os dois baselines
- [x] Manual: `.venv\Scripts\python -m radar backtest` nos dados reais; n por corte ≈ 67/71/69

**Dependências:** T3
**Arquivos:** `radar/backtest.py`, `radar/__main__.py`, `tests/test_backtest.py`
**Tamanho:** M

---

### T4.1: Spec v2: verdade pela entrega e crescimento de escopo

**Descrição:** O backtest v1 não passou. A verdade passa a ser a entrega do escopo
criado até a data alvo, e o Monte Carlo passa a simular a entrada de itens novos
(pares entregues/criados por semana do histórico do Epic). Depois, rodar o backtest de novo.

**Critérios de aceite:**
- [x] `entrada_semanal` conta criações por semana na mesma janela do ritmo
- [x] `simular` aceita entrada; itens novos só até a semana da data alvo; pares sorteados juntos
- [x] `atrasou` pela entrega: Epic fechado tarde com o escopo entregue a tempo = cumpriu; Epic sem escopo na data alvo fica fora

**Verificação:**
- [x] `pytest -q` (testes novos de entrada, simulação com crescimento e verdade pela entrega)
- [x] `radar backtest` nos dados reais → Checkpoint B de novo

**Dependências:** T4
**Arquivos:** `radar/previsao.py`, `radar/backtest.py`, `tests/test_previsao.py`, `tests/test_backtest.py`
**Tamanho:** M

---

## Checkpoint B: Portão (revisão humana obrigatória)
- [x] Resultado do backtest mostrado ao humano — v1 **NÃO PASSOU** (recall 30%, F1 0,40 < ingênuo 0,49 < trivial 0,77)
- [x] Backtest v2 (T4.1) — **NÃO PASSOU** (precisão 67%, recall 58%, F1 0,62 > ingênuo 0,55, < trivial 0,73; AUC 0,66). Nenhum corte do farol passa.
- [x] Ajuste único dos cortes do farol: nenhum corte passa, cortes mantidos (40% / 70%)
- [x] Decisão do humano: **1 + 3** — congelar v3 para teste prospectivo (T4.2, T8) e construir o relatório para uso interno (T5–T7)

---

### T4.2: v3 congelada: escopo vazio = vermelho

**Descrição:** Epic com data alvo futura e sem nenhum item de escopo vira vermelho (sem
probabilidade), em vez de "sem como prever". O modelo ganha uma versão (`MODELO_VERSAO = "v3"`)
gravada em todo CSV, para o teste prospectivo saber qual modelo fez cada previsão.

**Critérios de aceite:**
- [x] Escopo vazio + data alvo futura → `vermelho`, `prob_cumprir = None`; sem data alvo continua `sem_como_prever`
- [x] `MODELO_VERSAO` aparece nos CSVs do backtest
- [x] Backtest v3 roda e o resultado fica registrado (só como referência: o portão agora é o prospectivo)

**Verificação:**
- [x] `pytest -q`
- [x] `radar backtest` nos dados reais

**Dependências:** T4.1
**Arquivos:** `radar/previsao.py`, `radar/backtest.py`, `tests/test_previsao.py`
**Tamanho:** XS

---

## Fase 3: Relatório

### T5: Motivos por regra

**Descrição:** `motivos.py` aplica as 6 regras da spec (precisa acelerar, parado, escopo
crescendo, sem responsável, Features vencidas, sem escopo detalhado) a um Epic e devolve a lista de frases.

**Critérios de aceite:**
- [x] Cada regra dispara exatamente nos limiares da spec (1,5×; 4 semanas; 20%; 20%; ≥1 Feature vencida)
- [x] Frases curtas, com números concretos (ex.: "precisa entregar 2,1× mais rápido")
- [x] Só calculado para Epics vermelhos e amarelos

**Verificação:**
- [x] `tests/test_motivos.py`: cada regra, dos dois lados do limiar

**Dependências:** T3 (usa `Previsao`), T2 (Features filhas)
**Arquivos:** `radar/motivos.py`, `tests/test_motivos.py`, `radar/dados.py` (expor Features filhas, se preciso)
**Tamanho:** S

---

### T6: Comando `radar relatorio` gerando o CSV por Epic

**Descrição:** O CLI `relatorio` carrega os dados, prevê todos os Epics abertos, aplica
os motivos e grava `relatorios/radar-YYYY-MM-DD.csv` com uma linha por Epic e todos os
números. Esta é a primeira fatia de ponta a ponta do relatório.

**Critérios de aceite:**
- [x] Todo Epic aberto aparece exatamente uma vez, com a seção; a soma das seções = nº de Epics avaliados
- [x] Duas execuções com a mesma entrada e semente geram CSVs idênticos
- [x] Execução completa nos dados reais em < 60 s

**Verificação:**
- [x] Teste de integração com dados sintéticos: reconciliação e determinismo
- [x] Manual: rodar duas vezes nos dados reais, comparar os arquivos e medir o tempo

**Dependências:** T3, T5
**Arquivos:** `radar/__main__.py`, `radar/relatorio.py` (parte CSV), `tests/test_relatorio.py`
**Tamanho:** S

---

### T7: Relatório HTML e interface `Narrador`

**Descrição:** `relatorio.py` gera `relatorios/radar-YYYY-MM-DD.html` autocontido, com
seções Vermelho, Amarelo, Já atrasados, Sem como prever e Verde (recolhida) e a
reconciliação no topo. `narrativa.py` define a interface `Narrador` com só o
`NarradorNulo` (o LLM fica para a etapa 2).

**Critérios de aceite:**
- [x] Cada Epic mostra id, título, área, data alvo, probabilidade, P50, P85, restante, ritmo, razão e motivos
- [x] HTML autocontido: sem `<script>` nem CSS externos; textos escapados
- [x] `Narrador` recebe só números e motivos já calculados; `NarradorNulo` não acrescenta nada

**Verificação:**
- [x] `tests/test_relatorio.py`: seções, escape de HTML (título com `<`), ausência de recursos externos
- [x] Manual: abrir o HTML dos dados reais no navegador e conferir 3 Epics com o ADO (leitura)

**Dependências:** T6
**Arquivos:** `radar/relatorio.py`, `radar/narrativa.py`, `radar/__main__.py`, `tests/test_relatorio.py`
**Tamanho:** M

---

### T7.1: Painel interativo e legenda (pedido na revisão do HTML, 2026-11-05)

**Descrição:** A lista longa por seções virou um painel: cartões por seção (clicáveis),
gráficos de Epics por programa e de datas alvo por mês (clicáveis), busca, filtro por
programa, ordenação por coluna e legenda "Como ler este relatório" (também como dica nos
cabeçalhos). O script é embutido e só filtra/ordena; sem JS, a tabela completa continua legível.

**Critérios de aceite:**
- [x] Legenda explica Chance, P50, P85, Restante, Ritmo/sem e Razão
- [x] Filtros por seção, programa e mês da data alvo; busca por id/título/área/motivo; contador "Mostrando N de M"
- [x] Nenhum recurso externo; títulos sempre escapados; layout sem rolagem lateral no celular

**Verificação:**
- [x] `pytest -q` (84 testes; novos: legenda, filtros; teste de autocontido ajustado ao script embutido)
- [x] Edge headless: cliques simulados → "Mostrando 46 de 242 Epics · filtro: Vão atrasar · data alvo: dez/26"

**Arquivos:** `radar/relatorio.py`, `tests/test_relatorio.py`
**Tamanho:** S

---

## Checkpoint C: Relatório interno completo
- [x] Critérios de sucesso 3–9 da spec (o 2, portão, fica para a T8): 4,2 s, determinístico, 3 Epics conferidos com o ADO
- [x] HTML com aviso "uso interno — modelo em validação" no topo
- [x] Revisão humana do HTML (aprovada em 2026-11-11)

---

## Fase 4: Teste prospectivo

### T8: Avaliação prospectiva (em 2026-12-28)

**Descrição:** Comparar as previsões gravadas nos `relatorios/radar-*.csv` semanais com a
verdade pela entrega, para Epics cuja data alvo caiu entre a previsão e a avaliação. Cada
Epic conta uma vez, pela primeira previsão. Mesmo portão da spec.

**Pré-requisito operacional (MVP estático, sem agendamento):** as previsões já gravadas em
`relatorios/radar-2026-11-05.csv` bastam: 62 Epics têm data alvo entre 05/11 e 28/12 (56 com
previsão). Em 28/12, rodar `python -m extrator` **uma vez, à mão**, para ter a verdade pela entrega.
Execuções extras no meio do caminho são opcionais.

**Critérios de aceite:**
- [ ] Métricas do modelo, ingênuo e trivial só com previsões feitas antes da data alvo
- [ ] Data alvo remarcada: julgar pela `data_alvo` gravada no CSV da previsão, não pela atual do ADO (decidido em 2026-11-11; ex.: 90008 e 90009, 06/11 → 30/11)
- [ ] Passou → relatório pode ir para a diretoria (tirar o aviso). Não passou → voltar à spec

**Dependências:** T6 (CSV semanal) e 8 semanas de execuções
**Tamanho:** S
