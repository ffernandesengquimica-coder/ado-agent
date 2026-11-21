"""Fatos de cada Epic do Escalar, montados só com o que o Radar e o registro de riscos já calcularam.

A entrada são as linhas que viram `radar-*.csv` e `riscos-*.csv`. Os números saem formatados
como no painel (vírgula decimal, %, ×, dd/mm/aaaa): o validador compara a narrativa com este
texto, então o LLM precisa ver os números exatamente como a diretoria os vê.
"""
from datetime import date

SECAO = {"vermelho": "vão atrasar", "amarelo": "atenção", "ja_atrasado": "já atrasado",
         "sem_como_prever": "sem como prever", "verde": "no prazo"}
CATEGORIA = {"PRAZO": "Prazo", "DEPENDENCIA": "Dependência", "CAPACIDADE": "Capacidade",
             "ESCOPO": "Escopo", "QUALIDADE": "Qualidade", "GOVERNANCA": "Governança"}
CRITICIDADE = {"critico": "Crítico", "alto": "Alto", "medio": "Médio", "baixo": "Baixo"}
GATILHO = {"data_proxima": "data alvo em até 4 semanas", "dependencia_entre_programas": "dependência entre programas",
           "atraso_grande": "atrasado há mais de 8 semanas", "sem_dono": "Epic sem dono"}


def _vazio(x) -> bool:
    return x is None or x == ""


def _data(iso) -> str:
    iso = str(iso or "")
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


def _decimal(x, sufixo: str = "") -> str:
    return "" if _vazio(x) else f"{float(x):.1f}".replace(".", ",") + sufixo


def _lista(texto: str) -> list[str]:
    return [p.strip() for p in str(texto or "").split(";") if p.strip()]


def _area(area: str) -> str:
    return " › ".join(area.split("\\")[1:3]) or area


def _radar(l: dict) -> dict:
    prob = l.get("prob_cumprir")
    return {
        "situacao": SECAO.get(l["secao"], l["secao"]),
        "chance_de_cumprir_a_data": "" if _vazio(prob) else f"{float(prob):.0%}",
        "termino_provavel_pessimista": _data(l.get("p85")),
        "itens_no_escopo": int(l["escopo"]),
        "itens_restantes": int(l["restante"]),
        "itens_entregues_por_semana": _decimal(l.get("ritmo_medio")),
        "aceleracao_necessaria": _decimal(l.get("razao_ritmo"), "×"),
        "motivos": _lista(l.get("motivos")),
    }


def por_epic(linhas_riscos: list[dict]) -> dict[int, list[dict]]:
    grupos: dict[int, list[dict]] = {}
    for l in linhas_riscos:
        grupos.setdefault(int(l["epic_id"]), []).append(l)
    return grupos


def fatos_epic(epic_id: int, riscos: list[dict], radar: dict | None, hoje: date) -> dict:
    """Fatos de um Epic aberto qualquer (com riscos, só com Radar, ou os dois). Campos vazios saem do dict."""
    if riscos:
        r0 = riscos[0]
        titulo, area, alvo, dono = r0["titulo"], r0["area"], r0["data_alvo"], r0["dono"]
    else:
        titulo, area, alvo, dono = radar["titulo"], radar["area"], radar["data_alvo"], radar.get("responsavel", "")
    gatilhos = sorted({g for r in riscos for g in _lista(r["gatilhos"])}, key=list(GATILHO).index)
    f = {
        "hoje": _data(hoje.isoformat()),
        "epic": f"#{epic_id}",
        "titulo": titulo,
        "area": _area(area),
        "data_alvo": _data(alvo),
        "dono": dono or "sem dono",
        "por_que_escalar": [GATILHO[g] for g in gatilhos],
        "riscos": [{"categoria": CATEGORIA[r["categoria"]], "estado": r["estado"],
                    "probabilidade": r["probabilidade"], "criticidade": CRITICIDADE[r["criticidade"]],
                    "evidencia": r["evidencia"]} for r in riscos],
    }
    if radar is not None:
        f["radar"] = {k: v for k, v in _radar(radar).items() if not _vazio(v) and v != []}
    return {k: v for k, v in f.items() if not _vazio(v) and v != []}


def fatos_escalar(linhas_radar: list[dict], linhas_riscos: list[dict], hoje: date) -> dict[int, dict]:
    """epic_id → fatos, só para Epics com pelo menos um risco `escalar = sim`."""
    radar = {int(l["epic_id"]): l for l in linhas_radar}
    grupos = por_epic(linhas_riscos)
    return {e: fatos_epic(e, grupos[e], radar.get(e), hoje)
            for e in sorted(e for e, rs in grupos.items() if any(r["escalar"] == "sim" for r in rs))}


def evidencias(fatos: dict) -> list[str]:
    """Os fatos que o painel mostra embaixo da narrativa: motivos do Radar + evidências dos riscos, sem repetir."""
    vistos, saida = set(), []
    for texto in [*fatos.get("radar", {}).get("motivos", []),
                  *(f"{r['categoria']}: {r['evidencia']}" for r in fatos.get("riscos", []))]:
        if texto not in vistos:
            vistos.add(texto)
            saida.append(texto)
    return saida
