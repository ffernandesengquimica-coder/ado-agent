"""Servidor local do painel: entrega a página e só aceita pergunta vinda dela."""
import http.client
import json
import threading

import pytest

from radar import servidor


@pytest.fixture
def no_ar(tmp_path):
    (tmp_path / "radar-2026-11-17.html").write_text("<p>painel</p>", encoding="utf-8")
    chamadas = {"perguntas": [], "regerou": 0}

    def responder(pergunta):
        chamadas["perguntas"].append(pergunta)
        if "erro" in pergunta:
            raise RuntimeError("falha da API")
        if "orçamento" in pergunta:
            return {"ok": False, "erro": "Sem resposta para o painel."}
        return {"ok": True, "hora": "10:00", "pergunta": pergunta, "resposta": "São 3 riscos.", "usa_radar": False,
                "recorte": "painel inteiro"}

    def depois():
        chamadas["regerou"] += 1

    s = servidor.criar(tmp_path, "radar-2026-11-17.html", responder, depois, porta=0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1], chamadas
    s.shutdown()
    s.server_close()


def _pedir(porta, metodo, caminho, corpo=None, cabecalhos=None):
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    dados = json.dumps(corpo).encode("utf-8") if isinstance(corpo, dict) else corpo
    c.request(metodo, caminho, body=dados, headers=cabecalhos if cabecalhos is not None else
              {"Content-Type": "application/json"})
    r = c.getresponse()
    texto = r.read().decode("utf-8")
    c.close()
    return r, texto


def test_raiz_leva_ao_painel_do_dia(no_ar):
    porta, _ = no_ar
    r, _ = _pedir(porta, "GET", "/")
    assert r.status == 302 and r.getheader("Location") == "/radar-2026-11-17.html"
    r, texto = _pedir(porta, "GET", "/radar-2026-11-17.html")
    assert r.status == 200 and "painel" in texto and r.getheader("Cache-Control") == "no-store"


def test_pergunta_respondida_e_painel_regerado(no_ar):
    porta, chamadas = no_ar
    r, texto = _pedir(porta, "POST", "/perguntar", {"pergunta": "  quantos riscos?  "})
    assert r.status == 200
    assert json.loads(texto) == {"ok": True, "hora": "10:00", "pergunta": "quantos riscos?",
                                 "resposta": "São 3 riscos.", "usa_radar": False, "recorte": "painel inteiro"}
    _pedir(porta, "GET", "/")            # o `depois` roda após o envio: outro pedido garante que já terminou
    assert chamadas == {"perguntas": ["quantos riscos?"], "regerou": 1}


def test_resposta_invalida_nao_regera(no_ar):
    porta, chamadas = no_ar
    r, texto = _pedir(porta, "POST", "/perguntar", {"pergunta": "qual o orçamento?"})
    assert r.status == 200 and json.loads(texto)["ok"] is False and chamadas["regerou"] == 0


def test_erro_do_agente_vira_mensagem(no_ar):
    porta, chamadas = no_ar
    r, texto = _pedir(porta, "POST", "/perguntar", {"pergunta": "dá erro"})
    assert r.status == 500 and "falha da API" not in texto and chamadas["regerou"] == 0


@pytest.mark.parametrize("corpo, cabecalhos, status", [
    ({"pergunta": "oi"}, {"Content-Type": "text/plain"}, 415),                                    # formulário de outro site
    ({"pergunta": "oi"}, {"Content-Type": "application/json", "Origin": "http://evil.example"}, 403),
    ({"pergunta": "oi"}, {"Content-Type": "application/json", "Host": "evil.example"}, 403),      # DNS rebinding
    ({"pergunta": "   "}, None, 400),
    ({"pergunta": "x" * 301}, None, 400),
    ({"outra": "chave"}, None, 400),
    (b"{nao e json", None, 400),
    (b"x" * 5000, None, 400),
])
def test_pedidos_recusados_nao_chegam_ao_agente(no_ar, corpo, cabecalhos, status):
    porta, chamadas = no_ar
    r, _ = _pedir(porta, "POST", "/perguntar", corpo, cabecalhos)
    assert r.status == status and chamadas["perguntas"] == []


def test_so_perguntar_aceita_post(no_ar):
    porta, chamadas = no_ar
    r, _ = _pedir(porta, "POST", "/outro", {"pergunta": "oi"})
    assert r.status == 404 and chamadas["perguntas"] == []
