"""Núcleo de LLM, recortes, pauta, perguntas sugeridas e leitura por regra (Dashboard Inteligente)."""
from collections import Counter
from datetime import date

from explicacao import leitura, llm, pauta, recortes, sugeridas
from explicacao.anonimizacao import anonimizar
from explicacao.cliente_openai import Resposta
from explicacao.narrativas import chave as chave_causa

HOJE = date(2026, 11, 11)


def risco(epic, categoria="PRAZO", *, programa="Rede Norte", crit="critico", escalar="nao", gatilhos="",
          movimento="igual", estado="aberto", prob="alta", impacto="alto", anterior="", dono="Ana Souza",
          evidencia="precisa entregar 3,2× mais rápido", alvo="2026-11-30"):
    return {"epic_id": epic, "titulo": f"Epic {epic}", "programa": programa, "area": f"Atlas\\{programa}\\Time",
            "categoria": categoria, "estado": estado, "probabilidade": prob, "impacto": impacto, "criticidade": crit,
            "evidencia": evidencia, "dono": dono, "data_alvo": alvo, "escalar": escalar, "gatilhos": gatilhos,
            "movimento": movimento, "criticidade_anterior": anterior}


def radar(epic, programa="Rede Norte", secao="vermelho", alvo="2026-11-30"):
    return {"epic_id": epic, "titulo": f"Epic {epic}", "area": f"Atlas\\{programa}\\Time", "secao": secao,
            "data_alvo": alvo, "responsavel": "Ana Souza", "prob_cumprir": 0.1, "p85": "2027-01-10", "escopo": 10,
            "restante": 6, "ritmo_medio": 1.0, "razao_ritmo": 2.0, "motivos": ""}


RISCOS = [
    risco(1, escalar="sim", gatilhos="data_proxima", movimento="piorou", anterior="alto"),
    risco(1, "DEPENDENCIA", escalar="sim", gatilhos="dependencia_entre_programas", movimento="novo",
          evidencia="depende de #900 (Feature, Canais), vencida em 30/10/2026"),
    risco(2, "CAPACIDADE", programa="Canais", crit="medio", prob="media", impacto="medio",
          evidencia="5 de 14 itens restantes sem responsável"),
    risco(3, escalar="sim", gatilhos="atraso_grande", estado="materializado", programa="Canais"),
    risco(4, escalar="sim", gatilhos="sem_dono", dono=""),
]
RADAR = [radar(1), radar(2, "Canais", "amarelo"), radar(3, "Canais", "ja_atrasado", "2026-08-01"), radar(5, secao="verde")]


class Falso:
    modelo = "m"

    def __init__(self, texto="Texto."):
        self.texto, self.recebido = texto, []

    def completar(self, sistema, usuario):
        self.recebido.append((sistema, usuario))
        return Resposta(self.texto, 10, 5)


# --- núcleo -------------------------------------------------------------------------------

def test_chave_da_causa_provavel_nao_mudou():
    fatos_json, _ = anonimizar({"epic": "#1", "dono": "Ana"})
    assert llm.chave("causa", "m", fatos_json) == chave_causa("m", fatos_json)
    assert llm.chave("resumo", "m", fatos_json) != llm.chave("pauta", "m", fatos_json)


def test_pergunta_anonimizada_e_numeros_da_pergunta_valem():
    cliente = Falso("Pessoa A cuida do #1 desde 2025.")
    [t] = llm.gerar([llm.Pedido("pergunta", "geral", {"epic": "#1"}, extras=("Ana Souza",),
                                pergunta="o que a Ana Souza fez desde 2025?")], "m", {}, cliente)
    assert "Ana" not in cliente.recebido[0][1] and "Pessoa A" in cliente.recebido[0][1]
    assert t.status == "ok" and t.exibicao == "Ana Souza cuida do #1 desde 2025."


def test_limites_por_tipo():
    longa = "Uma frase. Outra frase."
    [t] = llm.gerar([llm.Pedido("pauta", "1", {"epic": "#1"})], "m", {}, Falso(longa))
    assert t.status == "rejeitada" and "frases demais" in t.motivo
    [t] = llm.gerar([llm.Pedido("resumo", "geral", {"epic": "#1"})], "m", {}, Falso(longa))
    assert t.status == "ok"


