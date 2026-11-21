"""Causa provável dos Epics do Escalar, sobre o núcleo `llm` (tipo "causa").

O cache são os próprios `relatorios/narrativas-*.csv`, com o formato e as chaves de sempre: as
narrativas aprovadas em 2026-11-11 continuam valendo sem nova chamada.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import llm
from .prompt import PROMPT_VERSAO

COLUNAS = ["data", "epic_id", "chave", "modelo", "prompt_versao", "status", "motivo",
           "tokens_entrada", "tokens_saida", "narrativa"]
VALIDAS = llm.VALIDAS
Cliente = llm.Cliente


@dataclass(frozen=True)
class Narrativa:
    epic_id: int
    chave: str
    status: str             # "ok" | "rejeitada" | "erro" | "cache"
    texto: str              # anonimizado, como o modelo devolveu; vazio se não for válida
    exibicao: str = ""      # com os nomes reais: só para o HTML, nunca gravado
    motivo: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0


def chave(modelo: str, fatos_json: str) -> str:
    return llm.chave("causa", modelo, fatos_json)


def ler_cache(pasta: Path) -> dict[str, tuple[str, str]]:
    """chave → (status, narrativa anonimizada ou motivo da rejeição), de todos os `narrativas-*.csv`."""
    return llm.ler_cache(pasta, "narrativas-*.csv", "narrativa")


def gerar(fatos: dict[int, dict], modelo: str, cache: dict[str, tuple[str, str]], cliente: Cliente | None,
          extras: dict[int, tuple[str, ...]] | None = None) -> list[Narrativa]:
    """Uma narrativa por Epic. Sem cliente, só o que está no cache (os demais ficam de fora)."""
    extras = extras or {}
    pedidos = [llm.Pedido("causa", str(e), f, extras.get(e, ()), usa_radar="radar" in f) for e, f in fatos.items()]
    return [Narrativa(int(t.alvo), t.chave, t.status, t.texto, t.exibicao, t.motivo, t.tokens_entrada, t.tokens_saida)
            for t in llm.gerar(pedidos, modelo, cache, cliente)]


def linhas_csv(narrativas: list[Narrativa], hoje: date, modelo: str) -> list[dict]:
    return [{"data": hoje.isoformat(), "epic_id": n.epic_id, "chave": n.chave, "modelo": modelo,
             "prompt_versao": PROMPT_VERSAO, "status": n.status, "motivo": n.motivo,
             "tokens_entrada": n.tokens_entrada, "tokens_saida": n.tokens_saida, "narrativa": n.texto}
            for n in narrativas]


def para_painel(narrativas: list[Narrativa]) -> dict[int, str]:
    """epic_id → texto com nomes reais, só das narrativas válidas."""
    return {n.epic_id: n.exibicao for n in narrativas if n.status in VALIDAS and n.exibicao}


def resumo(narrativas: list[Narrativa], total: int, segundos: float) -> str:
    conta = {s: sum(n.status == s for n in narrativas) for s in ("ok", "cache", "rejeitada", "erro")}
    tokens = sum(n.tokens_entrada + n.tokens_saida for n in narrativas)
    sem = total - len(narrativas)
    return (f"Narrativas: {total} Epics no Escalar = {conta['ok'] + conta['cache']} válidas "
            f"({conta['cache']} do cache) + {conta['rejeitada']} rejeitadas + {conta['erro']} com erro"
            + (f" + {sem} sem narrativa (sem LLM)" if sem else "")
            + f" | {tokens:,} tokens | {segundos:.0f} s".replace(",", "."))
