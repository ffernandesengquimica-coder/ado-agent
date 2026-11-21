"""Cliente mínimo da API da OpenAI (Chat Completions) com `requests`.

É a única chamada de rede dos pacotes do painel. Mensagens de erro nunca levam a chave nem o
texto devolvido pela API (a OpenAI repete parte da chave na mensagem de 401).
"""
import threading
import time
from dataclasses import dataclass

import requests

URL = "https://api.openai.com/v1/chat/completions"
TENTATIVAS = 3
ESPERA_S = 1.0


class ErroCliente(Exception):
    pass


@dataclass(frozen=True)
class Resposta:
    texto: str
    tokens_entrada: int = 0
    tokens_saida: int = 0


class ClienteOpenAI:
    def __init__(self, chave: str, modelo: str, timeout_s: float = 30, sessao=None):
        self._chave = chave
        self.modelo = modelo
        self._timeout = timeout_s
        self._sessao = sessao
        self._local = threading.local()

    def _sessao_atual(self):
        # Uma requests.Session por thread: compartilhada entre threads, ela dava SSLError (11/11/2026).
        if self._sessao is not None:
            return self._sessao
        if not hasattr(self._local, "sessao"):
            self._local.sessao = requests.Session()
        return self._local.sessao

    def _post(self, corpo: dict):
        # Falha de conexão (inclui SSLError) é intermitente nesta rede: até 2 novas tentativas.
        for tentativa in range(TENTATIVAS):
            try:
                return self._sessao_atual().post(URL, json=corpo, timeout=self._timeout,
                                                 headers={"Authorization": f"Bearer {self._chave}"})
            except requests.ConnectionError as e:
                if tentativa == TENTATIVAS - 1:
                    raise ErroCliente(f"falha de rede ({type(e).__name__})") from None
                self._local.__dict__.pop("sessao", None)      # conexão nova na próxima tentativa
                time.sleep(ESPERA_S * (tentativa + 1))
            except requests.RequestException as e:
                raise ErroCliente(f"falha de rede ({type(e).__name__})") from None

    def completar(self, sistema: str, usuario: str) -> Resposta:
        corpo = {"model": self.modelo, "temperature": 0,
                 "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
        r = self._post(corpo)
        if r.status_code == 400 and "temperature" in r.text:
            # Alguns modelos só aceitam a temperatura padrão: tenta uma vez sem ela.
            r = self._post({k: v for k, v in corpo.items() if k != "temperature"})
        if r.status_code != 200:
            codigo = ""
            try:
                codigo = (r.json().get("error") or {}).get("code") or ""
            except ValueError:
                pass
            raise ErroCliente(f"HTTP {r.status_code}" + (f" ({codigo})" if codigo else ""))
        try:
            dados = r.json()
            texto = dados["choices"][0]["message"]["content"] or ""
            uso = dados.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            raise ErroCliente("resposta em formato inesperado") from None
        return Resposta(texto.strip(), int(uso.get("prompt_tokens", 0)), int(uso.get("completion_tokens", 0)))
