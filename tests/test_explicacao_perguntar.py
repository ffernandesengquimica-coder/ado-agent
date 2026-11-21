"""Modo apresentador e partes do HTML alimentadas pelo agente (Dashboard Inteligente)."""
import json
import re
from datetime import date, datetime

import pytest

from explicacao import llm, perguntar
from explicacao.cliente_openai import Resposta
from radar import painel_agente
from test_explicacao_dashboard import RADAR, RISCOS, Falso, radar, risco

HOJE = date(2026, 11, 11)


@pytest.mark.parametrize("pergunta, esperado", [
    ("o que houve com o #3?", ("epic", 3)),
    ("e o épico 1, como está?", ("geral", None)),            # número curto demais não é Epic
    ("Por que REDE NORTE piorou?", ("programa", "Rede Norte")),
    ("quais dependências preocupam?", ("categoria", "DEPENDENCIA")),
    ("como está o projeto?", ("geral", None)),
])
def test_recorte_da_pergunta(pergunta, esperado):
    assert perguntar.recorte(pergunta, RADAR, RISCOS) == esperado


def test_recorte_por_sigla_e_id_longo():
    rs = [risco(90005, programa="Plataforma Digital Base"), risco(5, programa="Obras Sul")]
    assert perguntar.recorte("por que o PDB está crítico?", [], rs) == ("programa", "Plataforma Digital Base")
    assert perguntar.recorte("e o 90005?", [], rs) == ("epic", 90005)
    # Sigla de 2 letras ("os") não vale: é palavra comum em português.
    assert perguntar.recorte("os riscos da semana", [], rs) == ("geral", None)


def test_pergunta_e_fatos_sem_nomes():
    pedido, rotulo = perguntar.pedido("o que a Ana Souza está fazendo no #3?", RADAR, RISCOS, HOJE)
    assert rotulo == "Epic #3" and pedido.tipo == "pergunta" and pedido.usa_radar
    cliente = Falso("Pessoa A é a dona do #3, com prazo vencido.")
    [t] = llm.gerar([pedido], "m", {}, cliente)
    enviado = cliente.recebido[0][1]
    assert "Ana" not in enviado and "Souza" not in enviado
    assert t.valido and t.exibicao == "Ana Souza é a dona do #3, com prazo vencido."
    assert not t.usa_radar                                  # não cita o Radar → sem selo


def test_registrar_acumula_e_painel_so_ve_validas(tmp_path):
    ok = llm.Texto("pergunta", "geral", "k", "ok", "x", "Resposta com chance de 10%.", usa_radar=True)
    ruim = llm.Texto("pergunta", "geral", "k2", "rejeitada", motivo="número fora dos fatos: 99")
    perguntar.registrar(tmp_path, HOJE, "primeira?", "painel inteiro", ok, datetime(2026, 11, 11, 9, 5))
    perguntar.registrar(tmp_path, HOJE, "segunda?", "painel inteiro", ruim, datetime(2026, 11, 11, 9, 7))
    perguntar.registrar(tmp_path, HOJE, "terceira?", "painel inteiro", ok, datetime(2026, 11, 11, 9, 9))
    texto = (tmp_path / "perguntas-2026-11-11.csv").read_text(encoding="utf-8-sig")
    assert texto.count("\n") == 4 and "número fora dos fatos: 99" in texto
    assert [q["pergunta"] for q in perguntar.validas_do_dia(tmp_path, HOJE)] == ["terceira?", "primeira?"]
    assert perguntar.validas_do_dia(tmp_path, date(2026, 11, 12)) == []


# --- HTML do agente -----------------------------------------------------------------------

