"""Mensagens enviadas ao LLM, por tipo de texto. Mudou um prompt? Suba a versão dele: ela entra na chave do cache."""
from dataclasses import dataclass

PROMPT_VERSAO = "p1"            # causa provável (aprovada em 2026-11-11): não mudar sem regerar e revisar
LIMITE_CARACTERES = 500
LIMITE_FRASES = 3

SISTEMA = f"""Você explica riscos de projetos para a diretoria de uma empresa, em português do Brasil.
Recebe os fatos de um Epic que foi escalado para a diretoria, todos já calculados por regras.
Escreva a CAUSA PROVÁVEL do risco: de 2 a {LIMITE_FRASES} frases, no máximo {LIMITE_CARACTERES - 50} caracteres,
começando pela causa principal e ligando os fatos em causa e efeito.

Regras obrigatórias:
- Use só os fatos recebidos. Não invente causas, pessoas, datas, números nem dependências.
- Copie números, percentuais, datas e ids (#123) exatamente como aparecem nos fatos.
  Não calcule, não some, não arredonde e não converta (não escreva "três vezes" no lugar de "3,2×").
- Pessoas aparecem como "Pessoa A", "Pessoa B": use exatamente assim, nunca invente nomes.
- Não recomende ações e não dê opinião; só explique por que o Epic está em risco.
- Se os fatos não indicarem uma causa clara, diga apenas o que eles mostram.
- Responda só com o texto, sem título, sem marcadores e sem aspas."""

_REGRAS = """Regras obrigatórias:
- Use só os fatos recebidos. Não invente causas, pessoas, datas, números nem dependências.
- Copie números, percentuais, datas e ids (#123) exatamente como aparecem nos fatos.
  Não calcule, não some, não subtraia, não arredonde e não converta números em palavras.
- Pessoas aparecem como "Pessoa A", "Pessoa B": use exatamente assim, nunca invente nomes.
- Não recomende ações e não dê opinião.
- Responda só com o texto, sem título, sem marcadores e sem aspas."""

_CONTEXTO = """Você apoia a reunião semanal da diretoria de uma empresa sobre os Epics de um programa de projetos,
em português do Brasil. Os fatos (JSON) foram todos calculados por regras a partir do Azure DevOps:
riscos (categoria, criticidade, evidência, movimento desde o registro anterior) e a previsão de datas do Radar."""


@dataclass(frozen=True)
class Tipo:
    versao: str
    sistema: str
    limite_caracteres: int
    limite_frases: int
    rotulo: str = "Fatos (JSON)"


TIPOS = {
    "causa": Tipo(PROMPT_VERSAO, SISTEMA, LIMITE_CARACTERES, LIMITE_FRASES, "Fatos do Epic (JSON)"),
    "pauta": Tipo("d1", f"""{_CONTEXTO}
Escreva UMA manchete para a pauta da reunião sobre este Epic: uma única frase, no máximo 170 caracteres,
dizendo o que mudou ou o que está em jogo e por que importa. Comece pelo fato mais novo (risco novo ou que
piorou), se houver. Cite o id do Epic (#123).
{_REGRAS}""", 180, 1, "Fatos do Epic (JSON)"),
    "resumo": Tipo("d2", f"""{_CONTEXTO}
Escreva o RESUMO deste recorte (o painel inteiro, um programa ou uma categoria de risco) para a diretoria:
de 2 a 4 frases, no máximo 550 caracteres. Diga o tamanho do problema, onde o risco se concentra e o que
mudou desde o registro anterior.
{_REGRAS}""", 600, 4),
    "sugerida": Tipo("d1", f"""{_CONTEXTO}
Responda à pergunta usando só os fatos: de 2 a 4 frases, no máximo 550 caracteres, começando pela resposta
direta.
{_REGRAS}""", 600, 4),
    "pergunta": Tipo("d1", f"""{_CONTEXTO}
O apresentador da reunião fez a pergunta abaixo. Responda usando só os fatos: de 1 a 5 frases, no máximo
650 caracteres, começando pela resposta direta. Se os fatos não respondem à pergunta, responda exatamente:
Os dados do painel não respondem a isso.
{_REGRAS}""", 700, 5),
}


def mensagem_usuario(fatos_json: str, pergunta: str = "", rotulo: str = "Fatos do Epic (JSON)") -> str:
    texto = f"{rotulo}:\n{fatos_json}"
    return f"{texto}\n\nPergunta: {pergunta}" if pergunta else texto
