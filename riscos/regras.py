"""Regras das 6 categorias de risco (SPEC-agente-de-riscos.md).

Cada regra olha um Epic aberto em `hoje` e devolve um `Sinal` (probabilidade alta ou
média, com a evidência em frases curtas e com números) ou None se não dispara. Nada de
Monte Carlo nem LLM: a razão de ritmo e o ritmo vêm das funções determinísticas do Radar.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from radar.dados import ESTADOS_FECHADOS, Dados, Item
from radar.motivos import crescimento_escopo, texto_crescimento
from radar.previsao import _concluido, entrada_semanal, razao_ritmo, ritmo_semanal

CATEGORIAS = ("PRAZO", "DEPENDENCIA", "CAPACIDADE", "ESCOPO", "QUALIDADE", "GOVERNANCA")
JANELA_RECENTE = timedelta(weeks=4)
RAZAO_ALTA, RAZAO_MEDIA = 1.5, 1.0
FRACAO_ALTA, FRACAO_MEDIA = 0.50, 0.20
MIN_QUALIDADE = 2
MAX_EVIDENCIAS_DEPENDENCIA = 3
# Só a frase é limitada (números extremos soam estranhos para a diretoria); a regra usa o valor exato.
RAZAO_EXIBIDA_MAX = 10.0


@dataclass(frozen=True)
class Sinal:
    categoria: str
    probabilidade: str               # "alta" | "media"
    evidencias: tuple[str, ...]
    estado: str = "aberto"           # "aberto" | "materializado"
    entre_programas: bool = False    # DEPENDENCIA: algum predecessor que pesa é de outro programa


@dataclass(frozen=True)
class Contexto:
    """O que as regras precisam saber de um Epic em `hoje`."""
    epic: Item
    existentes: list[Item]       # escopo criado antes de hoje
    restantes: list[Item]
    faults_abertas: list[Item]
    ritmo_medio: float
    entrada_media: float
    ultima_entrega: date | None


def programa(area: str) -> str:
    partes = area.split("\\")
    return partes[1] if len(partes) > 1 else area


def _decimal(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _data_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def contexto(epic: Item, dados: Dados, hoje: date) -> Contexto:
    existentes = [i for i in dados.escopo.get(epic.id, []) if i.criado < hoje]
    entregas = [i.fechado for i in existentes if _concluido(i, hoje)]
    ritmo, entrada = ritmo_semanal(existentes, hoje), entrada_semanal(existentes, hoje)
    return Contexto(
        epic=epic, existentes=existentes,
        restantes=[i for i in existentes if not _concluido(i, hoje)],
        faults_abertas=[f for f in dados.faults.get(epic.id, []) if f.criado < hoje and f.estado not in ESTADOS_FECHADOS],
        ritmo_medio=float(ritmo.mean()) if ritmo.size else 0.0,
        entrada_media=float(entrada.mean()) if entrada.size else 0.0,
        ultima_entrega=max(entregas, default=None),
    )


# --- Regras por categoria ----------------------------------------------------------------

def risco_prazo(c: Contexto, hoje: date) -> Sinal | None:
    alvo = c.epic.alvo
    if alvo is None:
        return None
    if alvo < hoje:
        dias = (hoje - alvo).days
        ha = _plural(dias // 7, "semana", "semanas") if dias >= 7 else _plural(dias, "dia", "dias")
        return Sinal("PRAZO", "alta", (f"data alvo vencida há {ha}; "
                                       f"{_plural(len(c.restantes), 'item restante', 'itens restantes')}",),
                     estado="materializado")
    if not c.restantes:
        return None   # escopo vazio é risco de ESCOPO; tudo entregue não é risco

    evidencias, alta = [], False
    if c.ultima_entrega is None:
        evidencias.append("nenhuma entrega registrada")
        alta = True
    elif (dias := (hoje - c.ultima_entrega).days) >= JANELA_RECENTE.days:
        evidencias.append(f"sem entregas há {dias // 7} semanas")
        alta = True
    elif c.ritmo_medio == 0:
        evidencias.append("nada entregue nas últimas 12 semanas")
        alta = True
    razao = razao_ritmo(len(c.restantes), c.ritmo_medio, c.entrada_media, (alvo - hoje).days)
    if razao is not None and razao >= RAZAO_MEDIA:
        vezes = "mais de 10" if razao > RAZAO_EXIBIDA_MAX else _decimal(razao)
        evidencias.insert(0, f"precisa entregar {vezes}× mais rápido")
        alta = alta or razao >= RAZAO_ALTA
    if not evidencias:
        return None
    return Sinal("PRAZO", "alta" if alta else "media", tuple(evidencias))


def risco_capacidade(c: Contexto) -> Sinal | None:
    if not c.restantes:
        return None
    sem_dono = sum(not i.responsavel for i in c.restantes)
    fracao = sem_dono / len(c.restantes)
    if fracao < FRACAO_MEDIA:
        return None
    return Sinal("CAPACIDADE", "alta" if fracao >= FRACAO_ALTA else "media",
                 (f"{sem_dono} de {len(c.restantes)} itens restantes sem responsável",))


def risco_escopo(c: Contexto, hoje: date) -> Sinal | None:
    if not c.existentes:
        if c.epic.alvo is not None and c.epic.alvo >= hoje:
            return Sinal("ESCOPO", "alta", ("data marcada sem nenhum item detalhado",))
        return None
    if (cresc := crescimento_escopo(c.existentes, hoje)) is None or cresc[0] < FRACAO_MEDIA:
        return None
    return Sinal("ESCOPO", "alta" if cresc[0] >= FRACAO_ALTA else "media", (texto_crescimento(*cresc),))


def risco_qualidade(c: Contexto) -> Sinal | None:
    if not c.restantes:
        return None
    faults = len(c.faults_abertas)
    bugs = sum(i.tipo == "Bug" for i in c.restantes)
    total = faults + bugs
    fracao = total / len(c.restantes)
    if total < MIN_QUALIDADE or fracao < FRACAO_MEDIA:
        return None
    partes = [p for p in (_plural(faults, "Fault", "Faults") if faults else "",
                          _plural(bugs, "Bug", "Bugs") if bugs else "") if p]
    return Sinal("QUALIDADE", "alta" if fracao >= FRACAO_ALTA else "media",
                 (f"{' e '.join(partes)} {'aberto' if total == 1 else 'abertos'} = {fracao:.0%} do restante",))


def risco_governanca(c: Contexto) -> Sinal | None:
    if c.epic.alvo is not None:
        return None
    return Sinal("GOVERNANCA", "media", ("Epic sem data alvo",))


def risco_dependencia(epic: Item, predecessores: list[Item], dados: Dados,
                      prazo: dict[int, Sinal], hoje: date) -> Sinal | None:
    """Segunda passada: usa o PRAZO já calculado do Epic de cada predecessor."""
    altas, medias, entre_programas = [], [], False
    # Vários itens do Epic podem depender do mesmo predecessor: ele conta uma vez só.
    unicos = {p.id: p for p in predecessores}
    for p in sorted(unicos.values(), key=lambda i: i.id):
        quem = f"#{p.id} ({p.tipo}, {programa(p.area)})"
        epic_p = dados.epic_de.get(p.id)
        sinal_p = prazo.get(epic_p) if epic_p is not None else None
        if p.alvo is not None and p.alvo < hoje:
            altas.append(f"depende de {quem}, vencida em {_data_br(p.alvo)}")
        elif sinal_p is not None and sinal_p.estado == "materializado":
            altas.append(f"depende de {quem}, cujo Epic #{epic_p} já está atrasado")
        elif sinal_p is not None and sinal_p.probabilidade == "alta":
            medias.append(f"depende de {quem}, cujo Epic #{epic_p} tem risco de prazo alto")
            continue
        else:
            continue
        entre_programas = entre_programas or programa(p.area) != programa(epic.area)
    evidencias = altas + medias
    if not evidencias:
        return None
    if len(evidencias) > MAX_EVIDENCIAS_DEPENDENCIA:
        extras = len(evidencias) - MAX_EVIDENCIAS_DEPENDENCIA
        evidencias = evidencias[:MAX_EVIDENCIAS_DEPENDENCIA] + [f"e mais {_plural(extras, 'dependência', 'dependências')}"]
    return Sinal("DEPENDENCIA", "alta" if altas else "media", tuple(evidencias), entre_programas=entre_programas)


# --- Todas as regras ---------------------------------------------------------------------

def avaliar(dados: Dados, hoje: date) -> dict[int, list[Sinal]]:
    """Sinais de risco por Epic avaliado (aberto), na ordem de CATEGORIAS."""
    abertos = sorted((e for e in dados.epics.values() if e.estado not in ("Done", "Removed")), key=lambda e: e.id)
    sinais: dict[int, list[Sinal]] = {}
    for e in abertos:
        c = contexto(e, dados, hoje)
        sinais[e.id] = [s for s in (risco_prazo(c, hoje), risco_capacidade(c), risco_escopo(c, hoje),
                                    risco_qualidade(c), risco_governanca(c)) if s]

    prazo = {eid: s for eid, lista in sinais.items() for s in lista if s.categoria == "PRAZO"}
    predecessores: dict[int, list[Item]] = {}
    for p, s in dados.dependencias:
        predecessores.setdefault(dados.epic_de[s.id], []).append(p)
    for e in abertos:
        if dep := risco_dependencia(e, predecessores.get(e.id, []), dados, prazo, hoje):
            sinais[e.id].append(dep)

    ordem = {c: k for k, c in enumerate(CATEGORIAS)}
    return {eid: sorted(lista, key=lambda s: ordem[s.categoria]) for eid, lista in sinais.items()}