def test_cache_de_textos(tmp_path):
    import csv
    ts = llm.gerar([llm.Pedido("resumo", "geral", {"x": "1"}, usa_radar=True)], "m", {}, Falso("Resumo no prazo."))
    linhas = llm.linhas_csv(ts, HOJE, "m")
    with (tmp_path / "textos-2026-11-11.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=llm.COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    outro = Falso()
    [t] = llm.gerar([llm.Pedido("resumo", "geral", {"x": "1"}, usa_radar=True)], "m", llm.ler_cache(tmp_path), outro)
    assert outro.recebido == [] and (t.status, t.exibicao, t.usa_radar) == ("cache", "Resumo no prazo.", True)
    assert "válidos (1 do cache)" in llm.contagem([t])


# --- recortes -----------------------------------------------------------------------------

def test_fatos_recorte_geral_programa_e_categoria():
    geral, usa = recortes.fatos_recorte(RADAR, RISCOS, HOJE)
    assert usa and geral["riscos"] == 5 and geral["epics_com_risco"] == 4 and geral["epics_no_escalar"] == 3
    assert geral["riscos_por_criticidade"] == {"Crítico": 4, "Médio": 1}
    assert geral["movimento_desde_o_registro_anterior"] == {"novos": 1, "pioraram": 1}
    assert geral["epics_mais_graves"][0]["epic"] == "#3"          # materializado primeiro
    assert geral["radar_epics_abertos_por_situacao"] == {"vão atrasar": 1, "atenção": 1, "já atrasado": 1, "no prazo": 1}
    q, _ = recortes.fatos_recorte(RADAR, RISCOS, HOJE, programa_="Canais")
    assert q["riscos"] == 2 and "programas_com_mais_riscos" not in q
    assert q["radar_epics_abertos_por_situacao"] == {"atenção": 1, "já atrasado": 1}
    d, _ = recortes.fatos_recorte(RADAR, RISCOS, HOJE, categoria="DEPENDENCIA")
    assert d["riscos"] == 1 and "riscos_por_categoria" not in d and d["recorte"] == "categoria Dependência"
    assert "Ana" not in str(geral)
    assert [a for a, _, _ in recortes.recortes(RISCOS)] == [
        "geral", "programa:Canais", "programa:Rede Norte", "categoria:PRAZO", "categoria:DEPENDENCIA",
        "categoria:CAPACIDADE"]


# --- pauta --------------------------------------------------------------------------------

def test_pauta_pontuacao_e_desempate():
    # Epic 1: novo/piorou (+3) + dependência entre programas (+2) + 2º gatilho (+1) = 6.
    # Epics 3 e 4 empatam em 0: o materializado (3) vem antes. Epic 2 não está no Escalar.
    assert pauta.escolher(RISCOS) == [1, 3, 4]
    muitos = [risco(e, escalar="sim", gatilhos="data_proxima") for e in range(10, 20)]
    assert len(pauta.escolher(muitos)) == pauta.MAX_PONTOS


def test_pauta_fatos_e_manchete_de_regra():
    rs = [r for r in RISCOS if r["epic_id"] == 1]
    assert pauta.fatos_ponto({"epic": "#1"}, rs)["movimento_dos_riscos"] == ["Prazo: piorou", "Dependência: risco novo"]
    assert pauta.manchete_regra(1, rs) == "#1 Epic 1 — data alvo em até 4 semanas; dependência entre programas"


# --- perguntas sugeridas ------------------------------------------------------------------

def test_sugeridas_com_fatos_e_respostas_fixas():
    s = {x.alvo: x for x in sugeridas.sugeridas(RISCOS)}
    assert s["programas"].fatos["programas_por_riscos_criticos"][0] == {
        "programa": "Rede Norte", "riscos_criticos": 3, "epics_no_escalar": 2, "riscos_de_prazo_materializados": 0}
    assert s["dependencias"].fatos["dependencias"][0]["epic"] == "#1"
    assert s["pioraram"].fatos["riscos_novos"] == 1 and s["pioraram"].fatos["riscos_que_pioraram"] == 1
    calmo = [risco(9, crit="medio")]
    f = {x.alvo: x for x in sugeridas.sugeridas(calmo)}
    assert f["dependencias"].resposta_fixa == "Nenhuma dependência entre programas nesta semana."
    assert f["pioraram"].resposta_fixa == "Nenhum risco novo ou que piorou desde o registro anterior."
    assert f["programas"].resposta_fixa == "Nenhum risco Crítico nesta semana."
    primeiro = [risco(9, movimento="novo")]
    assert sugeridas.sugeridas(primeiro)[2].resposta_fixa == "Não há registro anterior para comparar."


# --- leitura por regra --------------------------------------------------------------------

def test_leitura_riscos_bate_com_as_linhas():
    t = leitura.leitura_riscos(RISCOS)
    assert t["criticidade:critico"].startswith("4 riscos Crítico (probabilidade × impacto), 4 com marca Escalar")
    assert t["escalar:sim"].startswith("3 Epics (4 riscos) com gatilho para a diretoria: data alvo em até 4 semanas 1")
    assert t["estado:materializado"].startswith("1 risco de prazo já aconteceu")
    assert t["celula:alta-alto"] == "4 riscos com probabilidade alta e impacto alto = criticidade Crítico."
    assert t["programa:Canais"] == "Canais: 2 riscos em 2 Epics = Crítico 1 · Médio 1; 1 Epic no Escalar."
    assert t["epic:1"] == "Epic #1: Prazo Crítico · Dependência Crítico."
    assert "celula:media-baixo" not in t


def test_leitura_radar_por_secao_programa_e_mes():
    faixa = lambda l: "vencida" if l["data_alvo"] < HOJE.isoformat() else "2026-11"
    t = leitura.leitura_radar(RADAR, faixa, {"vencida": "já vencida", "2026-11": "em nov/26", "sem": "não definida"})
    assert t["secao:vermelho"].startswith('1 Epic em "vão atrasar" = menos de 40% de chance')
    assert t["programa:Canais"] == "Canais: 2 Epics abertos = atenção 1 · já atrasado 1."
    assert t["mes:vencida"] == "1 Epic com data alvo já vencida: já atrasado 1."
    assert "mes:sem" not in t
    assert Counter(k.split(":")[0] for k in t) == {"secao": 4, "programa": 2, "mes": 2}
