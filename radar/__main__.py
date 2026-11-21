"""Radar de Datas: prevê quais Epics vão estourar a data alvo.

    python -m radar backtest     # valida o modelo em datas passadas (portão)
    python -m radar relatorio    # relatório semanal (Radar + registro de riscos + textos do agente)
    python -m radar perguntar "..."   # modo apresentador: pergunta livre, resposta entra no painel
    python -m radar servir       # painel em http://127.0.0.1:8765/ com caixa de pergunta na página
"""
import argparse
import contextlib
import csv
import io
import os
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from explicacao import leitura, llm, narrativas, pauta, perguntar, recortes, sugeridas
from explicacao.cliente_openai import ClienteOpenAI
from explicacao.fatos import evidencias, fatos_epic, fatos_escalar, por_epic
from riscos import painel, registro

from . import backtest, painel_agente, relatorio
from . import servidor as servidor_local
from .dados import carregar, ultima_extracao
from .previsao import MODELO_VERSAO

CORTES_PADRAO = "2026-07-06,2026-08-03,2026-08-31"


def _cortes(texto: str) -> list[date]:
    return [date.fromisoformat(c.strip()) for c in texto.split(",") if c.strip()]


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="radar", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)

    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("--extracao", help="pasta da extração (padrão: a mais recente em out/<projeto>/)")
    comuns.add_argument("--hoje", type=date.fromisoformat, default=date.today(), help="data de referência (AAAA-MM-DD)")
    comuns.add_argument("--semente", type=int, default=42, help="semente do Monte Carlo")
    comuns.add_argument("--saida", default="relatorios", help="pasta dos relatórios e do cache de textos (padrão: relatorios)")

    rel = sub.add_parser("relatorio", parents=[comuns], help="gera o relatório semanal")
    rel.add_argument("--sem-llm", action="store_true",
                     help="não chama a OpenAI: textos do agente só do cache (narrativas-*.csv e textos-*.csv)")
    pq = sub.add_parser("perguntar", parents=[comuns],
                        help="modo apresentador: responde uma pergunta com os fatos do painel do dia")
    pq.add_argument("texto", help='a pergunta, entre aspas: "por que Obras Sul piorou?"')
    sv = sub.add_parser("servir", parents=[comuns],
                        help="abre o painel do dia num servidor local, com caixa de pergunta na página")
    sv.add_argument("--porta", type=int, default=8765, help="porta em 127.0.0.1 (padrão: 8765)")
    bt = sub.add_parser("backtest", parents=[comuns], help="mede o acerto do modelo em cortes passados")
    bt.add_argument("--cortes", type=_cortes, default=_cortes(CORTES_PADRAO),
                    help=f"datas de corte separadas por vírgula (padrão: {CORTES_PADRAO})")
    return p


def _gravar_csv(caminho: Path, linhas: list[dict], campos: list[str] | None = None) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos or (list(linhas[0]) if linhas else ["vazio"]))
        w.writeheader()
        w.writerows(linhas)


def _pasta_extracao(args) -> Path:
    if args.extracao:
        return Path(args.extracao)
    load_dotenv()
    projeto = os.getenv("ADO_PROJECT", "").strip()
    if not projeto:
        sys.exit("Defina ADO_PROJECT no .env ou passe a pasta da extração com --extracao.")
    return ultima_extracao(Path(os.getenv("OUT_DIR", "out")), projeto)


def _backtest(args) -> None:
    pasta = _pasta_extracao(args)
    r = backtest.executar(carregar(pasta), args.cortes, args.hoje, args.semente)
    saida = Path(args.saida) / f"backtest-{args.hoje.isoformat()}.csv"
    _gravar_csv(saida, r.linhas)
    _gravar_csv(saida.with_name(f"{saida.stem}-detalhe.csv"), r.detalhe)

    print(f"Extração: {pasta}  |  hoje: {args.hoje}  |  cortes: {', '.join(map(str, args.cortes))}\n")
    print(f"{'corte':<11} {'preditor':<8} {'n':>4} {'únicos':>6} {'base':>6} {'precisão':>8} {'recall':>7} {'F1':>6}")
    for l in r.linhas:
        print(f"{l['corte']:<11} {l['preditor']:<8} {l['n']:>4} {l['epics_unicos']:>6} {l['taxa_base']:>6.0%} "
              f"{l['precisao']:>8.0%} {l['recall']:>7.0%} {l['f1']:>6.2f}")
    print(f"\nPortão: {'PASSOU' if r.passou else 'NÃO PASSOU'} "
          "(recall ≥ 70%, precisão ≥ base + 10 p.p., F1 > ingênuo e > trivial)")
    print(f"Arquivos: {saida} e {saida.stem}-detalhe.csv")


