"""As 3 perguntas que a diretoria deveria fazer hoje: perguntas e fatos por regra, resposta pelo LLM.

Quando a regra não acha dados (nenhuma dependência entre programas, nada piorou), a resposta é
fixa e não passa pelo LLM.
"""
from collections import Counter
from dataclasses import dataclass

from .fatos import CATEGORIA, CRITICIDADE
from .recortes import gravidade

MAX_DEPENDENCIAS = 10
MAX_MUDANCAS = 15


@dataclass(frozen=True)
class Sugerida:
    alvo: str
    pergunta: str
    fatos: dict | None          # None = resposta fixa
    resposta_fixa: str = ""


def _criticos_por_programa(riscos: list[dict]) -> Sugerida:
    crit = Counter(l["programa"] for l in riscos if l["criticidade"] == "critico")
    esc = {p: len({l["epic_id"] for l in riscos if l["programa"] == p and l["escalar"] == "sim"}) for p in crit}
    mat = Counter(l["programa"] for l in riscos if l["estado"] == "materializado")
    pergunta = "Qual programa concentra mais riscos críticos?"
    if not crit:
        return Sugerida("programas", pergunta, None, "Nenhum risco Crítico nesta semana.")
    ranking = [{"programa": p, "riscos_criticos": n, "epics_no_escalar": esc[p], "riscos_de_prazo_materializados": mat[p]}
               for p, n in crit.most_common(5)]
    return Sugerida("programas", pergunta, {"total_de_riscos_criticos": sum(crit.values()),
                                           "programas_por_riscos_criticos": ranking})


def _dependencias(riscos: list[dict]) -> Sugerida:
    deps = sorted((l for l in riscos if l["categoria"] == "DEPENDENCIA"
                   and "dependencia_entre_programas" in l["gatilhos"]), key=gravidade)
    pergunta = "Quais dependências entre programas estão travando Epics?"
    if not deps:
        return Sugerida("dependencias", pergunta, None, "Nenhuma dependência entre programas nesta semana.")
    return Sugerida("dependencias", pergunta, {
        "epics_travados_por_outro_programa": len(deps),
        "dependencias": [{"epic": f"#{l['epic_id']}", "titulo": l["titulo"], "programa": l["programa"],
                          "criticidade": CRITICIDADE[l["criticidade"]], "evidencia": l["evidencia"]}
                         for l in deps[:MAX_DEPENDENCIAS]]})


def _pioraram(riscos: list[dict]) -> Sugerida:
    pergunta = "O que piorou desde o último registro?"
    if riscos and all(l["movimento"] == "novo" for l in riscos):
        return Sugerida("pioraram", pergunta, None, "Não há registro anterior para comparar.")
    mudou = sorted((l for l in riscos if l["movimento"] in ("novo", "piorou")), key=gravidade)
    if not mudou:
        return Sugerida("pioraram", pergunta, None, "Nenhum risco novo ou que piorou desde o registro anterior.")
    return Sugerida("pioraram", pergunta, {
        "riscos_novos": sum(l["movimento"] == "novo" for l in mudou),
        "riscos_que_pioraram": sum(l["movimento"] == "piorou" for l in mudou),
        "mais_graves": [{"epic": f"#{l['epic_id']}", "titulo": l["titulo"], "programa": l["programa"],
                         "categoria": CATEGORIA[l["categoria"]], "movimento": l["movimento"],
                         "criticidade": CRITICIDADE[l["criticidade"]],
                         **({"criticidade_anterior": CRITICIDADE[l["criticidade_anterior"]]}
                            if l.get("criticidade_anterior") else {}),
                         "evidencia": l["evidencia"]} for l in mudou[:MAX_MUDANCAS]]})


def sugeridas(linhas_riscos: list[dict]) -> list[Sugerida]:
    return [_criticos_por_programa(linhas_riscos), _dependencias(linhas_riscos), _pioraram(linhas_riscos)]
