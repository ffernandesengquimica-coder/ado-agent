# Tarefas: Dashboard Inteligente v1

> Spec: [SPEC-dashboard-inteligente.md](../../SPEC-dashboard-inteligente.md) · Status: aprovado em 2026-11-11 ("vai até o fim")
> Comando de teste: `.venv\Scripts\python -m pytest -q`

Ordem pelo grafo de dependências: D1 → D2 → (D3, D4) → D5 → D6 → D7 → D8.

## Fase 1: Base

### D1: Crescimento de escopo do Radar alinhado aos Riscos (pré-requisito)
- [x] `radar/motivos.py`: novos ÷ itens de 4 semanas atrás, mín. 5, "mais que quadruplicou" acima de 300%
- [x] Mesmo % nas duas abas para o mesmo Epic; `radar-*.csv` muda só em `motivos`
- **Verif.:** `tests/test_motivos.py`; diff do CSV real antes/depois só na coluna `motivos`
- **Arquivos:** `radar/motivos.py`, `tests/test_motivos.py` · **S**

### D2: Núcleo genérico de LLM
- [x] `explicacao/llm.py`: `Pedido` → chave → cache (`textos-*.csv`) → cliente → validador → `Texto`
- [x] `narrativas.py` usa o núcleo; chave da causa provável idêntica à de antes
- [x] Limites por tipo no validador; prompts por tipo
- **Verif.:** `tests/test_explicacao_llm.py`; testes atuais de narrativas passam sem mudança
- **Arquivos:** `explicacao/llm.py`, `explicacao/narrativas.py`, `explicacao/prompt.py`, `explicacao/validador.py` · **M**

## Checkpoint A
- [x] `pytest -q` passa; `radar relatorio` real: 28 narrativas ainda do cache depois da refatoração (as 8 com motivo de escopo foram regeradas pela D1)

## Fase 2: Conteúdo

### D3: Recortes, pauta e perguntas sugeridas (fatos + regras)
- [x] `recortes.py`: fatos geral/programa/categoria/Epic qualquer
- [x] `pauta.py`: pontuação, desempate, 5 pontos, manchete de fallback
- [x] `sugeridas.py`: 3 perguntas com fatos; resposta fixa sem dependências
- **Verif.:** `tests/test_explicacao_recortes.py`, `tests/test_explicacao_pauta.py`
- **Arquivos:** 3 módulos + 2 testes · **M**

### D4: Leitura por regra
- [x] `leitura.py`: texto por valor de filtro (Radar: seção, programa, mês; Riscos: criticidade, escalar, estado, célula, categoria, programa, epic)
- **Verif.:** `tests/test_explicacao_leitura.py` (números batem com as linhas)
- **Arquivos:** `explicacao/leitura.py`, teste · **S**

## Fase 3: Painel

### D5: HTML — topo, caixas, painel lateral, JSON e JS
- [x] Pauta + perguntas sugeridas + "Perguntas desta reunião" no topo
- [x] Caixa "Leitura do agente" nas duas abas, reagindo aos filtros
- [x] Título do Epic abre painel lateral (Esc fecha)
- [x] Selo "previsão em validação" onde `usa_radar`; aviso "em validação" até `AGENTE_APROVADO`
- **Verif.:** `tests/test_relatorio.py`, `tests/test_riscos_painel.py`; conferência no navegador
- **Arquivos:** `radar/relatorio.py`, `riscos/painel.py`, testes · **M/L**

### D6: CLI `relatorio` gera os textos
- [x] Pedidos de pauta, sugeridas e resumos; `textos-AAAA-MM-DD.csv`; resumo no terminal
- **Verif.:** `tests/test_cli.py`; execução real com cache na 2ª vez (zero chamadas, mesmo HTML)
- **Arquivos:** `radar/__main__.py`, teste · **S**

### D7: Modo apresentador `radar perguntar`
- [x] Recorte por regra; anonimização da pergunta; CSV; regera o painel
- **Verif.:** `tests/test_explicacao_perguntar.py`; 3 perguntas reais
- **Arquivos:** `explicacao/perguntar.py`, `radar/__main__.py`, teste · **M**

### D7b: Caixa de pergunta na página (`radar servir`) — pedido em 2026-11-17
- [x] `radar/servidor.py`: servidor só em 127.0.0.1, `POST /perguntar` (Host local, Origin igual, JSON, até 300 caracteres)
- [x] `radar servir [--porta 8765]`: mesmo fluxo do `perguntar`; regera o HTML depois de cada resposta
- [x] Chat no canto inferior direito (`painel_agente.chat`): conversa do dia + campo; aberto como arquivo, o campo fica desligado com a dica. "Perguntas desta reunião" no topo continua como registro
- **Verif.:** `tests/test_servidor.py`; pergunta real pelo servidor em 3 s; `node --check` no JS (clique no navegador fica para a D8)
- **Arquivos:** `radar/servidor.py`, `radar/__main__.py`, `radar/painel_agente.py`, testes · **S**

## Checkpoint B
- [x] Critérios 1–11 da spec verificados nos dados reais de 11/11 (exceto a interação no navegador: o Chrome automatizado não alcança o servidor local; JS conferido com `node --check`)

## Fase 4: Validação (usuário)

### D8: Revisão humana
- [ ] Apresentador testa 10 perguntas reais e revisa pauta e resumos → `AGENTE_APROVADO = True`
