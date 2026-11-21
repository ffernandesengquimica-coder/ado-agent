import pytest

from explicacao.prompt import SISTEMA, mensagem_usuario
from explicacao.validador import rejeicoes

FATOS = ('{"data_alvo": "13/11/2026", "epic": "#90001", "dono": "Pessoa A", "chance": "12%", '
         '"aceleracao": "3,2×", "restantes": 14, "evidencia": "depende de #1234, vencida em 10/10/2026"}')
PESSOAS = {"Pessoa A"}


def test_narrativa_valida():
    texto = ("O Epic #90001 precisa entregar 3,2× mais rápido para fechar 14 itens até 13/11, "
             "e depende de #1234, vencida em 10/10/2026. Por isso a chance é de 12%; Pessoa A é o dono.")
    assert rejeicoes(texto, FATOS, PESSOAS) == []


@pytest.mark.parametrize("texto, erro", [
    ("Faltam 15 itens.", "número fora dos fatos: 15"),
    ("Precisa acelerar 3,5×.", "número fora dos fatos: 3,5"),
    ("Precisa acelerar 3.2×.", "número fora dos fatos: 3.2"),
    ("A chance é de 13%.", "número fora dos fatos: 13%"),
    ("A data é 14/11/2026.", "data fora dos fatos: 14/11/2026"),
    ("Vence em 12/11.", "data fora dos fatos: 12/11"),
    ("Depende de #999.", "id fora dos fatos: #999"),
    ("Pessoa B está sobrecarregada.", "pessoa desconhecida: Pessoa B"),
    ("   ", "resposta vazia"),
    ("Um. Dois. Três. Quatro.", "frases demais: 4"),
    ("a" * 501 + ".", "texto longo: 502 caracteres"),
])
def test_rejeita(texto, erro):
    assert erro in rejeicoes(texto, FATOS, PESSOAS)


def test_numero_dentro_de_data_nao_conta_solto():
    # "2026" só existe dentro das datas dos fatos; solto, é número inventado.
    assert rejeicoes("Entrega prevista para 2026.", FATOS, PESSOAS) == ["número fora dos fatos: 2026"]


def test_prompt_traz_regras_e_fatos():
    assert "Copie números" in SISTEMA and "Não recomende" in SISTEMA and "Pessoa A" in SISTEMA
    assert mensagem_usuario('{"x": 1}').endswith('{"x": 1}')