def _relatorio(args) -> None:
    pasta = _pasta_extracao(args)
    dados = carregar(pasta)
    linhas = relatorio.linhas_relatorio(dados, args.hoje, args.semente)
    saida = Path(args.saida) / f"radar-{args.hoje.isoformat()}.csv"
    _gravar_csv(saida, linhas)

    # O anterior é procurado antes de gravar o de hoje: rodar de novo no mesmo dia dá o mesmo CSV.
    anterior = registro.csv_anterior(saida.parent, args.hoje)
    anteriores = registro.ler_csv(anterior)
    riscos = registro.montar(dados, args.hoje)
    linhas_riscos = registro.linhas_csv(riscos, dados, args.hoje, anteriores)
    saida_riscos = saida.with_name(f"riscos-{args.hoje.isoformat()}.csv")
    _gravar_csv(saida_riscos, linhas_riscos, registro.COLUNAS)

    modelo, cliente, pulo = _llm(args)
    causas, resumo_narrativas = _narrativas(args, linhas, linhas_riscos, saida.parent, modelo, cliente, pulo)
    agente, resumo_agente = _agente(args, linhas, linhas_riscos, saida.parent, modelo, cliente, pulo,
                                    {e: t for e, (t, _) in causas.items()})

    data_anterior = date.fromisoformat(anterior.stem.removeprefix("riscos-")) if anterior else None
    aba = painel.gerar_aba(linhas_riscos, registro.saidas(riscos, anteriores, dados), data_anterior, causas,
                           leitura=True)
    html = saida.with_suffix(".html")
    html.write_text(relatorio.gerar_html(linhas, args.hoje, pasta.name, riscos_html=aba, agente=agente),
                    encoding="utf-8")

    contagem = Counter(l["secao"] for l in linhas)
    partes = " + ".join(f"{s} {contagem[s]}" for s in relatorio.ORDEM_SECOES)
    print(f"Extração: {pasta}  |  hoje: {args.hoje}  |  modelo {MODELO_VERSAO}"
          + ("" if painel_agente.RADAR_APROVADO else " (uso interno)"))
    print(f"{len(linhas)} Epics abertos = {partes}")
    escalar = {r.epic_id for r in riscos if r.gatilhos}
    print(f"Riscos: {len(riscos)} em {len({r.epic_id for r in riscos})} Epics; Escalar: {len(escalar)} Epics"
          f" (anterior: {anterior.name if anterior else 'nenhum'})")
    print(resumo_narrativas)
    print(resumo_agente)
    print(f"Arquivos: {saida}, {saida_riscos.name} e {html.name}")


def _llm(args):
    """(modelo, cliente ou None, motivo de só usar o cache). Sem modelo, nada de LLM, nem cache."""
    load_dotenv()
    modelo = os.getenv("OPENAI_MODEL", "").strip()
    chave = os.getenv("OPENAI_API_KEY", "").strip()
    if not modelo:
        return "", None, ""
    if getattr(args, "sem_llm", False) or not chave:
        return modelo, None, "--sem-llm" if getattr(args, "sem_llm", False) else "OPENAI_API_KEY vazia"
    return modelo, ClienteOpenAI(chave, modelo, float(os.getenv("OPENAI_TIMEOUT_S") or 30)), ""


