"""Relatório semanal: uma linha por Epic aberto, com previsão e motivos.

O CSV (`radar-AAAA-MM-DD.csv`) é também o registro das previsões que o teste
prospectivo vai avaliar; por isso cada linha leva a versão do modelo e a data.
"""
import unicodedata
from collections import Counter
from datetime import date
from html import escape

import numpy as np

from .dados import Dados
from .motivos import motivos
from . import painel_agente
from .narrativa import Narrador, NarradorNulo
from riscos.painel import CSS as CSS_RISCOS

from .previsao import MODELO_VERSAO, prever

ORDEM_SECOES = ["vermelho", "amarelo", "ja_atrasado", "sem_como_prever", "verde"]


def _iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def linhas_relatorio(dados: Dados, hoje: date, semente: int = 42) -> list[dict]:
    rng = np.random.default_rng(semente)
    abertos = sorted((e for e in dados.epics.values() if e.estado not in ("Done", "Removed")), key=lambda e: e.id)
    linhas = []
    for e in abertos:
        itens = dados.escopo.get(e.id, [])
        p = prever(e, itens, hoje, rng)
        linhas.append({
            "modelo_versao": MODELO_VERSAO, "data_previsao": hoje.isoformat(),
            "epic_id": e.id, "titulo": e.titulo, "area": e.area, "estado": e.estado,
            "responsavel": e.responsavel, "data_alvo": _iso(e.alvo), "secao": p.secao,
            "prob_cumprir": p.prob_cumprir, "p50": _iso(p.p50), "p85": _iso(p.p85),
            "escopo": p.escopo, "concluidos": p.concluidos, "restante": p.restante,
            "ritmo_medio": round(p.ritmo_medio, 2), "entrada_media": round(p.entrada_media, 2),
            "razao_ritmo": round(p.razao_ritmo, 2) if p.razao_ritmo is not None else None,
            "motivos": "; ".join(motivos(p, itens, dados.features.get(e.id, []), hoje)),
        })
    # Dentro da seção, o mais arriscado e o mais urgente primeiro.
    return sorted(linhas, key=lambda l: (ORDEM_SECOES.index(l["secao"]),
                                         l["prob_cumprir"] if l["prob_cumprir"] is not None else -1,
                                         l["data_alvo"] or "9999"))




# --- HTML (painel) ------------------------------------------------------------------
# O painel funciona sem JavaScript (tabela completa, já ordenada por risco). O script
# embutido só acrescenta filtros, busca e ordenação; nenhum recurso externo é carregado.

_TITULOS = {
    "vermelho": ("Vão atrasar", "Menos de 40% de chance de cumprir a data alvo, ou data marcada sem escopo detalhado."),
    "amarelo": ("Atenção", "Entre 40% e 70% de chance de cumprir a data alvo."),
    "ja_atrasado": ("Já atrasados", "A data alvo já passou e o Epic continua aberto."),
    "sem_como_prever": ("Sem como prever", "Sem data alvo, ou nada entregue nas últimas 12 semanas."),
    "verde": ("No prazo", "70% ou mais de chance de cumprir a data alvo."),
}

# (coluna, tipo de ordenação, explicação) — a explicação vira a dica do cabeçalho e a legenda.
_COLUNAS = [
    ("Situação", "num", "Seção do Epic no radar, pela chance de cumprir a data alvo."),
    ("Epic", "num", "Id do Epic no Azure DevOps."),
    ("Título", "txt", "Título do Epic e a área (programa › time)."),
    ("Data alvo", "txt", "Data alvo (Target Date) do Epic no ADO: o compromisso assumido."),
    ("Chance", "num", "Probabilidade de entregar todo o escopo até a data alvo, em 10.000 simulações do "
                      "ritmo real do Epic. Abaixo de 40% = vão atrasar; de 40% a 70% = atenção; 70% ou mais = no prazo."),
    ("P50", "txt", "Data em que metade das simulações termina: a data mais provável de conclusão."),
    ("P85", "txt", "Data em que 85% das simulações terminam: a data segura para prometer. "
                   "Se cai depois da data alvo, o compromisso está em risco."),
    ("Restante", "num", "Itens do escopo (PBI, Bug, Habilitator, Spike) ainda não concluídos."),
    ("Ritmo/sem", "num", "Média de itens entregues por semana nas últimas 12 semanas "
                         "(semanas sem entrega contam como zero; nada antes de 02/03/2026, por causa da migração)."),
    ("Razão", "num", "Quantas vezes mais rápido o time precisa entregar para cumprir a data, contando o escopo novo "
                     "que costuma entrar. 1,0× = o ritmo atual basta; acima de 1 = precisa acelerar; abaixo de 1 = há folga."),
    ("Motivos", "txt", "Regras que explicam o risco: aceleração necessária, tempo sem entregas, escopo crescendo, "
                       "itens sem responsável e Features com data vencida."),
]

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_MESES_A_FRENTE = 6

