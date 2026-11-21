# Tarefas: Agente de Riscos v1

> Plano: [plan.md](plan.md) · Spec: [SPEC-agente-de-riscos.md](../../SPEC-agente-de-riscos.md)
> Comando de teste: `.venv\Scripts\python -m pytest -q`

---

## Fase 1: Fundação

### R1: Dados de risco e `razao_ritmo` pura

**Descrição:** `radar/dados.py` passa a expor, além do que já expõe:
- o Epic mais próximo de cada item (`epic_de`);
- as Faults abertas por Epic;
- as dependências: pares (predecessor, sucessor) lidos dos links `Successor` de `workitem_links.csv`, em streaming.

A razão de ritmo sai do `prever` para uma função pura `razao_ritmo(...)`, que o `prever` passa a usar. O Radar não muda.

**Critérios de aceite:**
- [x] `Dados` ganha `epic_de`, `faults` e `dependencias`; os campos atuais não mudam
- [x] Dependência só entre itens abertos e com P fora do Epic de S; direção conferida (link `Successor` de P para S)
- [x] `razao_ritmo` dá o mesmo valor que o `prever` dava; `radar-*.csv` nos dados reais idêntico ao gerado antes de R1

**Verificação:**
- [x] `tests/test_dados.py`: Fault sob PBI sob Feature sob Epic; link dentro do mesmo Epic ignorado; item fechado ignorado; direção do link
- [x] Regressão: gerar `radar-2026-11-05.csv` antes e depois e comparar os bytes

**Dependências:** nenhuma
**Arquivos:** `radar/dados.py`, `radar/previsao.py`, `tests/conftest.py`, `tests/test_dados.py`, `tests/test_previsao.py`
**Tamanho:** M

---

### R2: Regras das 6 categorias

**Descrição:** `riscos/regras.py` implementa uma função por categoria:

| Categoria | Regra |
|---|---|
| PRAZO | inclui materializado |
| DEPENDENCIA | segunda passada |
| CAPACIDADE | itens restantes sem responsável |
| ESCOPO | sem escopo detalhado, ou crescimento contra o escopo de 4 semanas atrás, mínimo de 5 itens |
| QUALIDADE | Faults e Bugs abertos sobre o restante |
| GOVERNANCA | sem data alvo |

Cada função devolve (probabilidade, evidências) ou `None`.

**Critérios de aceite:**
- [x] Cada regra dispara exatamente nos limiares da spec, com evidência em frase curta com números
- [x] No máximo um risco por categoria por Epic; se várias regras da categoria disparam, vale a de maior probabilidade, e a evidência junta todas
- [x] DEPENDENCIA usa o PRAZO já calculado do Epic do predecessor

**Verificação:**
- [x] `tests/test_riscos_regras.py`: cada regra dos dois lados de cada limiar; Epic novo (< 5 itens há 4 semanas) não cresce; ritmo zero; sem data alvo
- [x] Manual: contagem por categoria nos dados reais batendo com o protótipo do planejamento

**Dependências:** R1
**Arquivos:** `riscos/__init__.py`, `riscos/regras.py`, `tests/test_riscos_regras.py`, `tests/conftest.py`
**Tamanho:** M

---

## Checkpoint A
- [x] `pytest -q` passa (123); CSV do Radar idêntico byte a byte (sha256 igual)
- [x] Contagens por categoria conferidas nos dados reais: 360 riscos em 239 Epics — PRAZO 172 (29 materializados) · ESCOPO 68 · CAPACIDADE 61 · GOVERNANCA 31 · DEPENDENCIA 20 (7 alta entre programas) · QUALIDADE 8; iguais ao protótipo do planejamento
- [x] Seguir para a Fase 2 (aprovado)

---

## Fase 2: Registro

### R3: Impacto, criticidade e gatilhos de Escalar

**Descrição:** `riscos/classificacao.py` calcula:
- o impacto do Epic (restante e dependentes);
- a criticidade, pela matriz 2×3;
- os 4 gatilhos: data próxima, dependência entre programas, atraso grande e sem dono.

**Critérios de aceite:**
- [x] Cada célula da matriz e cada gatilho conforme as tabelas da spec
- [x] Gatilhos devolvidos como tupla de nomes (vazia = não escala)

**Verificação:**
- [x] `tests/test_riscos_classificacao.py`: 6 células; 28 dias (27, 28 e 29); 8 semanas; Epic sem dono com e sem Crítico; dependência no mesmo programa não escala

**Dependências:** R2
**Arquivos:** `riscos/classificacao.py`, `tests/test_riscos_classificacao.py`
**Tamanho:** S

---

### R4: Registro, CSV semanal, movimento e integração no `radar relatorio`

**Descrição:** `riscos/registro.py` monta o registro: `Risco` com id estável, ordenado, e as linhas do CSV, com as colunas da spec. Ele calcula o movimento contra o `riscos-*.csv` anterior mais recente. O `radar relatorio` passa a gravar `riscos-AAAA-MM-DD.csv`.

**Critérios de aceite:**
- [x] Colunas exatamente as do critério 1 da spec; `REGRAS_VERSAO = "r1"`
- [x] Movimento: novo, piorou (inclui aberto → materializado), melhorou, igual e saiu (Epic fechado / sinal desapareceu); sem anterior, tudo é novo
- [x] Mesma entrada = CSV idêntico

