"""Partes do painel que o agente alimenta (SPEC-dashboard-inteligente.md).

- topo: pauta da semana, perguntas sugeridas e "Perguntas desta reunião";
- caixa "Leitura do agente" em cada aba, que reage aos filtros (significado por regra + resumo do recorte);
- painel lateral do Epic (clique no título).

Tudo é estático: os textos vêm prontos num JSON embutido e o JS só escolhe o que mostrar.
A única exceção é o chat do canto inferior direito: quando a página é aberta pelo `radar servir`
(radar/servidor.py), ele manda a pergunta para o servidor local.
"""
import json
from dataclasses import dataclass, field
from html import escape

from explicacao.fatos import CATEGORIA, CRITICIDADE, SECAO, _area, _data, _decimal, por_epic
from explicacao.recortes import gravidade
from explicacao.validador import cita_radar

# Radar validado (2026-11-21). False volta o aviso "modelo em validação" e o selo nos textos que usam a previsão.
RADAR_APROVADO = True
# Pauta, perguntas sugeridas e resumos: False mostra "em validação" até a revisão do apresentador (critério 12).
AGENTE_APROVADO = False

SELO = '<span class="selo-ia" title="Usa a previsão do Radar, que ainda está em validação">previsão em validação</span>'


@dataclass
class Agente:
    """O que o agente produziu para o painel. Textos já com os nomes reais e prontos para escapar."""
    pauta: list[dict] = field(default_factory=list)          # {"epic", "texto", "usa_radar"}
    sugeridas: list[dict] = field(default_factory=list)      # {"pergunta", "resposta", "usa_radar"}
    perguntas: list[dict] = field(default_factory=list)      # {"hora", "pergunta", "resposta", "usa_radar"}
    leitura: dict = field(default_factory=dict)              # {"radar": {"filtro:valor": texto}, "riscos": {...}}
    resumos: dict = field(default_factory=dict)              # {"geral" | "programa:X" | "categoria:Y": {"t", "radar"}}
    epics: dict = field(default_factory=dict)                # {"id": dados do painel lateral}


def _selo(usa_radar: bool) -> str:
    return SELO if usa_radar and not RADAR_APROVADO else ""


def dados_epics(linhas_radar: list[dict], linhas_riscos: list[dict], causas: dict[int, str]) -> dict:
    """Dados do painel lateral de cada Epic aberto (Radar ∪ registro de riscos)."""
    radar = {int(l["epic_id"]): l for l in linhas_radar}
    grupos = por_epic(linhas_riscos)
    saida = {}
    for e in sorted(set(radar) | set(grupos)):
        rs = sorted(grupos.get(e, []), key=gravidade)
        r = radar.get(e)
        base = rs[0] if rs else r
        prob = r.get("prob_cumprir") if r else None
        saida[str(e)] = {
            "t": base["titulo"], "a": _area(base["area"]), "alvo": _data(base["data_alvo"]),
            "dono": (rs[0]["dono"] if rs else r.get("responsavel", "")) or "",
            "radar": {"s": SECAO.get(r["secao"], r["secao"]),
                      "c": "" if prob in (None, "") else f"{float(prob):.0%}",
                      "p85": _data(r.get("p85")),
                      "m": [m.strip() for m in str(r.get("motivos") or "").split(";") if m.strip()]} if r else None,
            "riscos": [[CRITICIDADE[x["criticidade"]], x["criticidade"], CATEGORIA[x["categoria"]], x["evidencia"],
                        x["escalar"] == "sim"] for x in rs],
            "causa": causas.get(e, ""),
            "cr": bool(r) and cita_radar(causas.get(e, "")),
        }
    return saida


def _json(dados: dict) -> str:
    # `<` escapado: nenhum título com "</script>" consegue fechar o bloco.
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def dados_script(agente: Agente) -> str:
    dados = {"leitura": agente.leitura, "resumos": agente.resumos, "epics": agente.epics,
             "selo": not RADAR_APROVADO}
    return f'<script type="application/json" id="agente-dados">{_json(dados)}</script>'


def _aviso_validacao() -> str:
    if AGENTE_APROVADO:
        return ""
    return ('<p class="aviso-ia"><b>Textos do agente em validação.</b> Redigidos por IA só a partir dos números '
            "do painel; números e ids são conferidos automaticamente.</p>")