def _agente():
    return painel_agente.Agente(
        pauta=[{"epic": 1, "texto": "Epic #1 piorou <b>muito</b>", "usa_radar": True}],
        sugeridas=[{"pergunta": "O que piorou?", "resposta": "Nada.", "usa_radar": False}],
        perguntas=[{"hora": "09:05", "pergunta": "e o #1?", "resposta": "Atrasado.", "usa_radar": False}],
        leitura={"radar": {"secao:vermelho": "1 Epic"}, "riscos": {}},
        resumos={"geral": {"t": "Resumo.", "radar": True}},
        epics=painel_agente.dados_epics([radar(1)], [risco(1)],
                                        {1: "Causa com chance de 10%."}))


def test_topo_escapa_e_selo_so_onde_usa_radar(monkeypatch):
    monkeypatch.setattr(painel_agente, "RADAR_APROVADO", False)
    html = painel_agente.topo(_agente())
    assert "Epic #1 piorou &lt;b&gt;muito&lt;/b&gt;" in html and 'data-ir-epic="1"' in html
    assert html.count("previsão em validação</span>") == 1
    assert 'Perguntas desta reunião (<span id="pq-n">1</span>)' in html and "Textos do agente em validação" in html
    monkeypatch.setattr(painel_agente, "RADAR_APROVADO", True)
    monkeypatch.setattr(painel_agente, "AGENTE_APROVADO", True)
    html = painel_agente.topo(_agente())
    assert "previsão em validação</span>" not in html and "Textos do agente em validação" not in html
    assert painel_agente.topo(painel_agente.Agente()) == ""


def test_chat_traz_a_conversa_do_dia_na_ordem_e_escapada(monkeypatch):
    monkeypatch.setattr(painel_agente, "RADAR_APROVADO", False)
    agente = painel_agente.Agente(perguntas=[      # como vem de `validas_do_dia`: a mais recente primeiro
        {"hora": "09:40", "pergunta": "e o <b>#2</b>?", "resposta": "Chance de 10%.", "usa_radar": True},
        {"hora": "09:05", "pergunta": "e o #1?", "resposta": "Atrasado.", "usa_radar": False}])
    html = painel_agente.chat(agente)
    assert 'id="chat-janela"' in html and 'id="pq-form"' in html and 'id="pq-off" hidden' in html
    assert html.index("e o #1?") < html.index("Atrasado.") < html.index("e o &lt;b&gt;#2&lt;/b&gt;?") < html.index("Chance de 10%.")
    assert html.count("previsão em validação</span>") == 1
    vazio = painel_agente.chat(painel_agente.Agente())           # sem perguntas ainda: só a saudação e o campo
    assert vazio.count('class="chat-m ') == 1 and 'id="pq-form"' in vazio


def test_json_embutido_nao_fecha_o_script():
    a = _agente()
    a.epics["1"]["t"] = "</script><script>alert(1)</script>"
    bloco = painel_agente.dados_script(a)
    assert bloco.count("</script>") == 1
    dados = json.loads(re.search(r">(.*)</script>", bloco).group(1))
    assert dados["epics"]["1"]["t"] == "</script><script>alert(1)</script>"
    assert dados["epics"]["1"]["cr"] is True and dados["epics"]["1"]["radar"]["c"] == "10%"


def test_painel_completo_com_agente(extracao):
    from conftest import item
    from radar.dados import carregar
    from radar.relatorio import gerar_html, linhas_relatorio
    d = carregar(extracao([item(1, "Epic", alvo="2026-12-30"), item(2, "Product Backlog Item", pai=1)]))
    linhas = linhas_relatorio(d, HOJE)
    html = gerar_html(linhas, HOJE, "x", riscos_html="<p>riscos</p>", agente=_agente())
    assert html.index("Pauta da semana") < html.index('role="tablist"')
    assert 'class="cartao leitura" data-aba="radar"' in html and 'id="gaveta"' in html
    assert 'data-epic="1"' in html and 'id="agente-dados"' in html
    sem = gerar_html(linhas, HOJE, "x", riscos_html="<p>riscos</p>")
    assert "Pauta da semana" not in sem and "agente-dados" not in sem