**Verificação:**
- [x] `tests/test_riscos_registro.py`: os 5 movimentos com um CSV anterior sintético; id estável; ordenação
- [x] `tests/test_cli.py`: `relatorio` grava os dois CSVs
- [x] Manual: rodar nos dados reais duas vezes, comparar arquivos, medir o tempo; Escalar ≈ 26 Epics

**Dependências:** R3
**Arquivos:** `riscos/registro.py`, `radar/__main__.py`, `tests/test_riscos_registro.py`, `tests/test_cli.py`
**Tamanho:** M

---

## Checkpoint B
- [x] `riscos-2026-11-05.csv` nos dados reais: 360 riscos em 239 Epics; relatório completo em 3,8 s; duas execuções = mesmo sha256; CSV do Radar ainda idêntico ao de antes da R1
- [x] Escalar: 37 riscos em 26 Epics — registrado na spec
- [x] Movimento simulado (semana anterior = 29/10, em pasta de rascunho): igual 298 · piorou 34 · novo 18 · melhorou 10
- [x] Ajuste de texto achado na simulação: vencida há menos de 7 dias fala em dias, não "0 semanas"
- [x] Seguir para a Fase 3 (aprovado)

---

## Fase 3: Painel

### R5: Abas Radar | Riscos, cartões, tabela e filtros

**Descrição:** `radar/relatorio.py` passa a ter duas abas. A aba Radar continua como está. `riscos/painel.py` gera a aba Riscos com:
- o aviso de uso interno;
- os cartões Escalar, Crítico, Alto, Médio, Baixo e Materializados (clicáveis);
- a reconciliação;
- a busca, os filtros por categoria e programa;
- a tabela: risco, Epic, categoria, estado, P, I, criticidade, evidência, dono, data alvo e movimento.

**Critérios de aceite:**
- [x] Todo risco do CSV aparece exatamente uma vez na tabela; reconciliação no topo
- [x] As abas funcionam sem JS (as duas visíveis em sequência); com JS, uma por vez
- [x] Sem recurso externo; textos escapados

**Verificação:**
- [x] `tests/test_riscos_painel.py`: uma linha por risco, escape, aviso, filtros presentes
- [x] `tests/test_relatorio.py` continua passando (aba Radar intacta)
- [x] Edge headless: screenshot desktop e celular; clique simulado em um cartão

**Dependências:** R4
**Arquivos:** `riscos/painel.py`, `radar/relatorio.py`, `tests/test_riscos_painel.py`, `tests/test_relatorio.py`
**Tamanho:** M

---

### R6: Escalar por Epic, matriz P × I, categorias, "Saíram do registro"

**Descrição:** A aba Riscos ganha:
- no topo, o bloco **Escalar**: uma linha por Epic, com os riscos e gatilhos dele;
- a matriz probabilidade × impacto clicável, que filtra a tabela;
- o gráfico de riscos por categoria, empilhado por criticidade;
- a seção recolhível "Saíram do registro", com o motivo de cada saída.

**Critérios de aceite:**
- [x] Bloco Escalar com uma linha por Epic; contagem igual à do CSV
- [x] Matriz e gráfico de categorias filtram a tabela, como os gráficos do Radar
- [x] "Saíram do registro" só aparece quando há CSV anterior

**Verificação:**
- [x] `tests/test_riscos_painel.py`: agrupamento por Epic, células da matriz, seção de saídas com e sem anterior
- [x] Edge headless: screenshot e clique simulado na matriz

**Dependências:** R5
**Arquivos:** `riscos/painel.py`, `tests/test_riscos_painel.py`
**Tamanho:** M

---

## Checkpoint C
- [x] Critérios de sucesso 1–8 da spec: CSV com as 19 colunas; ids estáveis; regras, matriz e gatilhos testados; movimento; aba Riscos completa; reconciliação; 3,8 s e determinístico; 170 testes
- [x] 3 riscos conferidos com o ADO (GET, somente leitura): R-90008-DEPENDENCIA (link Successor 90010 → 90007 na direção certa; Epic 90002 com alvo 30/10 em andamento), R-90001-PRAZO (alvo 13/11, em andamento), R-90003-QUALIDADE (Faults 90012 e 90013 abertas sob PBI › Feature › Epic 90003)
- [x] Bug achado na revisão visual e corrigido: predecessor repetido nas evidências de DEPENDENCIA (vários itens do Epic dependendo do mesmo P); teste novo
- [x] Revisão humana do painel (aprovado em 2026-11-05)

---

## Fase 4: Portão

### R7: Portão — revisão do painel pelo usuário (MVP estático)

**Descrição:** O MVP é estático: nada agendado (decisão do usuário, 2026-11-05). O usuário revisa o
painel de 05/11 (bloco Escalar e os 3 riscos já conferidos no ADO). Se aprovado, a constante
`RISCOS_APROVADOS` passa a `True`, a aba Riscos perde o aviso, e a aprovação é registrada na spec.

**Critérios de aceite:**
- [x] Decisão do usuário registrada na spec; o aviso do Radar segue até a T8 (28/12)

**Dependências:** R6
**Arquivos:** `riscos/painel.py`, `SPEC-agente-de-riscos.md`
**Tamanho:** XS