def topo(agente: Agente) -> str:
    partes = []
    if agente.pauta:
        itens = "".join(
            f'<li><button type="button" class="ponto" data-ir-epic="{escape(str(p["epic"]))}">'
            f'{escape(p["texto"])}</button>{_selo(p["usa_radar"])}</li>' for p in agente.pauta)
        partes.append(f'<section class="cartao pauta"><h2>Pauta da semana <span class="dica">· clique para ver os riscos'
                      f'</span></h2>{_aviso_validacao()}<ol>{itens}</ol></section>')
    if agente.sugeridas:
        itens = "".join(f'<details><summary>{escape(s["pergunta"])}</summary><p>{escape(s["resposta"])}'
                        f'{_selo(s["usa_radar"])}</p></details>' for s in agente.sugeridas)
        partes.append(f'<section class="cartao sugeridas"><h2>Perguntas que vale fazer hoje</h2>{itens}</section>')
    if agente.perguntas:
        itens = "".join(f'<li><div class="pq"><span class="hora">{escape(q["hora"])}</span> {escape(q["pergunta"])}</div>'
                        f'<p>{escape(q["resposta"])}{_selo(q["usa_radar"])}</p></li>' for q in agente.perguntas)
        partes.append(f'<section class="cartao reuniao"><h2>Perguntas desta reunião (<span id="pq-n">'
                      f'{len(agente.perguntas)}</span>)</h2><ul id="pq-lista">{itens}</ul></section>')
    return f'<div class="agente-topo">{"".join(partes)}</div>' if partes else ""


_ICONE_CHAT = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
               '<path d="M21 12a8 8 0 0 1-8 8H4l2.3-3.1A8 8 0 1 1 21 12z"/></svg>')


def chat(agente: Agente) -> str:
    """Chat do agente no canto inferior direito, já com as perguntas do dia (a mais antiga em cima).

    Enviar só funciona quando a página vem do `radar servir` (o JS confere); aberta como arquivo,
    a conversa do dia continua visível e o campo fica desligado, com a instrução.
    """
    historico = "".join(
        f'<p class="chat-m eu">{escape(q["pergunta"])}</p>'
        f'<p class="chat-m agente">{escape(q["resposta"])}{_selo(q["usa_radar"])}'
        f'<span class="meta">{escape(q["hora"])}</span></p>' for q in reversed(agente.perguntas))
    return ('<div class="chat" id="chat">'
            '<section class="chat-janela" id="chat-janela" role="dialog" aria-labelledby="chat-tit" hidden>'
            '<header><h2 id="chat-tit">Pergunte ao agente</h2>'
            '<button type="button" class="chat-fechar" aria-label="Fechar o chat">×</button></header>'
            '<div class="chat-msgs" id="chat-msgs" role="log" aria-live="polite">'
            '<p class="chat-m agente">Pergunte sobre os Epics, programas e riscos deste painel. '
            'Respondo só com os números que estão aqui.</p>'
            f'{historico}</div>'
            '<p class="chat-off" id="pq-off" hidden>Para perguntar, abra o painel com '
            '<code>python -m radar servir</code>.</p>'
            '<form id="pq-form"><input id="pq-texto" type="text" maxlength="300" required autocomplete="off" '
            'aria-label="Pergunta ao agente" placeholder="Por que Obras Sul piorou?">'
            '<button type="submit">Enviar</button></form></section>'
            '<button type="button" class="chat-abrir" id="chat-abrir" aria-expanded="false" aria-controls="chat-janela">'
            f'{_ICONE_CHAT}Pergunte ao agente</button></div>')


def caixa_leitura(aba: str) -> str:
    return f'<section class="cartao leitura" data-aba="{aba}" aria-live="polite" hidden></section>'


GAVETA = ('<aside class="gaveta" id="gaveta" role="dialog" aria-modal="false" aria-labelledby="gaveta-tit" hidden>'
          '<button type="button" class="fechar" aria-label="Fechar">×</button><div class="conteudo"></div></aside>')

