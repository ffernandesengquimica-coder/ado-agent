"""Servidor local do painel: entrega os arquivos de `relatorios/` e responde as perguntas digitadas na página.

    python -m radar servir   →   http://127.0.0.1:8765/

Só escuta em 127.0.0.1. A pergunta só é aceita se vier da própria página: `Host` local, `Origin` igual
ao `Host` e corpo JSON (um site aberto em outra aba não consegue disparar chamadas à OpenAI).
Uma pergunta por vez; depois de responder, o HTML do dia é regerado para o F5 manter a resposta.
"""
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

MAX_PERGUNTA = 300
MAX_CORPO = 4096
_LOCAIS = ("127.0.0.1", "localhost")


def criar(pasta: Path, pagina: str, responder: Callable[[str], dict], depois: Callable[[], None] | None = None,
          porta: int = 8765) -> ThreadingHTTPServer:
    """`responder(pergunta)` devolve o JSON da resposta; `depois()` roda após o envio (regerar o painel)."""
    trava = threading.Lock()

    class Manipulador(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(pasta), **k)

        def log_message(self, formato, *args):       # só as perguntas aparecem no terminal
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")   # F5 sempre pega o painel regerado
            super().end_headers()

        def _local(self) -> bool:
            return (self.headers.get("Host") or "").rsplit(":", 1)[0] in _LOCAIS

        def _json(self, codigo: int, dados: dict) -> None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            self.wfile.flush()

        def do_GET(self):
            if not self._local():
                return self.send_error(403)
            if self.path in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", "/" + pagina)
                self.send_header("Content-Length", "0")
                return self.end_headers()
            super().do_GET()

        def do_POST(self):
            if self.path != "/perguntar":
                return self.send_error(404)
            origem = self.headers.get("Origin")
            if not self._local() or (origem and origem != f"http://{self.headers.get('Host')}"):
                return self._json(403, {"ok": False, "erro": "Pedido recusado: só a própria página pode perguntar."})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(415, {"ok": False, "erro": "Pedido recusado: o corpo precisa ser JSON."})
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
                if not 0 < tamanho <= MAX_CORPO:
                    raise ValueError
                pergunta = str(json.loads(self.rfile.read(tamanho))["pergunta"]).strip()
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"ok": False, "erro": "Pergunta inválida."})
            if not pergunta or len(pergunta) > MAX_PERGUNTA:
                return self._json(400, {"ok": False, "erro": f"Escreva uma pergunta de até {MAX_PERGUNTA} caracteres."})
            with trava:
                try:
                    resposta = responder(pergunta)
                except Exception as e:                      # a reunião continua: o erro vai para a página e o terminal
                    print(f"Erro ao responder: {e!r}", file=sys.stderr)
                    return self._json(500, {"ok": False, "erro": "Não consegui responder agora. Tente de novo."})
                self._json(200, resposta)
                if depois and resposta.get("ok"):
                    try:
                        depois()
                    except Exception as e:
                        print(f"Erro ao regerar o painel: {e!r}", file=sys.stderr)

    return ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
