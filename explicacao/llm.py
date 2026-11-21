"""Núcleo de todo texto redigido por LLM: pedido → anonimização → cache → cliente → validador.

Cada tipo de texto (causa provável, pauta, resumo, pergunta sugerida, pergunta do apresentador)
tem prompt, versão e limites próprios (`prompt.TIPOS`). As garantias são as mesmas para todos:
o LLM só vê fatos já calculados e anonimizados, e nada é exibido sem passar no validador.
Rejeições ficam no cache (temperatura 0: pedir de novo daria o mesmo texto); só erros de rede ou
da API são tentados de novo na próxima execução.
"""
import csv
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from .anonimizacao import anonimizar, desanonimizar, trocar_nomes
from .cliente_openai import ErroCliente, Resposta
from .prompt import TIPOS, mensagem_usuario
from .validador import cita_radar, rejeicoes

COLUNAS = ["data", "tipo", "alvo", "chave", "modelo", "prompt_versao", "status", "motivo",
           "tokens_entrada", "tokens_saida", "texto"]
VALIDAS = ("ok", "cache")
REJEITADA = "rejeitada"
PARALELO = 4


class Cliente(Protocol):
    modelo: str

    def completar(self, sistema: str, usuario: str) -> Resposta: ...


@dataclass(frozen=True)
class Pedido:
    tipo: str                       # chave de prompt.TIPOS
    alvo: str                       # "90004", "programa:Rede Norte", "geral", ...
    fatos: dict
    extras: tuple[str, ...] = ()    # nomes a esconder além do dono
    usa_radar: bool = False         # a entrada tem números do Radar → selo "previsão em validação"
    pergunta: str = ""              # só para os tipos de pergunta


@dataclass(frozen=True)
class Texto:
    tipo: str
    alvo: str
    chave: str
    status: str                     # "ok" | "cache" | "rejeitada" | "erro"
    texto: str = ""                 # anonimizado, como o modelo devolveu
    exibicao: str = ""              # com os nomes reais: só para tela, nunca gravado
    motivo: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0
    usa_radar: bool = False

    @property
    def valido(self) -> bool:
        return self.status in VALIDAS and bool(self.exibicao)


def chave(tipo: str, modelo: str, fatos_json: str, pergunta: str = "") -> str:
    versao = TIPOS[tipo].versao
    if tipo == "causa":   # formato histórico: mantém no cache as narrativas já aprovadas
        base = f"{modelo}\n{versao}\n{fatos_json}"
    else:
        base = f"{tipo}\n{modelo}\n{versao}\n{pergunta}\n{fatos_json}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def ler_cache(pasta: Path, padrao: str = "textos-*.csv", coluna: str = "texto") -> dict[str, tuple[str, str]]:
    """chave → (status, texto anonimizado ou motivo da rejeição), de todos os arquivos do padrão."""
    cache = {}
    for arq in sorted(pasta.glob(padrao)):
        with arq.open(encoding="utf-8-sig", newline="") as f:
            for l in csv.DictReader(f):
                if l.get("status") in VALIDAS and l.get(coluna):
                    cache[l["chave"]] = ("cache", l[coluna])
                elif l.get("status") == REJEITADA:
                    cache[l["chave"]] = (REJEITADA, l.get("motivo", ""))
    return cache


def _chamar(p: Pedido, fatos_json: str, pergunta: str, mapa: dict[str, str], k: str, cliente: Cliente) -> Texto:
    t = TIPOS[p.tipo]
    base = dict(tipo=p.tipo, alvo=p.alvo, chave=k, usa_radar=p.usa_radar)
    try:
        r = cliente.completar(t.sistema, mensagem_usuario(fatos_json, pergunta, t.rotulo))
    except ErroCliente as e:
        return Texto(**base, status="erro", motivo=str(e))
    uso = dict(tokens_entrada=r.tokens_entrada, tokens_saida=r.tokens_saida)
    erros = rejeicoes(r.texto, f"{fatos_json}\n{pergunta}", set(mapa), t.limite_caracteres, t.limite_frases)
    if erros:
        return Texto(**base, status=REJEITADA, motivo="; ".join(erros), **uso)
    return Texto(**{**base, "usa_radar": p.usa_radar and cita_radar(r.texto)}, status="ok", texto=r.texto,
                 exibicao=desanonimizar(r.texto, mapa), **uso)


def gerar(pedidos: list[Pedido], modelo: str, cache: dict[str, tuple[str, str]],
          cliente: Cliente | None) -> list[Texto]:
    """Um texto por pedido, na ordem dos pedidos. Sem cliente, só os que estão no cache."""
    prontos: dict[int, Texto] = {}
    pendentes = []
    for i, p in enumerate(pedidos):
        fatos_json, mapa = anonimizar(p.fatos, p.extras)
        pergunta = trocar_nomes(p.pergunta, mapa)
        k = chave(p.tipo, modelo, fatos_json, pergunta)
        if k in cache:
            status, valor = cache[k]
            base = dict(tipo=p.tipo, alvo=p.alvo, chave=k, usa_radar=p.usa_radar)
            prontos[i] = (Texto(**base, status=REJEITADA, motivo=valor) if status == REJEITADA
                          else Texto(**{**base, "usa_radar": p.usa_radar and cita_radar(valor)}, status="cache",
                                     texto=valor, exibicao=desanonimizar(valor, mapa)))
        elif cliente is not None:
            pendentes.append((i, p, fatos_json, pergunta, mapa, k))
    if pendentes:
        with ThreadPoolExecutor(max_workers=PARALELO) as ex:
            for i, texto in ex.map(lambda x: (x[0], _chamar(*x[1:], cliente)), pendentes):
                prontos[i] = texto
    return [prontos[i] for i in range(len(pedidos)) if i in prontos]


def linhas_csv(textos: list[Texto], hoje: date, modelo: str) -> list[dict]:
    return [{"data": hoje.isoformat(), "tipo": t.tipo, "alvo": t.alvo, "chave": t.chave, "modelo": modelo,
             "prompt_versao": TIPOS[t.tipo].versao, "status": t.status, "motivo": t.motivo,
             "tokens_entrada": t.tokens_entrada, "tokens_saida": t.tokens_saida, "texto": t.texto}
            for t in textos]


def contagem(textos: list[Texto]) -> str:
    """'26 válidos (20 do cache) + 0 rejeitados + 0 com erro | 9.120 tokens'"""
    n = {s: sum(t.status == s for t in textos) for s in ("ok", "cache", REJEITADA, "erro")}
    tokens = sum(t.tokens_entrada + t.tokens_saida for t in textos)
    return (f"{n['ok'] + n['cache']} válidos ({n['cache']} do cache) + {n[REJEITADA]} rejeitados + "
            f"{n['erro']} com erro | " + f"{tokens:,} tokens".replace(",", "."))
