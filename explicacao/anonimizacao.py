"""Troca nomes de pessoas por "Pessoa A", "Pessoa B"… antes de qualquer envio ao LLM, e desfaz a troca.

As pessoas de um Epic são o dono do Epic (registro de riscos) e o responsável (Radar). A troca vale
em todos os campos de texto, inclusive no título, se o nome aparecer lá. O mapa nunca sai da máquina.
"""
import json
import re
from string import ascii_uppercase

_ALIAS = re.compile(r"\bPessoa [A-Z]\d*\b")


def pessoas(fatos: dict, extras: tuple[str, ...] = ()) -> list[str]:
    """Nomes a esconder, na ordem em que aparecem (o dono primeiro). 'sem dono' não é pessoa."""
    nomes = [fatos.get("dono", ""), *extras]
    vistos = []
    for n in nomes:
        n = (n or "").strip()
        if n and n != "sem dono" and n not in vistos:
            vistos.append(n)
    return vistos


def _trocar(valor, trocas: list[tuple[str, str]]):
    if isinstance(valor, str):
        for de, para in trocas:
            valor = valor.replace(de, para)
        return valor
    if isinstance(valor, list):
        return [_trocar(v, trocas) for v in valor]
    if isinstance(valor, dict):
        return {k: _trocar(v, trocas) for k, v in valor.items()}
    return valor


def _alias(i: int) -> str:
    """Pessoa A … Pessoa Z, depois Pessoa A1, Pessoa B1 …"""
    return f"Pessoa {ascii_uppercase[i % 26]}{i // 26 or ''}"


def _trocas(mapa: dict[str, str]) -> list[tuple[str, str]]:
    # Nomes mais longos primeiro: "Ana Maria" não pode virar "Pessoa B Maria" por causa de "Ana".
    return sorted(((n, a) for a, n in mapa.items()), key=lambda t: -len(t[0]))


def trocar_nomes(texto: str, mapa: dict[str, str]) -> str:
    """Aplica o mapa (alias → nome) num texto livre, como a pergunta do apresentador."""
    return _trocar(texto, _trocas(mapa))


def anonimizar(fatos: dict, extras: tuple[str, ...] = ()) -> tuple[str, dict[str, str]]:
    """(JSON estável dos fatos anonimizados, mapa alias → nome real)."""
    nomes = pessoas(fatos, extras)
    mapa = {_alias(i): n for i, n in enumerate(nomes)}
    texto = json.dumps(_trocar(fatos, _trocas(mapa)), ensure_ascii=False, sort_keys=True, indent=1)
    return texto, mapa


def desanonimizar(texto: str, mapa: dict[str, str]) -> str:
    return _ALIAS.sub(lambda m: mapa.get(m.group(0), m.group(0)), texto)
