"""Pauta da semana: até 5 Epics do Escalar escolhidos por regra; o LLM só escreve a manchete.

Pontuação: +3 se algum risco do Epic é novo ou piorou; +2 se há dependência entre programas;
+1 por gatilho além do primeiro. Desempate pela gravidade (materializado, criticidade, data alvo).
"""
from .fatos import CATEGORIA, GATILHO, _lista
from .recortes import gravidade

MAX_PONTOS = 5
MOVIMENTO = {"novo": "risco novo", "piorou": "piorou", "melhorou": "melhorou", "igual": "sem mudança"}


def _gatilhos(riscos: list[dict]) -> list[str]:
    return sorted({g for r in riscos for g in _lista(r["gatilhos"])}, key=list(GATILHO).index)


def pontos(riscos: list[dict]) -> int:
    gat = _gatilhos(riscos)
    return (3 * any(r["movimento"] in ("novo", "piorou") for r in riscos)
            + 2 * ("dependencia_entre_programas" in gat) + max(0, len(gat) - 1))


def escolher(linhas_riscos: list[dict]) -> list[int]:
    """Ids dos Epics da pauta, do mais importante para o menos."""
    grupos: dict[int, list[dict]] = {}
    for l in linhas_riscos:
        grupos.setdefault(int(l["epic_id"]), []).append(l)
    candidatos = [e for e, rs in grupos.items() if any(r["escalar"] == "sim" for r in rs)]
    ordem = sorted(candidatos, key=lambda e: (-pontos(grupos[e]), min(gravidade(r) for r in grupos[e]), e))
    return ordem[:MAX_PONTOS]


def fatos_ponto(fatos: dict, riscos: list[dict]) -> dict:
    """Fatos do Epic (os mesmos da causa provável) + o movimento de cada risco."""
    return {**fatos, "movimento_dos_riscos": [f"{CATEGORIA[r['categoria']]}: {MOVIMENTO[r['movimento']]}"
                                              for r in riscos]}


def manchete_regra(epic_id: int, riscos: list[dict]) -> str:
    """Fallback sem LLM: '#id título — gatilhos'."""
    return f"#{epic_id} {riscos[0]['titulo']} — " + "; ".join(GATILHO[g] for g in _gatilhos(riscos))
