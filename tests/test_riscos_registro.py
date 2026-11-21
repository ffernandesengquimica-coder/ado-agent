import csv
from datetime import date
from pathlib import Path

from conftest import item
from radar.dados import carregar
from riscos.registro import COLUNAS, csv_anterior, ler_csv, linhas_csv, montar, movimento, saidas

HOJE = date(2026, 11, 5)


def _cenario():
    return [
        item(1, "Epic", alvo="2026-09-01", responsavel=""),                        # materializado, atraso grande
        *[item(100 + k, "Product Backlog Item", pai=1, responsavel="") for k in range(31)],  # restante 31 → impacto alto
        item(2, "Epic"), *[item(200 + k, "Product Backlog Item", pai=2, responsavel="") for k in range(3)],
        item(3, "Epic", estado="Done", fechado="2026-10-01"),
    ]


def _registro(extracao, itens=None):
    d = carregar(extracao(itens or _cenario()))
    return d, montar(d, HOJE)


def test_um_risco_por_epic_e_categoria_com_id_estavel(extracao):
    _, riscos = _registro(extracao)
    ids = [r.id for r in riscos]
    assert ids == ["R-1-PRAZO", "R-1-CAPACIDADE", "R-2-CAPACIDADE", "R-2-GOVERNANCA"]
    assert len(set(ids)) == len(ids)


def test_risco_classificado_e_com_gatilhos(extracao):
    _, riscos = _registro(extracao)
    prazo = riscos[0]
    assert (prazo.estado, prazo.probabilidade, prazo.impacto, prazo.criticidade) == (
        "materializado", "alta", "alto", "critico")
    assert prazo.gatilhos == ("atraso_grande", "sem_dono")
    gov = riscos[3]
    assert (gov.impacto, gov.criticidade, gov.gatilhos) == ("baixo", "baixo", ())


def test_linhas_csv_tem_as_colunas_da_spec(extracao):
    d, riscos = _registro(extracao)
    linhas = linhas_csv(riscos, d, HOJE, [])
    assert list(linhas[0]) == COLUNAS
    l = linhas[0]
    assert (l["regras_versao"], l["data"], l["programa"], l["escalar"], l["gatilhos"], l["movimento"]) == (
        "r1", "2026-11-05", "Area", "sim", "atraso_grande; sem_dono", "novo")
    assert l["dono"] == "" and l["data_alvo"] == "2026-09-01"
    assert "data alvo vencida" in l["evidencia"]


def test_mesma_entrada_mesmo_csv(extracao):
    d, riscos = _registro(extracao)
    assert linhas_csv(riscos, d, HOJE, []) == linhas_csv(montar(d, HOJE), d, HOJE, [])


# --- Movimento ------------------------------------------------------------------------

def _ant(criticidade, estado="aberto"):
    return {"criticidade": criticidade, "estado": estado}


def test_os_movimentos(extracao):
    _, riscos = _registro(extracao)
    prazo, cap = riscos[0], riscos[1]          # crítico materializado; capacidade
    assert movimento(prazo, None) == "novo"
    assert movimento(prazo, _ant("critico", "materializado")) == "igual"
    assert movimento(prazo, _ant("alto", "materializado")) == "piorou"
    assert movimento(prazo, _ant("critico", "aberto")) == "piorou"         # virou materializado
    assert cap.criticidade == "critico"
    assert movimento(riscos[3], _ant("medio")) == "melhorou"               # baixo, antes médio


def test_saidas_com_os_dois_motivos(extracao):
    d, riscos = _registro(extracao)
    anteriores = [
        {"risco_id": "R-1-PRAZO", "epic_id": "1"},
        {"risco_id": "R-3-PRAZO", "epic_id": "3"},          # Epic 3 está Done
        {"risco_id": "R-2-ESCOPO", "epic_id": "2"},         # Epic aberto, sinal sumiu
        {"risco_id": "R-9-PRAZO", "epic_id": "9"},          # Epic não existe mais
    ]
    s = {x["risco_id"]: x["motivo_saida"] for x in saidas(riscos, anteriores, d)}
    assert s == {"R-3-PRAZO": "Epic fechado", "R-2-ESCOPO": "sinal desapareceu", "R-9-PRAZO": "Epic fechado"}


def test_csv_anterior_pega_o_mais_recente_antes_de_hoje(tmp_path):
    for nome in ["riscos-2026-10-22.csv", "riscos-2026-10-29.csv", "riscos-2026-11-05.csv",
                 "riscos-xx.csv", "radar-2026-11-01.csv"]:
        (tmp_path / nome).write_text("", encoding="utf-8")
    assert csv_anterior(tmp_path, HOJE).name == "riscos-2026-10-29.csv"
    assert csv_anterior(tmp_path, date(2026, 10, 22)) is None
    assert ler_csv(None) == []


def test_linhas_usam_a_criticidade_anterior(extracao):
    d, riscos = _registro(extracao)
    linhas = linhas_csv(riscos, d, HOJE, [{"risco_id": "R-2-GOVERNANCA", "criticidade": "medio", "estado": "aberto"}])
    gov = next(l for l in linhas if l["risco_id"] == "R-2-GOVERNANCA")
    assert (gov["movimento"], gov["criticidade_anterior"]) == ("melhorou", "medio")
    assert next(l for l in linhas if l["risco_id"] == "R-1-PRAZO")["criticidade_anterior"] == ""
