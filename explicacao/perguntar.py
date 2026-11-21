"""Modo apresentador: uma pergunta livre vira um pedido ao LLM com os fatos do recorte que ela cita.

O recorte sai por regra, sem acento e sem diferenciar maiúsculas, nesta ordem: Epic (`#id` ou
número de um Epic aberto), programa (nome ou sigla de 3+ letras), categoria de risco, ou o painel
inteiro. Toda pessoa conhecida (donos e responsáveis) é anonimizada, nos fatos e na pergunta.
O CSV do dia guarda a pergunta e a resposta como o apresentador as viu (é um arquivo local, como
o registro de riscos); para a OpenAI só vai a versão anonimizada.
"""
import csv
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from .fatos import CATEGORIA, fatos_epic, por_epic
from .llm import Pedido
from .recortes import fatos_recorte, programa

COLUNAS = ["data", "hora", "pergunta", "recorte", "status", "motivo", "tokens_entrada", "tokens_saida",
           "resposta", "usa_radar"]
_PALAVRAS_CATEGORIA = {"PRAZO": ("prazo", "prazos"), "DEPENDENCIA": ("dependencia", "dependencias"),
                       "CAPACIDADE": ("capacidade",), "ESCOPO": ("escopo", "escopos"),
                       "QUALIDADE": ("qualidade",), "GOVERNANCA": ("governanca",)}
_LIGACOES = {"and", "e", "de", "da", "do", "of", "the"}


def _norm(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower()


def sigla(nome: str) -> str:
    return "".join(p[0] for p in re.findall(r"[A-Za-z]+", nome) if p.lower() not in _LIGACOES).lower()


def recorte(pergunta: str, linhas_radar: list[dict], linhas_riscos: list[dict]) -> tuple[str, str | int | None]:
    """("epic", id) | ("programa", nome) | ("categoria", código) | ("geral", None)."""
    q = _norm(pergunta)
    epics = {int(l["epic_id"]) for l in linhas_radar} | {int(l["epic_id"]) for l in linhas_riscos}
    # Com "#", qualquer id; sem "#", só números de 3+ dígitos ("os 2 riscos" não é o Epic 2).
    for n in re.findall(r"#(\d+)|\b(\d{3,7})\b", q):
        if int(n[0] or n[1]) in epics:
            n = n[0] or n[1]
            return "epic", int(n)
    programas = sorted({programa(l["area"]) for l in linhas_radar} | {l["programa"] for l in linhas_riscos},
                       key=len, reverse=True)
    palavras = set(re.findall(r"[a-z0-9]+", q))
    # A raiz da área é o próprio projeto: não vale como programa na pergunta.
    raizes = {l["area"].split("\\")[0] for l in [*linhas_radar, *linhas_riscos] if l.get("area")}
    for p in programas:
        if p not in raizes and (_norm(p) in q or (len(sigla(p)) >= 3 and sigla(p) in palavras)):
            return "programa", p
    for c, termos in _PALAVRAS_CATEGORIA.items():
        if palavras & set(termos):
            return "categoria", c
    return "geral", None


def nomes(linhas_radar: list[dict], linhas_riscos: list[dict]) -> tuple[str, ...]:
    """Todas as pessoas conhecidas, para esconder na pergunta e nos fatos."""
    return tuple(sorted({l.get("responsavel", "") for l in linhas_radar} | {l["dono"] for l in linhas_riscos} - {""}))


def pedido(pergunta: str, linhas_radar: list[dict], linhas_riscos: list[dict], hoje: date) -> tuple[Pedido, str]:
    """(pedido ao LLM, rótulo do recorte para o CSV)."""
    tipo, valor = recorte(pergunta, linhas_radar, linhas_riscos)
    extras = nomes(linhas_radar, linhas_riscos)
    if tipo == "epic":
        radar = next((l for l in linhas_radar if int(l["epic_id"]) == valor), None)
        fatos = fatos_epic(valor, por_epic(linhas_riscos).get(valor, []), radar, hoje)
        return Pedido("pergunta", f"epic:{valor}", fatos, extras, radar is not None, pergunta), f"Epic #{valor}"
    if tipo == "programa":
        fatos, usa = fatos_recorte(linhas_radar, linhas_riscos, hoje, programa_=valor)
        return Pedido("pergunta", f"programa:{valor}", fatos, extras, usa, pergunta), f"programa {valor}"
    if tipo == "categoria":
        fatos, usa = fatos_recorte(linhas_radar, linhas_riscos, hoje, categoria=valor)
        return Pedido("pergunta", f"categoria:{valor}", fatos, extras, usa, pergunta), f"categoria {CATEGORIA[valor]}"
    fatos, usa = fatos_recorte(linhas_radar, linhas_riscos, hoje)
    return Pedido("pergunta", "geral", fatos, extras, usa, pergunta), "painel inteiro"


def arquivo(pasta: Path, hoje: date) -> Path:
    return pasta / f"perguntas-{hoje.isoformat()}.csv"


def registrar(pasta: Path, hoje: date, pergunta: str, rotulo: str, texto, agora: datetime | None = None) -> dict:
    """Acrescenta a pergunta (e a resposta, se válida) ao CSV do dia."""
    linha = {"data": hoje.isoformat(), "hora": (agora or datetime.now()).strftime("%H:%M"), "pergunta": pergunta,
             "recorte": rotulo, "status": texto.status, "motivo": texto.motivo,
             "tokens_entrada": texto.tokens_entrada, "tokens_saida": texto.tokens_saida,
             "resposta": texto.exibicao if texto.valido else "", "usa_radar": "sim" if texto.usa_radar else "nao"}
    caminho = arquivo(pasta, hoje)
    novo = not caminho.exists()
    pasta.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8-sig" if novo else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            w.writeheader()
        w.writerow(linha)
    return linha


def validas_do_dia(pasta: Path, hoje: date) -> list[dict]:
    """Perguntas respondidas do dia, a mais recente primeiro, no formato do painel."""
    caminho = arquivo(pasta, hoje)
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        linhas = [l for l in csv.DictReader(f) if l["status"] in ("ok", "cache") and l["resposta"]]
    return [{"hora": l["hora"], "pergunta": l["pergunta"], "resposta": l["resposta"],
             "usa_radar": l["usa_radar"] == "sim"} for l in reversed(linhas)]
