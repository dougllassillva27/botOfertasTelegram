"""
Destinatários extras do WhatsApp — números que recebem ofertas em DM.

Diferença em relação às flags `alertas_whatsapp`: aquelas decidem *se* a
oferta vai pro WhatsApp (sempre pro grupo Sol, com menção no dono). Aqui cada
destino tem um recorte próprio de keywords — o amigo que só pediu desconto de
café não é obrigado a receber alerta de bug de notebook.

Regras que o módulo garante:

- O JID é sempre normalizado (`<ddi><ddd><numero>@s.whatsapp.net`) antes de
  ser gravado. A ponte aceita qualquer string como `chatId` e responde
  `success: true` mesmo para JID inválido — um número mal formatado aqui
  viraria mensagem que nunca chega, sem erro em lugar nenhum.
- Destino só aceita conversa individual. Grupo tem fluxo próprio (o grupo Sol)
  e `@lid` não serve para iniciar conversa.
- Keyword de destino precisa existir em `alertas`, senão seria um filtro que
  nunca dispara.
"""

import logging
import re

from app.storage import save_data

logger = logging.getLogger(__name__)

KEY = "whatsapp_destinos"
JID_DOMAIN = "@s.whatsapp.net"
DDI_BR = "55"

# Número nacional (DDD + 8 ou 9 dígitos) e internacional (12 a 15 dígitos).
LEN_MIN_INTERNACIONAL = 12
LEN_MAX_INTERNACIONAL = 15


def _only_digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _warn_short_subscriber(digitos):
    """Avisa (só no log) quando o número tem 8 dígitos após o DDD.

    Completar o nono dígito automaticamente parece razoável e é errado na
    prática: em 11/11/2026 o destinatário real era `555194694630` (12 dígitos,
    sem o 9) e o "conserto" gerou `5551994694630` — JID que a ponte aceita com
    `success: true` e o WhatsApp descarta em silêncio. Quem conhece o número é
    quem cadastra, não o formato.
    """
    if not digitos.startswith(DDI_BR) or len(digitos) != 12:
        return
    assinante = digitos[4:]  # depois de DDI (2) + DDD (2)
    if assinante[0] in "6789":
        logger.info(
            f"Número com 8 dígitos após o DDD: {digitos}. Se não entregar, "
            f"confira se falta o nono dígito (ex.: {digitos[:4]}9{assinante})."
        )


def normalize_jid(raw):
    """Converte número digitado de qualquer jeito em JID utilizável.

    Aceita `5551999999999`, `+55 (51) 99999-9999` e o próprio JID. Devolve
    string vazia quando o número não tem cara de telefone ou quando o alvo é
    grupo/conta LID (nenhum dos dois serve para DM).
    """
    texto = str(raw or "").strip()
    if not texto:
        return ""

    if "@" in texto:
        local, _, dominio = texto.partition("@")
        dominio = dominio.lower()
        if dominio and f"@{dominio}" != JID_DOMAIN:
            return ""  # g.us, lid, broadcast, status@broadcast...
        digitos = _only_digits(local)
    else:
        digitos = _only_digits(texto)

    if not digitos:
        return ""

    # Número nacional sem DDI: 10 dígitos (fixo) ou 11 (celular com o 9).
    if len(digitos) in (10, 11):
        digitos = DDI_BR + digitos

    _warn_short_subscriber(digitos)

    if not LEN_MIN_INTERNACIONAL <= len(digitos) <= LEN_MAX_INTERNACIONAL:
        return ""

    return f"{digitos}{JID_DOMAIN}"


def _normalize_keyword(keyword):
    return str(keyword or "").lower().strip()


def load_destinos(state):
    """Lista de destinos válidos, tolerante a estado antigo ou corrompido."""
    bruto = state.setdefault(KEY, [])
    if not isinstance(bruto, list):
        return []

    destinos = []
    for item in bruto:
        if not isinstance(item, dict):
            continue
        jid = normalize_jid(item.get("jid"))
        if not jid:
            logger.warning(f"Destino WhatsApp ignorado (JID inválido): {item!r}")
            continue
        keywords = [
            _normalize_keyword(k)
            for k in item.get("keywords") or []
            if _normalize_keyword(k)
        ]
        destinos.append(
            {
                "nome": str(item.get("nome") or jid.split("@")[0]).strip(),
                "jid": jid,
                "keywords": keywords,
            }
        )
    return destinos


def _raw(state):
    """Lista bruta do estado — é nela que as mutações acontecem.

    `load_destinos` devolve cópias normalizadas (leitura), então escrever nelas
    não muda o estado. Toda função de escrita mexe aqui e normaliza no `_save`.
    """
    bruto = state.setdefault(KEY, [])
    if not isinstance(bruto, list):
        bruto = []
        state[KEY] = bruto
    return bruto


def _save(state):
    state[KEY] = load_destinos(state)
    save_data(state)


def _find(state, nome):
    alvo = _normalize_keyword(nome)
    for destino in load_destinos(state):
        if destino["nome"].lower() == alvo:
            return destino
    return None