def _narrativas(args, linhas: list[dict], linhas_riscos: list[dict], pasta: Path, modelo, cliente, pulo):
    """Causa provável dos Epics do Escalar: (epic_id → (texto, fatos usados), linha de resumo)."""
    if not modelo:
        return {}, "Narrativas: puladas (OPENAI_MODEL vazio no .env)"
    fatos = fatos_escalar(linhas, linhas_riscos, args.hoje)
    responsaveis = {int(l["epic_id"]): (l["responsavel"],) for l in linhas if l.get("responsavel")}
    inicio = time.perf_counter()
    lista = narrativas.gerar(fatos, modelo, narrativas.ler_cache(pasta), cliente, responsaveis)
    if lista:
        _gravar_csv(pasta / f"narrativas-{args.hoje.isoformat()}.csv",
                    narrativas.linhas_csv(lista, args.hoje, modelo), narrativas.COLUNAS)
    textos = narrativas.para_painel(lista)
    causas = {e: (t, evidencias(fatos[e])) for e, t in textos.items()}
    linha = narrativas.resumo(lista, len(fatos), time.perf_counter() - inicio)
    if cliente is None:
        linha += f" (só cache: {pulo})"
    return causas, linha


def _agente(args, linhas: list[dict], linhas_riscos: list[dict], pasta: Path, modelo, cliente, pulo,
            causas: dict[int, str]):
    """Pauta, perguntas sugeridas, resumos por recorte (LLM) e leitura por regra: (Agente, linha de resumo)."""
    hoje = args.hoje
    agente = painel_agente.Agente(
        leitura={"radar": leitura.leitura_radar(linhas, relatorio.faixa_de(hoje), relatorio.rotulos_mes(hoje)),
                 "riscos": leitura.leitura_riscos(linhas_riscos)},
        epics=painel_agente.dados_epics(linhas, linhas_riscos, causas),
        perguntas=perguntar.validas_do_dia(pasta, hoje))
    radar = {int(l["epic_id"]): l for l in linhas}
    grupos = por_epic(linhas_riscos)
    escolhidos = pauta.escolher(linhas_riscos)
    lista_sug = sugeridas.sugeridas(linhas_riscos)
    textos: dict[tuple[str, str], llm.Texto] = {}
    linha = "Agente: pauta por regra; resumos e respostas pulados (OPENAI_MODEL vazio no .env)"
    if modelo:
        pedidos = [llm.Pedido("pauta", str(e), pauta.fatos_ponto(fatos_epic(e, grupos[e], radar.get(e), hoje), grupos[e]),
                              (radar[e]["responsavel"],) if e in radar and radar[e].get("responsavel") else (),
                              usa_radar=e in radar) for e in escolhidos]
        for alvo, prog, cat in recortes.recortes(linhas_riscos):
            fatos, usa = recortes.fatos_recorte(linhas, linhas_riscos, hoje, prog, cat)
            pedidos.append(llm.Pedido("resumo", alvo, fatos, usa_radar=usa))
        pedidos += [llm.Pedido("sugerida", s.alvo, s.fatos, pergunta=s.pergunta) for s in lista_sug if s.fatos]
        inicio = time.perf_counter()
        gerados = llm.gerar(pedidos, modelo, llm.ler_cache(pasta), cliente)
        if gerados:
            _gravar_csv(pasta / f"textos-{hoje.isoformat()}.csv", llm.linhas_csv(gerados, hoje, modelo), llm.COLUNAS)
        textos = {(t.tipo, t.alvo): t for t in gerados}
        linha = (f"Agente: {len(pedidos)} textos (pauta {len(escolhidos)} + resumos "
                 f"{sum(p.tipo == 'resumo' for p in pedidos)} + perguntas {sum(p.tipo == 'sugerida' for p in pedidos)})"
                 f" = {llm.contagem(gerados)} | {time.perf_counter() - inicio:.0f} s"
                 + (f" (só cache: {pulo})" if cliente is None else ""))

    for e in escolhidos:
        t = textos.get(("pauta", str(e)))
        agente.pauta.append({"epic": e, "texto": t.exibicao if t and t.valido else pauta.manchete_regra(e, grupos[e]),
                             "usa_radar": bool(t and t.valido and t.usa_radar)})
    for s in lista_sug:
        t = textos.get(("sugerida", s.alvo))
        if s.fatos is None:
            agente.sugeridas.append({"pergunta": s.pergunta, "resposta": s.resposta_fixa, "usa_radar": False})
        elif t and t.valido:
            agente.sugeridas.append({"pergunta": s.pergunta, "resposta": t.exibicao, "usa_radar": t.usa_radar})
    agente.resumos = {alvo: {"t": t.exibicao, "radar": t.usa_radar}
                      for (tipo, alvo), t in textos.items() if tipo == "resumo" and t.valido}
    return agente, linha