_CSS = """
:root{--fundo:#f6f6f3;--papel:#fff;--texto:#1d1d1b;--suave:#5f5e5a;--linha:#e3e2dd;--foco:#2563eb;
--vermelho:#c0362c;--amarelo:#b7791f;--ja_atrasado:#7a1f17;--sem_como_prever:#a3a29d;--verde:#2f7d32;
--aviso-f:#fff4e5;--aviso-t:#7a4100;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--fundo:#161615;--papel:#20201f;--texto:#ecebe7;--suave:#a9a8a3;
--linha:#363634;--foco:#60a5fa;--vermelho:#f97066;--amarelo:#fdb022;--ja_atrasado:#fecdca;
--sem_como_prever:#6b6a66;--verde:#6ce9a6;--aviso-f:#3d2a10;--aviso-t:#fedf89;color-scheme:dark}}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--fundo);color:var(--texto);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1320px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:24px;margin:0 0 2px}h2{font-size:15px;margin:0 0 10px}
.sub{color:var(--suave);margin:0}
button{font:inherit;color:inherit}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--foco);outline-offset:2px}
.aviso{background:var(--aviso-f);color:var(--aviso-t);border-radius:8px;padding:10px 14px;margin:14px 0}
.cartao{background:var(--papel);border:1px solid var(--linha);border-radius:10px;padding:14px 16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr));gap:10px;margin:14px 0 6px}
.kpi{text-align:left;background:var(--papel);border:1px solid var(--linha);border-left:5px solid var(--cor);
border-radius:10px;padding:10px 14px;cursor:pointer}
.kpi b{display:block;font-size:28px;line-height:1.2;color:var(--cor)}.kpi span{font-weight:600}
.kpi small{display:block;color:var(--suave);font-size:12px;line-height:1.35;margin-top:2px}
.kpi:hover{border-color:var(--cor)}.kpi[aria-pressed=true]{box-shadow:0 0 0 2px var(--cor) inset;border-color:var(--cor)}
.vermelho{--cor:var(--vermelho)}.amarelo{--cor:var(--amarelo)}.ja_atrasado{--cor:var(--ja_atrasado)}
.sem_como_prever{--cor:var(--sem_como_prever)}.verde{--cor:var(--verde)}
.reconc{font-size:12px;margin-bottom:14px}
.paineis{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:12px;margin-bottom:12px}
@media (max-width:900px){.paineis{grid-template-columns:minmax(0,1fr)}}
.cartao{min-width:0}
.dica{color:var(--suave);font-size:12px;font-weight:400}
.linha-barra{display:grid;grid-template-columns:minmax(90px,210px) minmax(0,1fr) 34px;gap:8px;align-items:center;width:100%;
background:none;border:0;border-radius:6px;padding:3px 4px;cursor:pointer;text-align:left}
.linha-barra:hover,.coluna:hover{background:color-mix(in srgb,var(--texto) 6%,transparent)}
.linha-barra[aria-pressed=true],.coluna[aria-pressed=true]{background:color-mix(in srgb,var(--foco) 14%,transparent)}
.linha-barra .rot{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trilho{display:flex;height:14px;border-radius:3px;overflow:hidden}
.trilho i,.pilha i{display:block;background:var(--cor)}
.tot{font-size:12px;color:var(--suave);text-align:right;font-variant-numeric:tabular-nums}
.colunas{display:flex;gap:4px;align-items:stretch}
.coluna{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;background:none;border:0;
border-radius:6px;padding:4px 2px;cursor:pointer;min-width:0}
.area-pilha{height:150px;width:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}
.pilha{width:70%;max-width:38px;display:flex;flex-direction:column-reverse;border-radius:3px 3px 0 0;overflow:hidden}
.coluna .rot{font-size:12px;line-height:1.2;text-align:center}.coluna .tot{text-align:center}
.cores{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:10px;font-size:12px;color:var(--suave)}
.cores span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--cor);margin-right:5px;vertical-align:-1px}
.ferramentas{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:4px 0 10px}
.so-js{display:none}.js .so-js{display:flex}
.ferramentas input,.ferramentas select{background:var(--papel);border:1px solid var(--linha);border-radius:8px;padding:7px 10px;font:inherit;color:inherit}
.ferramentas input{flex:1 1 260px;min-width:0}.ferramentas select{max-width:100%}
.contador{color:var(--suave);font-size:13px}
.limpar{background:none;border:1px solid var(--linha);border-radius:8px;padding:5px 10px;cursor:pointer}
details.legenda{margin-bottom:12px}details.legenda summary{cursor:pointer;font-weight:600}
.legenda dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:12px 0 0}
.legenda dt{font-weight:600}.legenda dd{margin:0;color:var(--suave)}
@media (max-width:600px){.legenda dl{grid-template-columns:1fr}.legenda dd{margin-bottom:6px}}
.tabela{overflow:auto;max-height:78vh;background:var(--papel);border:1px solid var(--linha);border-radius:10px}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:1080px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--linha);vertical-align:top}
th{position:sticky;top:0;z-index:1;background:var(--papel);font-size:12px;color:var(--suave);font-weight:600;white-space:nowrap}
th button{background:none;border:0;padding:0;cursor:pointer;font-weight:600;color:inherit;text-decoration:underline dotted;text-underline-offset:3px}
th[aria-sort=ascending] button::after{content:" ▲"}th[aria-sort=descending] button::after{content:" ▼"}
tbody tr:hover td{background:color-mix(in srgb,var(--texto) 4%,transparent)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.selo{display:inline-block;white-space:nowrap;font-size:12px;font-weight:600;color:var(--cor);
background:color-mix(in srgb,var(--cor) 14%,transparent);border-radius:999px;padding:1px 8px}
td.titulo{min-width:300px}.tit{font-weight:500}.area{color:var(--suave);font-size:12px}
.chance{display:flex;align-items:center;justify-content:flex-end;gap:6px}
.barra-chance{width:46px;height:6px;border-radius:3px;background:var(--linha);overflow:hidden}
.barra-chance i{display:block;height:100%;background:var(--cor)}
.motivos{min-width:240px}.chip{display:inline-block;font-size:12px;line-height:1.35;border:1px solid var(--linha);
border-radius:6px;padding:1px 6px;margin:0 4px 4px 0;color:var(--suave)}
.narrativa{margin-top:4px}.vazio td{text-align:center;color:var(--suave);padding:28px}
"""