CSS = """
.agente-topo{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:12px;margin:14px 0 4px}
.agente-topo .reuniao{grid-column:1/-1}
@media (max-width:900px){.agente-topo{grid-template-columns:minmax(0,1fr)}}
.pauta ol{margin:0;padding-left:22px}.pauta li{margin:4px 0}
.ponto{background:none;border:0;padding:0;text-align:left;cursor:pointer;line-height:1.45}
.ponto:hover{text-decoration:underline}
.sugeridas details{border-top:1px solid var(--linha);padding:6px 0}.sugeridas details:first-of-type{border-top:0}
.sugeridas summary{cursor:pointer;font-weight:600}.sugeridas p,.reuniao p{margin:6px 0 0;line-height:1.45}
.reuniao ul{list-style:none;margin:0;padding:0}.reuniao li{border-top:1px solid var(--linha);padding:8px 0}
.reuniao li:first-child{border-top:0}.pq{font-weight:600}.hora{color:var(--suave);font-weight:400;font-size:12px}
.chat{position:fixed;right:18px;bottom:18px;z-index:9;display:flex;flex-direction:column;align-items:flex-end;gap:10px}
.chat-abrir{display:flex;align-items:center;gap:8px;border:0;background:#2563eb;color:#fff;border-radius:999px;
padding:11px 16px;font-weight:600;cursor:pointer;box-shadow:0 6px 18px rgba(0,0,0,.28)}
.chat-abrir:hover{background:#1d4ed8}
.chat-janela{width:min(380px,calc(100vw - 36px));height:min(520px,calc(100vh - 110px));background:var(--papel);
border:1px solid var(--linha);border-radius:14px;box-shadow:0 12px 32px rgba(0,0,0,.28);display:flex;flex-direction:column;overflow:hidden}
.chat-janela[hidden]{display:none}
.chat-janela header{display:flex;align-items:center;justify-content:space-between;padding:10px 12px 10px 14px;
border-bottom:1px solid var(--linha)}
.chat-janela h2{margin:0;font-size:15px}
.chat-fechar{background:none;border:0;font-size:22px;line-height:1;cursor:pointer;padding:0 4px}
.chat-msgs{flex:1 1 auto;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:var(--fundo)}
.chat-m{max-width:86%;margin:0;padding:8px 11px;border-radius:12px;line-height:1.45;font-size:14px;overflow-wrap:anywhere}
.chat-m.eu{align-self:flex-end;background:#2563eb;color:#fff;border-bottom-right-radius:4px}
.chat-m.agente{align-self:flex-start;background:var(--papel);border:1px solid var(--linha);border-bottom-left-radius:4px}
.chat-m.erro{color:var(--vermelho)}.chat-m.espera{color:var(--suave);font-style:italic}
.chat-m .meta{display:block;margin-top:4px;font-size:11px;color:var(--suave)}
.chat-off{margin:0;padding:8px 12px;font-size:12px;color:var(--suave);border-top:1px solid var(--linha)}
#pq-form{display:flex;gap:8px;padding:10px;border-top:1px solid var(--linha)}
#pq-form input{flex:1 1 auto;min-width:0;background:var(--papel);border:1px solid var(--linha);border-radius:999px;
padding:8px 12px;font:inherit;color:inherit}
#pq-form button{border:0;background:#2563eb;color:#fff;border-radius:999px;padding:8px 14px;font-weight:600;cursor:pointer}
#pq-form button:disabled,#pq-form input:disabled{opacity:.55;cursor:not-allowed}
@media print{.chat{display:none}}
.selo-ia{display:inline-block;margin-left:6px;font-size:11px;font-weight:600;color:var(--aviso-t);
background:var(--aviso-f);border-radius:999px;padding:0 7px;vertical-align:1px;white-space:nowrap}
.leitura{margin:10px 0 12px}.leitura .resumo{margin:0 0 6px;line-height:1.5}
.leitura ul{margin:4px 0 0;padding-left:18px;color:var(--suave);font-size:13px}
.leitura .rec{font-size:12px;color:var(--suave);font-weight:400}
[data-epic] .tit{cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}
.gaveta{position:fixed;top:0;right:0;bottom:0;width:min(440px,100%);background:var(--papel);border-left:1px solid var(--linha);
box-shadow:-8px 0 24px rgba(0,0,0,.12);padding:20px 20px 32px;overflow:auto;z-index:10}
.gaveta .fechar{position:absolute;top:10px;right:12px;background:none;border:0;font-size:24px;cursor:pointer;line-height:1}
.gaveta h2{font-size:17px;margin:0 28px 2px 0}.gaveta h3{font-size:13px;margin:16px 0 4px;color:var(--suave)}
.gaveta ul{margin:0;padding-left:18px}.gaveta li{margin:3px 0}.gaveta p{margin:4px 0;line-height:1.5}
"""