def _painel_e_cliente(args):
    """(modelo, cliente) do modo apresentador; sai com a instrução certa se faltar o painel do dia ou a chave."""
    pasta = Path(args.saida)
    dia = args.hoje.isoformat()
    if not ((pasta / f"radar-{dia}.csv").exists() and (pasta / f"riscos-{dia}.csv").exists()):
        sys.exit(f"Painel de {dia} não encontrado em {pasta}. Rode antes: python -m radar relatorio --hoje {dia}")
    modelo, cliente, pulo = _llm(args)
    if cliente is None:
        sys.exit("Modo apresentador precisa de OPENAI_MODEL e OPENAI_API_KEY no .env"
                 + (f" ({pulo})" if pulo else " (OPENAI_MODEL vazio)"))
    return modelo, cliente


def _responder(args, pergunta: str, modelo, cliente):
    """Responde com os fatos do painel do dia e grava no CSV de perguntas: (texto, rótulo do recorte, linha do CSV)."""
    pasta = Path(args.saida)
    dia = args.hoje.isoformat()
    linhas = registro.ler_csv(pasta / f"radar-{dia}.csv")
    linhas_riscos = registro.ler_csv(pasta / f"riscos-{dia}.csv")
    pedido, rotulo = perguntar.pedido(pergunta, linhas, linhas_riscos, args.hoje)
    [texto] = llm.gerar([pedido], modelo, {}, cliente)
    return texto, rotulo, perguntar.registrar(pasta, args.hoje, pergunta, rotulo, texto)


def _servir(args) -> None:
    modelo, cliente = _painel_e_cliente(args)
    pagina = f"radar-{args.hoje.isoformat()}.html"

    def responder(pergunta: str) -> dict:
        inicio = time.perf_counter()
        texto, rotulo, linha = _responder(args, pergunta, modelo, cliente)
        print(f"[{linha['hora']}] {rotulo} | {time.perf_counter() - inicio:.0f} s | {texto.status} | {pergunta}")
        if not texto.valido:
            return {"ok": False, "erro": f"Sem resposta para o painel ({texto.status}: {texto.motivo}). "
                                         "Reformule a pergunta."}
        return {"ok": True, "hora": linha["hora"], "pergunta": pergunta, "resposta": texto.exibicao,
                "usa_radar": texto.usa_radar, "recorte": rotulo}

    def regerar() -> None:                # só com o cache: nenhuma chamada nova além da pergunta
        args.sem_llm = True
        with contextlib.redirect_stdout(io.StringIO()):
            _relatorio(args)

    regerar()                             # garante que o HTML do dia já tem a caixa de pergunta
    try:
        servidor = servidor_local.criar(Path(args.saida), pagina, responder, regerar, args.porta)
    except OSError as e:
        sys.exit(f"Não consegui abrir a porta {args.porta} ({e}). Tente outra: python -m radar servir --porta 8766")
    print(f"Painel no ar: http://127.0.0.1:{args.porta}/  (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")


def _perguntar(args) -> None:
    modelo, cliente = _painel_e_cliente(args)
    inicio = time.perf_counter()
    texto, rotulo, _ = _responder(args, args.texto, modelo, cliente)
    print(f"Recorte: {rotulo}  |  {time.perf_counter() - inicio:.0f} s  |  "
          f"{texto.tokens_entrada + texto.tokens_saida} tokens")
    if texto.valido:
        aviso = ("(cita a previsão do Radar: aparece com o selo 'previsão em validação')\n"
                 if texto.usa_radar and not painel_agente.RADAR_APROVADO else "")
        print(f"\n{texto.exibicao}\n{aviso}")
    else:
        print(f"\nSem resposta para o painel ({texto.status}: {texto.motivo}). Reformule a pergunta.\n")
    args.sem_llm = True          # o painel é regerado só com o cache: nenhuma chamada nova além da pergunta
    _relatorio(args)


def main() -> None:
    args = montar_parser().parse_args()
    {"backtest": _backtest, "relatorio": _relatorio, "perguntar": _perguntar, "servir": _servir}[args.comando](args)


if __name__ == "__main__":
    main()
