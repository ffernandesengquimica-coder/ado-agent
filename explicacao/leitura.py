"""Leitura por regra: o que significa cada valor de filtro do painel, com os números do recorte.

Sem LLM. Um texto por valor de filtro que existe nas linhas, com a chave "filtro:valor" que o JS
usa (os mesmos `data-filtro`/`data-valor` dos botões e selects de cada aba).
"""
from collections import Counter

from .fatos import CATEGORIA, CRITICIDADE, GATILHO, SECAO, _lista
from .recortes import ORDEM_CRITICIDADE, ORDEM_SECOES, programa

SIGNIFICADO_SECAO = {
    "vermelho": "menos de 40% de chance de cumprir a data alvo, ou data marcada sem escopo detalhado",
    "amarelo": "entre 40% e 70% de chance de cumprir a data alvo",
    "ja_atrasado": "a data alvo já passou e o Epic continua aberto",
    "sem_como_prever": "sem data alvo, ou nada entregue nas últimas 12 semanas",
    "verde": "70% ou mais de chance de cumprir a data alvo",
}
DEFINICAO_CATEGORIA = {
    "PRAZO": "o ritmo atual não fecha o restante até a data, ou o Epic está parado há 4 semanas",
    "DEPENDENCIA": "o Epic depende de um item de outro Epic que venceu ou está em risco de prazo",
    "CAPACIDADE": "20% ou mais dos itens restantes estão sem responsável",
    "ESCOPO": "data marcada sem itens detalhados, ou escopo que cresceu 20% ou mais em 4 semanas",
    "QUALIDADE": "Faults e Bugs abertos somam 20% ou mais do restante",
    "GOVERNANCA": "Epic aberto sem data alvo",
}
MATRIZ = {("alta", "alto"): "critico", ("alta", "medio"): "alto", ("alta", "baixo"): "medio",
          ("media", "alto"): "alto", ("media", "medio"): "medio", ("media", "baixo"): "baixo"}
NIVEL = {"alta": "alta", "media": "média", "alto": "alto", "medio": "médio", "baixo": "baixo"}


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _lista_contagem(c: Counter, rotulos: dict, ordem) -> str:
    return " · ".join(f"{rotulos[k]} {c[k]}" for k in ordem if c[k])


def _top(c: Counter, n: int = 3) -> str:
    return ", ".join(f"{k} ({v})" for k, v in c.most_common(n))


def leitura_radar(linhas: list[dict], faixa_de, rotulos_mes: dict[str, str]) -> dict[str, str]:
    """Textos dos filtros da aba Radar: seção, programa e mês da data alvo."""
    textos = {}
    for s in ORDEM_SECOES:
        ls = [l for l in linhas if l["secao"] == s]
        if ls:
            textos[f"secao:{s}"] = (f"{_plural(len(ls), 'Epic', 'Epics')} em \"{SECAO[s]}\" = {SIGNIFICADO_SECAO[s]}. "
                                    f"Programas com mais: {_top(Counter(programa(l['area']) for l in ls))}.")
    for p in sorted({programa(l["area"]) for l in linhas}):
        ls = [l for l in linhas if programa(l["area"]) == p]
        c = Counter(l["secao"] for l in ls)
        textos[f"programa:{p}"] = (f"{p}: {_plural(len(ls), 'Epic aberto', 'Epics abertos')} = "
                                   f"{_lista_contagem(c, SECAO, ORDEM_SECOES)}.")
    for chave, rotulo in rotulos_mes.items():
        ls = [l for l in linhas if faixa_de(l) == chave]
        if ls:
            c = Counter(l["secao"] for l in ls)
            textos[f"mes:{chave}"] = (f"{_plural(len(ls), 'Epic', 'Epics')} com data alvo {rotulo}: "
                                      f"{_lista_contagem(c, SECAO, ORDEM_SECOES)}.")
    return textos


def leitura_riscos(linhas: list[dict]) -> dict[str, str]:
    """Textos dos filtros da aba Riscos: criticidade, Escalar, materializado, célula, categoria, programa, Epic."""
    textos = {}
    for c in ORDEM_CRITICIDADE:
        ls = [l for l in linhas if l["criticidade"] == c]
        if ls:
            esc = sum(l["escalar"] == "sim" for l in ls)
            textos[f"criticidade:{c}"] = (
                f"{_plural(len(ls), 'risco', 'riscos')} {CRITICIDADE[c]} (probabilidade × impacto), "
                f"{esc} com marca Escalar. Categorias: {_lista_contagem(Counter(l['categoria'] for l in ls), CATEGORIA, CATEGORIA)}.")
    esc = [l for l in linhas if l["escalar"] == "sim"]
    if esc:
        gat = Counter(g for l in esc for g in _lista(l["gatilhos"]))
        textos["escalar:sim"] = (f"{_plural(len({l['epic_id'] for l in esc}), 'Epic', 'Epics')} "
                                 f"({_plural(len(esc), 'risco', 'riscos')}) com gatilho para a diretoria: "
                                 + " · ".join(f"{GATILHO[g]} {gat[g]}" for g in GATILHO if gat[g]) + ".")
    mat = [l for l in linhas if l["estado"] == "materializado"]
    if mat:
        textos["estado:materializado"] = (f"{_plural(len(mat), 'risco de prazo já aconteceu', 'riscos de prazo já aconteceram')}"
                                          f" (data alvo vencida, Epic aberto). Programas com mais: "
                                          f"{_top(Counter(l['programa'] for l in mat))}.")
    for (p, i), crit in MATRIZ.items():
        n = sum(l["probabilidade"] == p and l["impacto"] == i for l in linhas)
        if n:
            textos[f"celula:{p}-{i}"] = (f"{_plural(n, 'risco', 'riscos')} com probabilidade {NIVEL[p]} e impacto "
                                         f"{NIVEL[i]} = criticidade {CRITICIDADE[crit]}.")
    for cat in CATEGORIA:
        ls = [l for l in linhas if l["categoria"] == cat]
        if ls:
            c = Counter(l["criticidade"] for l in ls)
            textos[f"categoria:{cat}"] = (f"{CATEGORIA[cat]}: {DEFINICAO_CATEGORIA[cat]}. "
                                          f"{_plural(len(ls), 'risco', 'riscos')} = {_lista_contagem(c, CRITICIDADE, ORDEM_CRITICIDADE)}.")
    for p in sorted({l["programa"] for l in linhas}):
        ls = [l for l in linhas if l["programa"] == p]
        c = Counter(l["criticidade"] for l in ls)
        n_esc = len({l["epic_id"] for l in ls if l["escalar"] == "sim"})
        textos[f"programa:{p}"] = (f"{p}: {_plural(len(ls), 'risco', 'riscos')} em "
                                   f"{_plural(len({l['epic_id'] for l in ls}), 'Epic', 'Epics')} = "
                                   f"{_lista_contagem(c, CRITICIDADE, ORDEM_CRITICIDADE)}; "
                                   f"{_plural(n_esc, 'Epic', 'Epics')} no Escalar.")
    for e in sorted({int(l["epic_id"]) for l in linhas}):
        ls = [l for l in linhas if int(l["epic_id"]) == e]
        textos[f"epic:{e}"] = (f"Epic #{e}: " + " · ".join(
            f"{CATEGORIA[l['categoria']]} {CRITICIDADE[l['criticidade']]}" for l in ls) + ".")
    return textos