_JS = r"""
(function(){
  document.documentElement.classList.add('js');
  const norm=s=>s.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
  // Cada .painel (aba) tem a própria tabela, busca e filtros; data-filtro="x" filtra tr[data-x].
  function painel(raiz){
    const corpo=raiz.querySelector('table.dados tbody');
    if(!corpo)return;
    const linhas=[...corpo.querySelectorAll('tr[data-busca]')];
    const vazio=corpo.querySelector('tr.vazio');
    const busca=raiz.querySelector('.f-busca'),limpar=raiz.querySelector('.limpar'),contador=raiz.querySelector('.contador');
    const selects=[...raiz.querySelectorAll('select[data-filtro-sel]')];
    const botoes=[...raiz.querySelectorAll('[data-filtro]')];
    const unidade=raiz.dataset.unidade||'itens',total=linhas.length,estado={},rotulos={};
    let q='';
    botoes.forEach(b=>{
      const f=b.dataset.filtro;
      (rotulos[f]=rotulos[f]||{})[b.dataset.valor]=b.dataset.rotulo;
      b.addEventListener('click',()=>{estado[f]=estado[f]===b.dataset.valor?'':b.dataset.valor;sincronizar();aplicar();});
    });
    selects.forEach(s=>{
      const f=s.dataset.filtroSel;
      rotulos[f]=rotulos[f]||{};
      [...s.options].forEach(o=>{if(o.value)rotulos[f][o.value]=o.text;});
      s.addEventListener('change',()=>{estado[f]=s.value;aplicar();});
    });
    function sincronizar(){selects.forEach(s=>{s.value=estado[s.dataset.filtroSel]||'';});}
    raiz.filtrar=(f,v)=>{for(const k in estado)estado[k]='';q='';busca.value='';estado[f]=v;sincronizar();aplicar();};
    busca.addEventListener('input',()=>{q=norm(busca.value.trim());aplicar();});
    limpar.addEventListener('click',()=>{for(const f in estado)estado[f]='';q='';busca.value='';sincronizar();aplicar();});
    function aplicar(){
      let n=0;
      for(const tr of linhas){
        let ok=!q||tr.dataset.busca.includes(q);
        for(const f in estado){if(ok&&estado[f]&&tr.dataset[f]!==estado[f])ok=false;}
        tr.hidden=!ok;if(ok)n++;
      }
      vazio.hidden=n>0;
      botoes.forEach(b=>b.setAttribute('aria-pressed',String(estado[b.dataset.filtro]===b.dataset.valor)));
      const ativos=Object.keys(estado).filter(f=>estado[f]).map(f=>(rotulos[f]||{})[estado[f]]||estado[f]);
      if(q)ativos.push('"'+busca.value.trim()+'"');
      contador.textContent=(n===total?'Mostrando todos os '+total+' '+unidade:'Mostrando '+n+' de '+total+' '+unidade)
        +(ativos.length?' · filtro: '+ativos.join(' · '):'');
      limpar.hidden=!ativos.length;
      raiz.dispatchEvent(new CustomEvent('filtros',{detail:Object.assign({},estado)}));
    }
    raiz.querySelectorAll('table.dados th button').forEach(btn=>btn.addEventListener('click',()=>{
      const th=btn.closest('th'),col=th.cellIndex,num=th.dataset.tipo==='num';
      const dir=th.getAttribute('aria-sort')==='ascending'?'descending':'ascending',k=dir==='ascending'?1:-1;
      raiz.querySelectorAll('table.dados th').forEach(t=>t.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort',dir);
      const v=tr=>tr.cells[col].dataset.v;
      linhas.sort((a,b)=>{
        const x=v(a),y=v(b);
        if(x===y)return 0;if(x==='')return 1;if(y==='')return -1;
        return (num?(+x)-(+y):x.localeCompare(y,'pt-BR'))*k;
      });
      linhas.forEach(tr=>corpo.appendChild(tr));corpo.appendChild(vazio);
    }));
    aplicar();
  }
  document.querySelectorAll('.painel').forEach(painel);
  // Abas: sem JS as duas aparecem em sequência; com JS, uma por vez.
  const abas=[...document.querySelectorAll('.abas [role=tab]')];
  abas.forEach(a=>a.addEventListener('click',()=>abas.forEach(b=>{
    const on=b===a;b.setAttribute('aria-selected',String(on));
    document.getElementById(b.getAttribute('aria-controls')).hidden=!on;
  })));
  if(abas.length)abas[0].click();
})();
"""


