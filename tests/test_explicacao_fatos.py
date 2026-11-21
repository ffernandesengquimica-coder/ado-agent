import json
from datetime import date

from explicacao.anonimizacao import anonimizar, desanonimizar
from explicacao.fatos import evidencias, fatos_escalar

HOJE = date(2026, 11, 11)


def _radar(epic_id, **kw):
    base = {"epic_id": epic_id, "secao": "vermelho", "prob_cumprir": 0.0, "p85": "2026-12-09", "escopo": 38,
            "restante": 3, "ritmo_medio": 1.33, "razao_ritmo": 3.25, "responsavel": "Zeca Exemplo",
            "motivos": "precisa entregar 3,2× mais rápido"}
    return {**base, **kw}


def _risco(epic_id, categoria="PRAZO", escalar="sim", **kw):
    base = {"epic_id": epic_id, "titulo": f"Epic {epic_id}", "area": "Atlas\\Area\\Time\\X",
            "categoria": categoria, "estado": "aberto", "probabilidade": "alta", "criticidade": "critico",
            "evidencia": "precisa entregar 3,2× mais rápido", "dono": "Zeca Exemplo", "data_alvo": "2026-11-13",
            "escalar": escalar, "gatilhos": "data_proxima" if escalar == "sim" else ""}
    return {**base, **kw}


def test_so_epics_do_escalar_com_todos_os_riscos_do_epic():
    riscos = [_risco(1), _risco(1, "CAPACIDADE", escalar="nao", criticidade="medio",
                                  evidencia="5 de 14 itens restantes sem responsável"),
              _risco(2, escalar="nao")]
    f = fatos_escalar([_radar(1), _radar(2)], riscos, HOJE)
    assert list(f) == [1]
    assert [r["categoria"] for r in f[1]["riscos"]] == ["Prazo", "Capacidade"]
    assert f[1]["por_que_escalar"] == ["data alvo em até 4 semanas"]


def test_numeros_formatados_como_no_painel():
    f = fatos_escalar([_radar(1)], [_risco(1)], HOJE)[1]
    assert f["hoje"] == "11/11/2026" and f["data_alvo"] == "13/11/2026" and f["epic"] == "#1"
    assert f["area"] == "Area › Time"
    r = f["radar"]
    assert (r["chance_de_cumprir_a_data"], r["termino_provavel_pessimista"], r["itens_entregues_por_semana"],
            r["aceleracao_necessaria"], r["situacao"]) == ("0%", "09/12/2026", "1,3", "3,2×", "vão atrasar")


def test_campos_vazios_saem_e_epic_sem_radar():
    f = fatos_escalar([_radar(1, prob_cumprir=None, p85="", razao_ritmo=None, motivos="")],
                      [_risco(1, dono=""), _risco(2)], HOJE)
    assert f[1]["dono"] == "sem dono"
    assert not {"chance_de_cumprir_a_data", "termino_provavel_pessimista", "aceleracao_necessaria",
                "motivos"} & set(f[1]["radar"])
    assert "radar" not in f[2]


def test_evidencias_sem_repetir():
    f = fatos_escalar([_radar(1)], [_risco(1)], HOJE)[1]
    assert evidencias(f) == ["precisa entregar 3,2× mais rápido", "Prazo: precisa entregar 3,2× mais rápido"]


def test_anonimizacao_esconde_nomes_em_todos_os_campos_e_desfaz():
    f = fatos_escalar([_radar(1)], [_risco(1, titulo="Painel do Zeca Exemplo")], HOJE)[1]
    texto, mapa = anonimizar(f, extras=("Bruna Lima",))
    assert "Zeca" not in texto and "Exemplo" not in texto
    assert mapa == {"Pessoa A": "Zeca Exemplo", "Pessoa B": "Bruna Lima"}
    assert json.loads(texto)["titulo"] == "Painel do Pessoa A"
    assert desanonimizar("Pessoa A segura o Epic; Pessoa Z não existe.", mapa) == \
        "Zeca Exemplo segura o Epic; Pessoa Z não existe."


def test_anonimizacao_estavel_e_sem_dono():
    f = fatos_escalar([_radar(1)], [_risco(1, dono="")], HOJE)[1]
    assert anonimizar(f) == anonimizar(dict(reversed(list(f.items()))))
    assert anonimizar(f)[1] == {}
