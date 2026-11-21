# Spec: Explicação de Indicadores v1 — causa provável por Epic (LLM)

> Origem: [docs/ideas/explicacao-de-indicadores.md](docs/ideas/explicacao-de-indicadores.md) · Sessão: RUN_LOG-Felipe-2026-11-11-19-23.md
> Status: **aprovada em 2026-11-11 · v1 concluída e liberada para a diretoria em 2026-11-11 (E6)**
> Reaproveita o Radar ([SPEC-radar-de-datas.md](SPEC-radar-de-datas.md)) e o Agente de Riscos ([SPEC-agente-de-riscos.md](SPEC-agente-de-riscos.md)): mesmos Epics, riscos, evidências e gatilhos.

## Objective

Dar à diretoria, para cada Epic que o Agente de Riscos manda **Escalar**, uma explicação curta
de **causa provável**: por que esse Epic está em risco, ligando os motivos do Radar, as
evidências dos riscos e as dependências numa relação de causa e efeito. A diretoria entende o
problema sem abrir o ADO.

- **Usuário:** diretoria / executivo, no painel semanal (aba Riscos, bloco Escalar).
- **Por que um LLM:** juntar 5 a 10 fatos soltos numa frase com causa e efeito é o que regra não
  faz bem. **O LLM só redige**: não calcula, não classifica, não decide cor, chance ou criticidade.
- **Cobertura:** só os Epics com a marca Escalar (28 em 11/11/2026). Expandir é trocar um filtro,
  depois da validação.
- **Provedor:** OpenAI (API direta). Nomes de pessoas são anonimizados antes do envio.
- **MVP estático:** gerado à mão junto com o painel (`radar relatorio`), sem agendamento.
- **Antes de ir para a diretoria:** sua revisão das narrativas de um painel libera
  (`NARRATIVAS_APROVADAS`), como foi com a aba Riscos. Até lá, aviso "em validação".

### Definições

| Termo | Definição |
|---|---|
| Epic do Escalar | Epic com pelo menos um risco `escalar = sim` no registro do dia |
| Fatos do Epic | Dados **já calculados**, nada novo: título, área, programa, data alvo, dono; do Radar: seção, chance, P85, restante, ritmo, razão de ritmo, motivos; de cada risco do Epic: categoria, estado, probabilidade, criticidade, evidência; os gatilhos de Escalar |
| Dependências | Só as que já estão na evidência do risco DEPENDENCIA (predecessor vencido ou em Epic em risco). Dependência em dia não entra |
| Pessoa | Valores de `responsavel`/`dono` do Epic. Viram `Pessoa A`, `Pessoa B`… na ordem em que aparecem nos fatos do Epic; o mapa fica só na memória local |
| Narrativa | Texto em português, 2 a 3 frases, até 500 caracteres, que começa pela causa principal. Rótulo no painel: **"Causa provável"** |
| Narrativa válida | Passou no validador (abaixo). Inválida ou com erro → não aparece; o painel mostra só os fatos |

### Validador (determinístico, depois da resposta)

A narrativa é **rejeitada** se:
1. contém um número (inteiro, decimal com vírgula ou ponto, percentual) que não aparece no texto
   dos fatos enviados;
2. contém uma data ou um `#id` que não aparece nos fatos;
3. cita `Pessoa X` que não está no mapa do Epic;
4. passa de 500 caracteres ou de 3 frases, ou vem vazia.

O motivo da rejeição vai para o CSV de narrativas. Não há nova tentativa automática.

### Cache e determinismo

- Chave = `sha256(modelo + PROMPT_VERSAO + fatos anonimizados em JSON ordenado)`.
- Antes de chamar a API, procura a chave nos `relatorios/narrativas-*.csv` existentes. Se achar
  uma narrativa válida, reaproveita, **sem chamada**. _(Implementação: rejeições também ficam no
  cache — com temperatura 0, pedir de novo daria o mesmo texto; só `erro` de rede/API é tentado
  de novo. Sem isso, a 2ª execução chamava a API para as rejeitadas e quebrava o critério 5.)_
- Temperatura 0. Mesma entrada → mesmo HTML (critério já exigido pelo Radar).

## Tech Stack

Igual ao Radar e aos Riscos: Python 3.12 no `.venv`, `pytest`, stdlib.
- Chamada à OpenAI com **`requests`**, que já está no `requirements.txt`. **Nenhuma dependência nova.**
- Configuração no `.env`:
  - `OPENAI_API_KEY`: sem ela, só o cache (como `--sem-llm`);
  - `OPENAI_MODEL`: **sem valor padrão no código**; sem ele, não há narrativa;
  - `OPENAI_TIMEOUT_S` (padrão 30).