def _data_br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"


def _num(x, fmt: str) -> str:
    return "—" if x is None or x == "" else fmt.format(x).replace(".", ",")


def _v(x) -> str:
    """Valor de ordenação para o atributo data-v (vazio vai sempre para o fim)."""
    return "" if x is None or x == "" else escape(str(x), quote=True)


def _area(area: str) -> str:
    return " › ".join(area.split("\\")[1:3]) or area


def _programa(area: str) -> str:
    partes = area.split("\\")
    return partes[1] if len(partes) > 1 else area


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower()


def _faixa_mes(data_alvo: str, hoje: date) -> str:
    """Faixa da data alvo para o gráfico de prazos: vencida, um dos próximos meses, depois ou sem data."""
    if not data_alvo:
        return "sem"
    alvo = date.fromisoformat(data_alvo)
    if alvo < hoje:
        return "vencida"
    meses = (alvo.year - hoje.year) * 12 + alvo.month - hoje.month
    return f"{alvo.year}-{alvo.month:02d}" if meses < _MESES_A_FRENTE else "depois"


def _faixas(hoje: date) -> list[tuple[str, str]]:
    faixas = [("vencida", "Vencida")]
    for k in range(_MESES_A_FRENTE):
        ano, mes = divmod(hoje.month - 1 + k, 12)
        ano += hoje.year
        faixas.append((f"{ano}-{mes + 1:02d}", f"{_MESES[mes]}/{ano % 100:02d}"))
    return faixas + [("depois", "Depois"), ("sem", "Sem data")]


