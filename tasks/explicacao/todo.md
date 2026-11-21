# Tarefas: Explicação de Indicadores v1

> Plano: [plan.md](plan.md) · Spec: [SPEC-explicacao-de-indicadores.md](../../SPEC-explicacao-de-indicadores.md)
> Comando de teste: `.venv\Scripts\python -m pytest -q`

---

## Fase 1: Núcleo sem rede

### E1: Fatos do Epic do Escalar + anonimização

**Descrição:** `explicacao/fatos.py` monta, para cada Epic com risco `escalar = sim`, um dict de
fatos a partir das linhas do Radar e do registro de riscos. `explicacao/anonimizacao.py` troca
o dono por "Pessoa A" em todos os campos e desfaz a troca.

**Critérios de aceite:**
- [x] Só Epics do Escalar; fatos com título, área, data alvo, dono, Radar (seção, chance, P85, restante, ritmo, razão, motivos), riscos (categoria, estado, probabilidade, criticidade, evidência) e gatilhos
- [x] Números formatados como no painel (vírgula decimal, %)
- [x] Nenhum nome do dono no JSON anonimizado; a troca de volta restaura; mesma entrada dá o mesmo JSON

**Verificação:** `tests/test_explicacao_fatos.py`
**Dependências:** nenhuma
**Arquivos:** `explicacao/__init__.py`, `explicacao/fatos.py`, `explicacao/anonimizacao.py`, teste
**Tamanho:** M

### E2: Prompt + validador

**Descrição:** `explicacao/prompt.py` (PROMPT_VERSAO, mensagem de sistema, mensagem com os
fatos) e `explicacao/validador.py` (regras de rejeição da spec).

**Critérios de aceite:**
- [x] Um caso por regra de rejeição (número, decimal, %, data, `#id`, pessoa, tamanho, vazio) e um válido
- [x] Prompt proíbe números fora dos fatos e pede 2–3 frases começando pela causa principal

**Verificação:** `tests/test_explicacao_validador.py`
**Dependências:** E1
**Arquivos:** `explicacao/prompt.py`, `explicacao/validador.py`, teste
**Tamanho:** S

## Checkpoint A
- [x] `pytest -q` passa
- [x] Fatos dos Epics do Escalar reais (11/11) montados, sem nome de pessoa

---

## Fase 2: Chamada e integração

### E3: Cliente OpenAI + orquestrador com cache e CSV

**Descrição:** `explicacao/cliente_openai.py` faz o POST em `chat/completions` com `requests`
(temperatura 0, timeout). `explicacao/narrativas.py` faz o fluxo fatos → chave → cache
(`narrativas-*.csv`) → cliente → validador → `Narrativa`, e gera as linhas do CSV.

**Critérios de aceite:**
- [x] Cache acerta → cliente não é chamado (status `cache`)
- [x] Timeout/401/429/500/JSON ruim → `erro`, mensagem sem a chave, demais Epics seguem
- [x] Sem chave ou modelo → nenhuma chamada
- [x] Payload enviado sem nomes de pessoas (cliente falso captura o payload)

**Verificação:** `tests/test_explicacao_narrativas.py`
**Dependências:** E2
**Arquivos:** `explicacao/cliente_openai.py`, `explicacao/narrativas.py`, teste
**Tamanho:** M

### E4: Painel + CLI + `.env`

**Descrição:** `riscos.painel.gerar_aba` recebe `narrativas` (epic_id → texto com nomes reais) e
mostra "Causa provável" no bloco Escalar, com aviso enquanto `NARRATIVAS_APROVADAS = False`.
`radar relatorio` gera as narrativas, grava `narrativas-AAAA-MM-DD.csv` e imprime o resumo;
`--sem-llm` usa só o cache. O `.env` ganha o bloco OpenAI vazio.

**Critérios de aceite:**
- [x] Texto do LLM escapado no HTML; nomes reais no HTML
- [x] Aviso "explicação gerada por IA — em validação" só com `NARRATIVAS_APROVADAS = False`
- [x] Sem chave → painel igual ao de hoje + linha "Narrativas: puladas (…)"

**Verificação:** `tests/test_riscos_painel.py`, `tests/test_cli.py`
**Dependências:** E3
**Arquivos:** `riscos/painel.py`, `radar/__main__.py`, `.env`, testes
**Tamanho:** M

## Checkpoint B
- [x] `radar relatorio` nos dados reais sem chave: HTML igual ao anterior (critério 1)
- [x] Cliente falso nos dados reais: Epics do Escalar narrados, CSV gravado, 2ª execução com zero chamadas e mesmo HTML

---

## Fase 3: Validação (depende do usuário)

### E5: Execução real com chave
- [x] Usuário preenche `OPENAI_API_KEY` e `OPENAI_MODEL` no `.env` (`gpt-5.6-sol`)
- [x] `radar relatorio --hoje 2026-11-11`: 23 s na 1ª execução (18.643 tokens); 0 rejeitadas. 7 `SSLError` intermitentes → sessão por thread + 2 novas tentativas em falha de conexão; 28/28 válidas

### E6: Revisão humana
- [x] Usuário lê as narrativas do painel; aprovado em 2026-11-11 → `NARRATIVAS_APROVADAS = True` e spec atualizada
