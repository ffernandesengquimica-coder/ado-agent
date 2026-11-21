"""Validador determinístico da narrativa: nada pode aparecer no texto que não esteja nos fatos enviados.

Datas e ids são tirados do texto antes de procurar números, para que "13/11/2026" seja conferida
como data inteira e não como os números 13, 11 e 2026 soltos.
"""
import re

from .prompt import LIMITE_CARACTERES, LIMITE_FRASES

_DATA = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_ID = re.compile(r"#\d+")
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?%?")
_PESSOA = re.compile(r"\bPessoa [A-Z]\d*\b")
_FIM_DE_FRASE = re.compile(r"[.!?](?:\s|$)")


def _tokens(texto: str) -> tuple[set[str], set[str], set[str]]:
    datas = set(_DATA.findall(texto))
    ids = set(_ID.findall(texto))
    resto = _ID.sub(" ", _DATA.sub(" ", texto))
    return datas, ids, set(_NUMERO.findall(resto))


# Termos que só existem na previsão do Radar: o selo "previsão em validação" só aparece se o texto usa um deles.
_TERMOS_RADAR = ("radar", "chance", "vão atrasar", "vai atrasar", "já atrasad", "sem como prever", "no prazo",
                 "término", "termino", "pessimista")


def cita_radar(texto: str) -> bool:
    t = texto.lower()
    return any(termo in t for termo in _TERMOS_RADAR)


def frases(texto: str) -> int:
    return len(_FIM_DE_FRASE.findall(texto.strip())) or (1 if texto.strip() else 0)


def rejeicoes(texto: str, fatos_texto: str, pessoas: set[str],
              limite_caracteres: int = LIMITE_CARACTERES, limite_frases: int = LIMITE_FRASES) -> list[str]:
    """Lista vazia = narrativa válida. `pessoas` = aliases do Epic ("Pessoa A", …)."""
    if not texto.strip():
        return ["resposta vazia"]
    datas_f, ids_f, numeros_f = _tokens(fatos_texto)
    datas, ids, numeros = _tokens(texto)
    # "13/11" vale se for o começo de uma data dos fatos ("13/11/2026").
    erros = [f"data fora dos fatos: {d}" for d in sorted(datas - datas_f)
             if not any(f.startswith(d + "/") for f in datas_f)]
    erros += [f"id fora dos fatos: {i}" for i in sorted(ids - ids_f)]
    erros += [f"número fora dos fatos: {n}" for n in sorted(numeros - numeros_f)]
    erros += [f"pessoa desconhecida: {p}" for p in sorted(set(_PESSOA.findall(texto)) - pessoas)]
    if len(texto) > limite_caracteres:
        erros.append(f"texto longo: {len(texto)} caracteres")
    if frases(texto) > limite_frases:
        erros.append(f"frases demais: {frases(texto)}")
    return erros
