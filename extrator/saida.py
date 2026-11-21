"""Escrita de CSV e conversão de HTML para texto."""
import csv
import re
from html.parser import HTMLParser
from pathlib import Path


class Tabela:
    """Escreve um CSV linha a linha, com colunas fixas."""

    def __init__(self, caminho: Path, colunas: list[str], encoding: str):
        self.caminho = caminho
        self._arquivo = caminho.open("w", encoding=encoding, newline="")
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=colunas)
        self._escritor.writeheader()
        self.linhas = 0

    def escrever(self, linha: dict) -> None:
        self._escritor.writerow(linha)
        self.linhas += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._arquivo.close()


_BLOCOS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table"}


class _Extrator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCOS:
            self.partes.append("\n")
        elif tag == "td":
            self.partes.append(" | ")

    def handle_data(self, data):
        self.partes.append(data)


def html_para_texto(html: str | None) -> str:
    if not html:
        return ""
    p = _Extrator()
    p.feed(html)
    texto = "".join(p.partes).replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    return re.sub(r"\s*\n\s*", "\n", texto).strip()


def identidade(valor) -> tuple[str, str]:
    """Campos de identidade vêm como dict; devolve (nome, email)."""
    if isinstance(valor, dict):
        return valor.get("displayName", ""), valor.get("uniqueName", "")
    return (valor or "", "")
