import csv
from datetime import date

import pytest
import requests

from explicacao.cliente_openai import URL, ClienteOpenAI, ErroCliente, Resposta
from explicacao.narrativas import gerar, ler_cache, linhas_csv, para_painel, resumo

HOJE = date(2026, 11, 11)
FATOS = {
    1: {"epic": "#1", "dono": "Zeca Exemplo", "data_alvo": "13/11/2026",
        "radar": {"aceleracao_necessaria": "3,2×", "itens_restantes": 14}},
    2: {"epic": "#2", "dono": "sem dono", "data_alvo": "30/11/2026"},
}


class Falso:
    """Cliente falso: devolve respostas prontas por Epic e guarda o que recebeu."""
    modelo = "modelo-teste"

    def __init__(self, respostas):
        self.respostas, self.recebido = respostas, []

    def completar(self, sistema, usuario):
        self.recebido.append(usuario)
        r = self.respostas[next(e for e in self.respostas if f'"#{e}"' in usuario)]
        if isinstance(r, Exception):
            raise r
        return Resposta(r, 100, 20)


def test_valida_rejeita_e_desanonimiza():
    cliente = Falso({1: "Pessoa A precisa entregar 3,2× mais rápido para fechar 14 itens até 13/11/2026.",
                     2: "Faltam 99 itens."})
    ns = gerar(FATOS, "m", {}, cliente)
    assert [(n.epic_id, n.status) for n in ns] == [(1, "ok"), (2, "rejeitada")]
    assert ns[1].motivo == "número fora dos fatos: 99" and ns[1].texto == ""
    assert para_painel(ns) == {1: "Zeca Exemplo precisa entregar 3,2× mais rápido para fechar 14 itens até 13/11/2026."}
    assert ns[0].texto.startswith("Pessoa A")      # o CSV guarda a versão anonimizada


def test_payload_sem_nomes_de_pessoas():
    cliente = Falso({1: "ok.", 2: "ok."})
    gerar(FATOS, "m", {}, cliente, extras={1: ("Bruna Lima",)})
    enviado = "\n".join(cliente.recebido)
    assert "Zeca" not in enviado and "Exemplo" not in enviado and "Bruna" not in enviado


def test_erro_do_cliente_nao_derruba_os_outros():
    cliente = Falso({1: ErroCliente("HTTP 429 (rate_limit_exceeded)"), 2: "Data alvo em 30/11/2026."})
    ns = gerar(FATOS, "m", {}, cliente)
    assert [(n.status, n.motivo) for n in ns] == [("erro", "HTTP 429 (rate_limit_exceeded)"), ("ok", "")]


def test_cache_evita_chamada_e_sem_cliente_so_cache(tmp_path):
    cliente = Falso({1: "Pessoa A está atrasada.", 2: "Data alvo em 30/11/2026."})
    ns = gerar(FATOS, "m", {}, cliente)
    ns.append(gerar({3: {"epic": "#3"}}, "m", {}, Falso({3: "Faltam 99 itens."}))[0])
    linhas = linhas_csv(ns, HOJE, "m")
    with (tmp_path / "narrativas-2026-11-11.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    cache = ler_cache(tmp_path)

    outro = Falso({})
    de_novo = gerar(FATOS, "m", cache, outro)
    assert outro.recebido == [] and [n.status for n in de_novo] == ["cache", "cache"]
    # A rejeição também fica no cache: não pede de novo e continua sem narrativa.
    rej = gerar({3: {"epic": "#3"}}, "m", cache, outro)
    assert outro.recebido == [] and [(n.status, n.motivo) for n in rej] == [("rejeitada", "número fora dos fatos: 99")]
    assert para_painel(de_novo) == para_painel(ns)
    # Outro modelo = outra chave: sem cliente, nada sai.
    assert gerar(FATOS, "outro", cache, None) == []
    assert "28 Epics no Escalar = 2 válidas (2 do cache) + 0 rejeitadas + 0 com erro + 26 sem narrativa" \
        in resumo(de_novo, 28, 1.0)


class _Resp:
    def __init__(self, status, corpo=None, texto=""):
        self.status_code, self._corpo, self.text = status, corpo, texto

    def json(self):
        if self._corpo is None:
            raise ValueError("sem json")
        return self._corpo


class _Sessao:
    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []

    def post(self, url, json, timeout, headers):
        self.chamadas.append((url, json, headers))
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_cliente_monta_pedido_e_le_resposta():
    ok = _Resp(200, {"choices": [{"message": {"content": " Texto. "}}],
                     "usage": {"prompt_tokens": 10, "completion_tokens": 3}})
    s = _Sessao(ok)
    r = ClienteOpenAI("sk-segredo", "m", sessao=s).completar("sis", "usr")
    assert r == Resposta("Texto.", 10, 3)
    url, corpo, headers = s.chamadas[0]
    assert url == URL and corpo["model"] == "m" and corpo["temperature"] == 0
    assert headers["Authorization"] == "Bearer sk-segredo"


def test_cliente_tenta_sem_temperatura_quando_o_modelo_recusa():
    ok = _Resp(200, {"choices": [{"message": {"content": "T."}}]})
    s = _Sessao(_Resp(400, {"error": {"code": "unsupported_value"}}, "temperature not supported"), ok)
    assert ClienteOpenAI("k", "m", sessao=s).completar("s", "u").texto == "T."
    assert "temperature" not in s.chamadas[1][1]


@pytest.mark.parametrize("resposta, mensagem", [
    (_Resp(401, {"error": {"code": "invalid_api_key", "message": "Incorrect API key provided: sk-segr***"}}),
     "HTTP 401 (invalid_api_key)"),
    (_Resp(500, None, "erro"), "HTTP 500"),
    (_Resp(200, {"sem": "choices"}), "resposta em formato inesperado"),
    (requests.Timeout("sk-segredo"), "falha de rede (Timeout)"),
])
def test_erros_do_cliente_sem_vazar_a_chave(resposta, mensagem):
    with pytest.raises(ErroCliente) as e:
        ClienteOpenAI("sk-segredo", "m", sessao=_Sessao(resposta)).completar("s", "u")
    assert str(e.value) == mensagem and "segr" not in str(e.value)


def test_cliente_usa_uma_sessao_por_thread():
    import threading
    c = ClienteOpenAI("k", "m")
    sessoes = []
    ts = [threading.Thread(target=lambda: sessoes.append(c._sessao_atual())) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len({id(s) for s in sessoes}) == 3
    assert c._sessao_atual() is c._sessao_atual()


def test_cliente_tenta_de_novo_falha_de_conexao(monkeypatch):
    import explicacao.cliente_openai as c
    monkeypatch.setattr(c, "ESPERA_S", 0)
    ok = _Resp(200, {"choices": [{"message": {"content": "T."}}]})
    s = _Sessao(requests.exceptions.SSLError("x"), requests.ConnectionError("y"), ok)
    assert ClienteOpenAI("k", "m", sessao=s).completar("s", "u").texto == "T."
    s = _Sessao(*[requests.exceptions.SSLError("x")] * 3)
    with pytest.raises(ErroCliente, match=r"falha de rede \(SSLError\)"):
        ClienteOpenAI("k", "m", sessao=s).completar("s", "u")