def _segmentos(contagem: Counter, dimensao: str, escala: int) -> str:
    return "".join(
        f'<i class="{s}" style="{dimensao}:{contagem[s] / escala:.2%}" '
        f'title="{contagem[s]} {_TITULOS[s][0].lower()}"></i>'
        for s in ORDEM_SECOES if contagem[s])


def _kpis(por_secao: dict[str, list[dict]]) -> str:
    cartoes = []
    for s in ORDEM_SECOES:
        titulo, desc = _TITULOS[s]
        cartoes.append(
            f'<button type="button" class="kpi {s}" data-filtro="secao" data-valor="{s}" '
            f'data-rotulo="{escape(titulo, quote=True)}" aria-pressed="false">'
            f"<b>{len(por_secao[s])}</b><span>{titulo}</span><small>{desc}</small></button>")
    return '<div class="kpis">' + "".join(cartoes) + "</div>"


def _grafico_programas(linhas: list[dict]) -> str:
    por: dict[str, Counter] = {}
    for l in linhas:
        por.setdefault(_programa(l["area"]), Counter())[l["secao"]] += 1
    maior = max((sum(c.values()) for c in por.values()), default=1)
    barras = []
    for prog, c in sorted(por.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        p = escape(prog, quote=True)
        barras.append(
            f'<button type="button" class="linha-barra" data-filtro="programa" data-valor="{p}" data-rotulo="{p}" '
            f'aria-pressed="false"><span class="rot" title="{p}">{p}</span>'
            f'<span class="trilho">{_segmentos(c, "width", maior)}</span><span class="tot">{sum(c.values())}</span></button>')
    return ('<section class="cartao"><h2>Epics por programa <span class="dica">· clique para filtrar</span></h2>'
            + "".join(barras) + "</section>")


def _grafico_prazos(linhas: list[dict], hoje: date) -> str:
    por: dict[str, Counter] = {}
    for l in linhas:
        por.setdefault(_faixa_mes(l["data_alvo"], hoje), Counter())[l["secao"]] += 1
    maior = max((sum(c.values()) for c in por.values()), default=1)
    colunas = []
    for chave, rotulo in _faixas(hoje):
        c = por.get(chave, Counter())
        tot = sum(c.values())
        colunas.append(
            f'<button type="button" class="coluna" data-filtro="mes" data-valor="{chave}" '
            f'data-rotulo="data alvo: {rotulo}" aria-pressed="false"><span class="tot">{tot}</span>'
            f'<span class="area-pilha"><span class="pilha" style="height:{tot / maior:.2%}">'
            f'{_segmentos(c, "height", max(tot, 1))}</span></span><span class="rot">{rotulo}</span></button>')
    cores = "".join(f'<span class="{s}">{_TITULOS[s][0]}</span>' for s in ORDEM_SECOES)
    return ('<section class="cartao"><h2>Datas alvo por mês <span class="dica">· clique para filtrar</span></h2>'
            f'<div class="colunas">{"".join(colunas)}</div><div class="cores">{cores}</div></section>')


def _legenda() -> str:
    itens = "".join(f"<dt>{nome}</dt><dd>{texto}</dd>" for nome, _, texto in _COLUNAS)
    return ('<details class="legenda cartao"><summary>Como ler este relatório</summary>'
            "<p class=\"sub\">Cada linha é um Epic aberto do projeto. O escopo são os PBIs, Bugs, Habilitators e "
            "Spikes abaixo dele (Tasks e Test Cases não contam). Passe o mouse no nome de uma coluna para ver a "
            f"explicação, ou clique para ordenar.</p><dl>{itens}</dl></details>")


def _ferramentas(linhas: list[dict]) -> str:
    programas = sorted({_programa(l["area"]) for l in linhas})
    opcoes = "".join(f'<option value="{escape(p, quote=True)}">{escape(p)}</option>' for p in programas)
    return ('<div class="ferramentas so-js">'
            '<input class="f-busca" type="search" placeholder="Buscar por id, título, área ou motivo" '
            'aria-label="Buscar Epics">'
            f'<select data-filtro-sel="programa" aria-label="Filtrar por programa"><option value="">Todos os programas</option>'
            f"{opcoes}</select>"
            '<span class="contador" aria-live="polite"></span>'
            '<button type="button" class="limpar" hidden>Limpar filtros</button></div>')


def _linha(l: dict, hoje: date, narrador: Narrador) -> str:
    s = l["secao"]
    narrativa = narrador.narrar(l)
    chips = "".join(f'<span class="chip">{escape(m.strip())}</span>' for m in l["motivos"].split(";") if m.strip())
    if narrativa:
        chips += f'<div class="narrativa">{escape(narrativa)}</div>'
    prob = l["prob_cumprir"]
    chance = (f'<div class="chance"><span class="barra-chance"><i style="width:{prob:.0%}"></i></span>'
              f'{_num(prob, "{:.0%}")}</div>') if prob is not None else "—"
    busca = _sem_acento(f"{l['epic_id']} {l['titulo']} {l['area']} {l['motivos']}")
    celulas = [
        f'<td data-v="{ORDEM_SECOES.index(s)}"><span class="selo">{_TITULOS[s][0]}</span></td>',
        f'<td class="num" data-v="{l["epic_id"]}">{l["epic_id"]}</td>',
        f'<td class="titulo" data-v="{_v(l["titulo"])}"><div class="tit">{escape(l["titulo"])}</div>'
        f'<div class="area">{escape(_area(l["area"]))}</div></td>',
        f'<td class="num" data-v="{_v(l["data_alvo"])}">{_data_br(l["data_alvo"])}</td>',
        f'<td class="num" data-v="{_v(prob)}">{chance}</td>',
        f'<td class="num" data-v="{_v(l["p50"])}">{_data_br(l["p50"])}</td>',
        f'<td class="num" data-v="{_v(l["p85"])}">{_data_br(l["p85"])}</td>',
        f'<td class="num" data-v="{l["restante"]}">{l["restante"]}</td>',
        f'<td class="num" data-v="{_v(l["ritmo_medio"])}">{_num(l["ritmo_medio"], "{:.1f}")}</td>',
        f'<td class="num" data-v="{_v(l["razao_ritmo"])}">{_num(l["razao_ritmo"], "{:.1f}×")}</td>',
        f'<td class="motivos" data-v="{_v(l["motivos"])}">{chips}</td>',
    ]
    return (f'<tr class="{s}" data-epic="{l["epic_id"]}" data-secao="{s}" data-programa="{escape(_programa(l["area"]), quote=True)}" '
            f'data-mes="{_faixa_mes(l["data_alvo"], hoje)}" data-busca="{escape(busca, quote=True)}">'
            + "".join(celulas) + "</tr>")


def _tabela(linhas: list[dict], hoje: date, narrador: Narrador) -> str:
    cab = "".join(f'<th data-tipo="{tipo}" title="{escape(texto, quote=True)}" scope="col">'
                  f'<button type="button">{nome}</button></th>' for nome, tipo, texto in _COLUNAS)
    corpo = "".join(_linha(l, hoje, narrador) for l in linhas)
    vazio = f'<tr class="vazio" hidden><td colspan="{len(_COLUNAS)}">Nenhum Epic com esses filtros.</td></tr>'
    return (f'<div class="tabela"><table class="dados"><thead><tr>{cab}</tr></thead>'
            f"<tbody>{corpo}{vazio}</tbody></table></div>")


def rotulos_mes(hoje: date) -> dict[str, str]:
    """Faixas da data alvo como aparecem numa frase ("com data alvo em nov/26")."""
    frase = {"vencida": "já vencida", "depois": "mais adiante", "sem": "não definida"}
    return {k: frase.get(k, f"em {r}") for k, r in _faixas(hoje)}


def faixa_de(hoje: date):
    return lambda l: _faixa_mes(l["data_alvo"], hoje)


def gerar_html(linhas: list[dict], hoje: date, extracao: str, narrador: Narrador = NarradorNulo(),
               riscos_html: str = "", agente: "painel_agente.Agente | None" = None) -> str:
    """Painel semanal. Com `riscos_html` (a aba gerada por `riscos.painel`), ganha as abas Radar | Riscos;
    com `agente`, ganha pauta, perguntas, leitura por filtro e painel lateral do Epic."""
    por_secao = {s: [l for l in linhas if l["secao"] == s] for s in ORDEM_SECOES}
    reconciliacao = " + ".join(f"{len(por_secao[s])} {_TITULOS[s][0].lower()}" for s in ORDEM_SECOES)
    projeto = linhas[0]["area"].split("\\")[0] if linhas else ""   # raiz da área = nome do projeto no ADO
    abas = aba_riscos = ""
    if riscos_html:
        abas = ('<nav class="abas so-js" role="tablist">'
                '<button type="button" role="tab" aria-controls="aba-radar" aria-selected="true">Radar de datas</button>'
                '<button type="button" role="tab" aria-controls="aba-riscos" aria-selected="false">Riscos</button></nav>')
        aba_riscos = f'<section class="painel" id="aba-riscos" role="tabpanel" data-unidade="riscos">{riscos_html}</section>'
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Radar de Datas — {hoje.strftime('%d/%m/%Y')}</title><style>{_CSS}{CSS_RISCOS}{painel_agente.CSS}</style></head>
<body><main>
<h1>Radar de Datas</h1>
<p class="sub">Projeto {escape(projeto)} · previsão de {hoje.strftime('%d/%m/%Y')} · extração {escape(extracao)} · modelo {MODELO_VERSAO}</p>
{painel_agente.topo(agente) if agente else ""}
{abas}
<section class="painel" id="aba-radar" role="tabpanel" data-unidade="Epics">
<div class="aviso"><b>Uso interno — modelo em validação.</b> No backtest, 71% dos Epics marcados como
"vão atrasar" atrasaram de fato (a média geral é 57%). O modelo só vai para a diretoria depois do teste
com dados futuros, em 28/12/2026.</div>
{_kpis(por_secao)}
{painel_agente.caixa_leitura("radar") if agente else ""}
<p class="sub reconc">{len(linhas)} Epics abertos = {reconciliacao}</p>
<div class="paineis">{_grafico_programas(linhas)}{_grafico_prazos(linhas, hoje)}</div>
{_legenda()}
{_ferramentas(linhas)}
{_tabela(linhas, hoje, narrador)}
</section>
{aba_riscos}
</main>
{painel_agente.GAVETA + painel_agente.chat(agente) + painel_agente.dados_script(agente) if agente else ""}
<script>{_JS}</script>{f"<script>{painel_agente.JS}</script>" if agente else ""}
</body></html>
"""