- Endpoint: Chat Completions da OpenAI (`POST https://api.openai.com/v1/chat/completions`).
  É a **única chamada de rede** do pacote `radar`/`riscos`/`explicacao`. **Nenhuma chamada ao ADO.**

## Commands

```powershell
# painel semanal: Radar + Riscos + narrativas (se OPENAI_API_KEY e OPENAI_MODEL estiverem no .env)
.venv\Scripts\python -m radar relatorio
# sem chamar a OpenAI (usa só o cache; Epics sem cache ficam sem narrativa)
.venv\Scripts\python -m radar relatorio --sem-llm

# testes (nenhum teste chama a rede)
.venv\Scripts\python -m pytest -q
```

`radar relatorio` passa a gravar também `relatorios/narrativas-AAAA-MM-DD.csv`:
`data, epic_id, chave, modelo, prompt_versao, status (ok | rejeitada | erro | cache), motivo,
tokens_entrada, tokens_saida, narrativa` (texto **anonimizado**, como veio do modelo; a troca de
volta para os nomes reais acontece só ao montar o HTML).

No terminal, uma linha a mais:
`Narrativas: 28 Epics no Escalar = 25 ok (3 do cache) + 2 rejeitadas + 1 erro | 41.230 tokens | 18 s`.

## Project Structure

```
explicacao/
  __init__.py
  fatos.py          → Epic do Escalar → fatos (dict) a partir das linhas do Radar e do registro de riscos
  anonimizacao.py   → troca pessoas por "Pessoa A…" e desfaz a troca
  prompt.py         → PROMPT_VERSAO, mensagem de sistema e montagem da mensagem do usuário
  validador.py      → regras de rejeição (números, datas, #ids, pessoas, tamanho)
  cliente_openai.py → ClienteOpenAI com requests (o nome evita confundir com o SDK `openai`)
  narrativas.py     → orquestra: fatos → cache → chamada → validação → linhas do CSV
radar/
  __main__.py       → `relatorio` gera as narrativas; flag --sem-llm; lê OPENAI_* do .env
  narrativa.py      → sem mudança: o Narrador do Radar segue nulo; a causa provável é do `explicacao`
riscos/
  painel.py         → bloco Escalar mostra "Causa provável" + fatos; aviso até NARRATIVAS_APROVADAS
tests/
  test_explicacao_fatos.py, test_explicacao_anonimizacao.py, test_explicacao_validador.py,
  test_explicacao_narrativas.py (cliente falso, sem rede), test_riscos_painel.py (+ casos novos)
.env                → bloco "OpenAI" com OPENAI_API_KEY, OPENAI_MODEL e OPENAI_TIMEOUT_S vazios/comentados
```

Direção das dependências: `explicacao` importa de `radar` (dados, narrativa) e de `riscos`
(registro); `riscos.painel` recebe as narrativas prontas por parâmetro e não importa `explicacao`.

## Code Style

Igual ao resto: nomes em português, funções pequenas e puras, dataclasses, `hoje` por parâmetro.
O cliente HTTP é a única parte com efeito colateral e fica atrás da interface.

```python
@dataclass(frozen=True)
class Narrativa:
    epic_id: int
    chave: str
    status: str          # "ok" | "rejeitada" | "erro" | "cache"
    texto: str           # anonimizado; vazio se não for válida
    motivo: str = ""     # por que foi rejeitada ou deu erro


def rejeicoes(texto: str, fatos_texto: str, pessoas: set[str]) -> list[str]:
    """Lista vazia = narrativa válida."""
    erros = [f"número fora dos fatos: {n}" for n in _numeros(texto) if n not in fatos_texto]
    erros += [f"id fora dos fatos: {i}" for i in _ids(texto) if i not in fatos_texto]
    erros += [f"pessoa desconhecida: {p}" for p in _pessoas(texto) if p not in pessoas]
    if not texto.strip() or len(texto) > 500 or _frases(texto) > 3:
        erros.append("tamanho fora do limite")
    return erros
```

## Testing Strategy

- `pytest`, sem rede: o cliente HTTP é substituído por um falso que devolve respostas prontas.
- **fatos:** um Epic do Escalar sintético gera os fatos esperados. Dependência em dia não entra.
  Epic fora do Escalar não gera fatos.