def add_destino(state, nome, numero, keywords=None):
    """Cadastra um destino em DM. Retorna (ok, mensagem)."""
    nome = str(nome or "").strip()
    if not nome or " " in nome:
        return False, "⚠️ Use um nome sem espaços: `/wa add Amigo 5551999999999`"

    jid = normalize_jid(numero)
    if not jid:
        return False, (
            f"⚠️ Número inválido: `{numero}`\n\n"
            "📱 Use DDI + DDD + número: `/wa add Amigo 5551999999999`"
        )

    if any(d["jid"] == jid for d in load_destinos(state)):
        dono = next(d["nome"] for d in load_destinos(state) if d["jid"] == jid)
        return False, f"⚠️ Esse número já está cadastrado como `{dono}`."

    if _find(state, nome):
        return False, f"⚠️ Já existe um destino chamado `{nome}`."

    aceitas, recusadas = _filter_active_keywords(state, keywords)
    _raw(state).append({"nome": nome, "jid": jid, "keywords": aceitas})
    save_data(state)

    msg = f"✅ Destino `{nome}` cadastrado ({jid.split('@')[0]})."
    if aceitas:
        msg += "\n🔔 Recebe as ofertas de: " + ", ".join(f"`{k}`" for k in aceitas)
    else:
        msg += (
            "\n\n⚠️ Sem keywords ele **não recebe nada ainda**."
            f"\n🔔 Defina: `/wa kw {nome} orfeu`"
        )
    if recusadas:
        msg += "\n\n⚠️ Ignoradas (não são alertas ativos): " + ", ".join(
            f"`{k}`" for k in recusadas
        )
    return True, msg


def remove_destino(state, nome):
    """Remove um destino. Retorna (ok, mensagem)."""
    destino = _find(state, nome)
    if not destino:
        return False, f"⚠️ Destino `{nome}` não encontrado.\n\n📋 Veja a lista: `/wa`"

    alvo = destino["nome"].lower()
    restantes = [
        item
        for item in _raw(state)
        if not (isinstance(item, dict) and str(item.get("nome") or "").lower() == alvo)
    ]
    state[KEY] = restantes
    _save(state)
    return True, f"🗑️ Destino `{destino['nome']}` removido — não recebe mais ofertas."


def set_keywords(state, nome, keywords):
    """Substitui as keywords de um destino. Lista vazia = não recebe nada."""
    destino = _find(state, nome)
    if not destino:
        return False, f"⚠️ Destino `{nome}` não encontrado.\n\n📋 Veja a lista: `/wa`"

    aceitas, recusadas = _filter_active_keywords(state, keywords)
    alvo = destino["nome"].lower()
    for item in _raw(state):
        if isinstance(item, dict) and str(item.get("nome") or "").lower() == alvo:
            item["keywords"] = aceitas
    save_data(state)

    if not aceitas:
        msg = (
            f"🔕 `{destino['nome']}` **não recebe mais nada**.\n\n"
            f"🔔 Pra religar: `/wa kw {destino['nome']} orfeu, bug`"
        )
    else:
        msg = f"✅ `{destino['nome']}` **agora recebe** " + ", ".join(
            f"`{k}`" for k in aceitas
        )
    if recusadas:
        msg += "\n\n⚠️ Ignoradas (não são alertas ativos): " + ", ".join(
            f"`{k}`" for k in recusadas
        )
    return True, msg


def _filter_active_keywords(state, keywords):
    """Separa keywords válidas das que não são alertas ativos."""
    ativos = state.get("alertas", [])
    aceitas, recusadas = [], []
    for raw in keywords or []:
        kw = _normalize_keyword(raw)
        if not kw:
            continue
        if kw in ativos and kw not in aceitas:
            aceitas.append(kw)
        elif kw not in ativos and kw not in recusadas:
            recusadas.append(kw)
    return aceitas, recusadas


def destinos_for(state, matched_keywords):
    """Destinos que devem receber uma oferta que bateu essas keywords.

    Uma oferta pode bater várias keywords: o destino entra uma vez só, mesmo
    que duas delas estejam no recorte dele.
    """
    alvo = {_normalize_keyword(k) for k in matched_keywords or [] if k}
    if not alvo:
        return []
    return [d for d in load_destinos(state) if alvo.intersection(d["keywords"])]


def list_destinos(state):
    """Texto da lista de destinos para o comando `/wa`."""
    destinos = load_destinos(state)
    if not destinos:
        return (
            "📭 **Nenhum destino extra no WhatsApp.**\n\n"
            "➕ Cadastre: `/wa add Amigo 5551999999999`\n"
            "🔔 Depois escolha o que ele recebe: `/wa kw Amigo orfeu`"
        )

    linhas = []
    for d in destinos:
        keywords = (
            ", ".join(f"`{k}`" for k in d["keywords"]) or "_nenhuma (não recebe)_"
        )
        linhas.append(f"• **{d['nome']}** — {d['jid'].split('@')[0]}\n  🔔 {keywords}")
    return (
        f"📲 **Destinos extras ({len(destinos)})**\n\n"
        + "\n".join(linhas)
        + "\n\n⚙️ `/wa add Nome numero` · `/wa kw Nome orfeu, bug` · `/wa rm Nome`"
    )