JS = r"""
(function(){
  const el=document.getElementById('agente-dados');
  if(!el)return;
  const D=JSON.parse(el.textContent);
  function no(tag,cls,txt){const n=document.createElement(tag);if(cls)n.className=cls;if(txt!=null)n.textContent=txt;return n;}
  function selo(radar){if(!(radar&&D.selo))return null;const s=no('span','selo-ia','previsão em validação');
    s.title='Usa a previsão do Radar, que está em teste até 28/12/2026';return s;}
  // Leitura do agente: significado de cada filtro ativo (regra) + resumo do recorte (LLM).
  document.querySelectorAll('.leitura').forEach(box=>{
    const aba=box.dataset.aba,raiz=box.closest('.painel'),L=D.leitura[aba]||{};
    function render(estado){
      box.replaceChildren();
      const prog=estado.programa,cat=estado.categoria;
      const alvo=prog&&D.resumos['programa:'+prog]?'programa:'+prog:cat&&D.resumos['categoria:'+cat]?'categoria:'+cat:'geral';
      const r=D.resumos[alvo];
      const h=no('h2',null,'Leitura do agente ');
      h.appendChild(no('span','rec',alvo==='geral'?'· painel inteiro':'· '+(prog&&alvo.startsWith('programa')?prog:alvo.split(':')[1])));
      box.appendChild(h);
      if(r){const p=no('p','resumo',r.t+' ');const s=selo(r.radar);if(s)p.appendChild(s);box.appendChild(p);}
      const linhas=Object.keys(estado).filter(f=>estado[f]).map(f=>L[f+':'+estado[f]]).filter(Boolean);
      if(linhas.length){const ul=no('ul');linhas.forEach(t=>ul.appendChild(no('li',null,t)));box.appendChild(ul);}
      box.hidden=!r&&!linhas.length;
    }
    if(raiz)raiz.addEventListener('filtros',e=>render(e.detail));
    render({});
  });
  // Painel lateral do Epic.
  const gav=document.getElementById('gaveta'),corpo=gav&&gav.querySelector('.conteudo');
  let volta=null;
  function fechar(){if(!gav||gav.hidden)return;gav.hidden=true;if(volta)volta.focus();}
  function abrir(id,origem){
    const e=D.epics[id];if(!e||!gav)return;
    corpo.replaceChildren();
    const h=no('h2',null,'#'+id+' '+e.t);h.id='gaveta-tit';corpo.appendChild(h);
    corpo.appendChild(no('p','area',e.a+' · data alvo '+(e.alvo||'—')+' · '+(e.dono||'sem dono')));
    if(e.causa){corpo.appendChild(no('h3',null,'Causa provável'));const p=no('p',null,e.causa+' ');
      const s=selo(e.cr);if(s)p.appendChild(s);corpo.appendChild(p);}
    if(e.radar){corpo.appendChild(no('h3',null,'Radar de datas'));
      const p=no('p',null,e.radar.s+(e.radar.c?' · chance de cumprir '+e.radar.c:'')+(e.radar.p85?' · término pessimista '+e.radar.p85:'')+' ');
      const s=selo(true);if(s)p.appendChild(s);corpo.appendChild(p);
      if(e.radar.m.length){const ul=no('ul');e.radar.m.forEach(m=>ul.appendChild(no('li',null,m)));corpo.appendChild(ul);}}
    if(e.riscos.length){corpo.appendChild(no('h3',null,'Riscos ('+e.riscos.length+')'));const ul=no('ul');
      e.riscos.forEach(([crit,cls,cat,ev,esc])=>{const li=no('li');const b=no('span','selo c-'+cls,crit);li.appendChild(b);
        li.appendChild(document.createTextNode(' '+cat+(esc?' · Escalar':'')+': '+ev));ul.appendChild(li);});corpo.appendChild(ul);}
    volta=origem||null;gav.hidden=false;gav.querySelector('.fechar').focus();
  }
  if(gav){
    gav.querySelector('.fechar').addEventListener('click',fechar);
    document.addEventListener('keydown',ev=>{if(ev.key==='Escape')fechar();});
    document.querySelectorAll('[data-epic] .tit').forEach(t=>{t.tabIndex=0;t.setAttribute('role','button');
      t.title='Ver o Epic no painel lateral';});
    document.addEventListener('click',ev=>{const t=ev.target.closest('[data-epic] .tit');
      if(t)abrir(t.closest('[data-epic]').dataset.epic,t);});
    document.addEventListener('keydown',ev=>{if(ev.key!=='Enter'&&ev.key!==' ')return;
      const t=ev.target.closest&&ev.target.closest('[data-epic] .tit');if(t){ev.preventDefault();abrir(t.closest('[data-epic]').dataset.epic,t);}});
  }
  // Chat do agente (canto inferior direito). Enviar só funciona com o servidor local (`radar servir`).
  const chat=document.getElementById('chat');
  if(chat){
    const abrirB=document.getElementById('chat-abrir'),jan=document.getElementById('chat-janela'),
      msgs=document.getElementById('chat-msgs'),form=document.getElementById('pq-form'),campo=document.getElementById('pq-texto'),
      botao=form.querySelector('button'),online=location.protocol.startsWith('http');
    function fim(){msgs.scrollTop=msgs.scrollHeight;}
    function mostrar(aberto,foco){
      jan.hidden=!aberto;abrirB.setAttribute('aria-expanded',String(aberto));
      try{sessionStorage.setItem('chat',aberto?'1':'');}catch(e){}
      if(aberto){fim();if(foco&&online)campo.focus();}else if(foco)abrirB.focus();
    }
    function bolha(cls,txt){const p=no('p','chat-m '+cls,txt);msgs.appendChild(p);fim();return p;}
    abrirB.addEventListener('click',()=>mostrar(jan.hidden,true));
    jan.querySelector('.chat-fechar').addEventListener('click',()=>mostrar(false,true));
    document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&!jan.hidden&&chat.contains(document.activeElement))mostrar(false,true);});
    let aberto=false;try{aberto=sessionStorage.getItem('chat')==='1';}catch(e){}
    if(aberto)mostrar(true,false);
    if(!online){campo.disabled=true;botao.disabled=true;document.getElementById('pq-off').hidden=false;}
    form.addEventListener('submit',async ev=>{
      ev.preventDefault();
      const pergunta=campo.value.trim();if(!online||!pergunta||botao.disabled)return;
      bolha('eu',pergunta);campo.value='';botao.disabled=true;campo.readOnly=true;
      const esp=bolha('agente espera','Consultando o painel…');
      try{
        const r=await fetch('/perguntar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pergunta})});
        const d=await r.json();
        if(!d.ok){esp.className='chat-m agente erro';esp.textContent=d.erro||'Não consegui responder.';}
        else{
          esp.className='chat-m agente';esp.textContent=d.resposta+' ';
          const s=selo(d.usa_radar);if(s)esp.appendChild(s);
          esp.appendChild(no('span','meta',d.hora+' · '+d.recorte));
          // Registro no topo ("Perguntas desta reunião"), se a seção já existe; senão ela aparece no próximo F5.
          const lista=document.getElementById('pq-lista'),cont=document.getElementById('pq-n');
          if(lista){const li=no('li'),pq=no('div','pq');
            pq.appendChild(no('span','hora',d.hora));pq.appendChild(document.createTextNode(' '+d.pergunta));
            const p=no('p',null,d.resposta+' ');const s2=selo(d.usa_radar);if(s2)p.appendChild(s2);
            li.appendChild(pq);li.appendChild(p);lista.prepend(li);if(cont)cont.textContent=lista.children.length;}
        }
      }catch(e){esp.className='chat-m agente erro';esp.textContent='Servidor local fora do ar. Rode de novo: python -m radar servir';}
      fim();botao.disabled=false;campo.readOnly=false;campo.focus();
    });
  }
  // Pauta: abre a aba Riscos filtrada no Epic.
  document.querySelectorAll('[data-ir-epic]').forEach(b=>b.addEventListener('click',()=>{
    const aba=document.querySelector('.abas [aria-controls=aba-riscos]'),riscos=document.getElementById('aba-riscos');
    if(aba)aba.click();
    if(riscos&&riscos.filtrar){riscos.filtrar('epic',b.dataset.irEpic);
      const t=riscos.querySelector('.tabela:last-of-type');if(t)t.scrollIntoView({behavior:'smooth',block:'start'});}
  }));
})();
"""