- **anonimização:** nenhum valor de `responsavel`/`dono` aparece no payload serializado. A troca
  de volta restaura os nomes. O mapa é estável, então a mesma entrada dá a mesma chave.
- **validador:** um caso por regra (número inventado, decimal com vírgula, percentual, data,
  `#id`, `Pessoa Z`, texto longo, vazio) e um caso válido.
- **narrativas:** se o cache acerta, o cliente falso não é chamado. Se a API falha (timeout,
  401, 429, 500), o status é `erro`, a mensagem não traz a chave, o painel sai e os outros Epics
  seguem. Sem `OPENAI_API_KEY` ou `OPENAI_MODEL`, não há chamada e o painel sai igual ao de hoje.
- **painel:** o bloco Escalar mostra "Causa provável" com nomes reais, mostra o aviso quando
  `NARRATIVAS_APROVADAS = False` e escapa o HTML do texto do LLM.
- Os testes atuais (174) continuam passando.

## Boundaries

- **Always:**
  - mandar à OpenAI só os fatos anonimizados de Epics do Escalar;
  - validar toda resposta antes de exibir;
  - escapar o texto do LLM no HTML;
  - gravar status e motivo no CSV;
  - painel sai mesmo sem chave, sem rede ou com erro da API.
- **Ask first:**
  - ampliar a cobertura além do Escalar;
  - mandar qualquer campo novo à OpenAI (descrição, comentários, e-mails);
  - trocar de provedor;
  - adicionar dependência (ex.: SDK `openai`);
  - tirar o aviso (`NARRATIVAS_APROVADAS = True`).
- **Never:**
  - nomes ou e-mails de pessoas no payload;
  - chave da API no código, em log, em CSV ou em mensagem de erro;
  - LLM calculando ou alterando seção, chance, criticidade ou Escalar;
  - qualquer escrita no ADO;
  - agendar execuções;
  - teste que chame a API real.

## Success Criteria

1. Sem `OPENAI_MODEL`, `radar relatorio` gera o painel como hoje, sem narrativa, sem erro, e diz
   no terminal que as narrativas foram puladas. Sem `OPENAI_API_KEY`, usa só o cache.
   ✅ _11/11: conteúdo do HTML idêntico ao anterior (só o CSS novo difere)._
2. Com chave e modelo, cada Epic do Escalar sai com uma narrativa válida ou com `rejeitada`/`erro`
   e o motivo registrado em `narrativas-AAAA-MM-DD.csv`.
3. O payload enviado não contém nenhum valor de `responsavel`/`dono` dos dados (teste
   automático) nem e-mails. ✅ _11/11: 28 Epics reais, 0 nomes no payload._
4. Toda narrativa exibida passou no validador. Nenhum número, data, `#id` ou pessoa fora dos fatos.
5. Rodar de novo com a mesma extração e o mesmo `--hoje` faz **zero chamadas** e dá o mesmo HTML.
   ✅ _11/11, cliente falso nos dados reais: 28 chamadas → 0, mesmo hash do HTML._
6. A primeira execução com 28 Epics acrescenta **menos de 60 s**. Tokens e tempo aparecem no terminal.
   ✅ _11/11, `gpt-5.6-sol`: 23 s e 18.643 tokens; 0 rejeitadas. Falhas `SSLError` intermitentes resolvidas com
   sessão HTTP por thread e até 2 novas tentativas em falha de conexão; 28/28 válidas._
7. No bloco Escalar, cada Epic com narrativa mostra **"Causa provável"** com nomes reais, seguida
   dos fatos de onde ela saiu (motivos e evidências que já existem). Com
   `NARRATIVAS_APROVADAS = False`, o bloco mostra o aviso "explicação gerada por IA — em validação".
8. **Revisão humana:** você lê as narrativas de um painel. Se nenhuma "soar certa e estiver errada"
   em ponto relevante, `NARRATIVAS_APROVADAS = True`. ✅ _Aprovado em 2026-11-11 ("ficou ótimo"); aviso retirado._
9. `pytest -q` passa inteiro, sem rede. ✅ _207 testes (conftest zera `OPENAI_*` em todo teste)._

## Open Questions

- Qual valor você vai colocar em `OPENAI_MODEL`? Sem ele, o código não gera narrativa.
- Taxa de rejeição aceitável na revisão: se mais de 20% das narrativas forem rejeitadas pelo
  validador, ajustamos o prompt (`PROMPT_VERSAO` sobe) antes de você revisar?
