"""Ponto de extensão para a narrativa por LLM (etapa 2 da spec).

O narrador recebe só a linha do relatório já calculada (números e motivos) e
devolve um texto curto. Ele nunca calcula previsão: a conta é do `previsao`.
Na v1 só existe o NarradorNulo; um narrador com LLM exigirá dados anonimizados.
"""
from typing import Protocol


class Narrador(Protocol):
    def narrar(self, linha: dict) -> str: ...


class NarradorNulo:
    def narrar(self, linha: dict) -> str:
        return ""
