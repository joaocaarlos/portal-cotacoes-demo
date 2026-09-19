# -*- coding: utf-8 -*-
"""Configuração por ambiente. Nada de segredo fica no código — tudo vem de
variável de ambiente, com padrões seguros para desenvolvimento.

Em produção o processo se recusa a subir se um segredo obrigatório estiver
faltando (ver `validar()`), porque falhar no boot é melhor que rodar inseguro.
"""
import os, sys, secrets


def _bool(nome, padrao="0"):
    return os.environ.get(nome, padrao).strip().lower() in ("1", "true", "yes", "sim", "on")


def _int(nome, padrao):
    try:
        return int(os.environ.get(nome, padrao))
    except ValueError:
        return int(padrao)


AQUI = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ambiente
AMBIENTE = os.environ.get("AMBIENTE", "desenvolvimento").strip().lower()
PRODUCAO = AMBIENTE in ("producao", "produção", "production", "prod")

# ---------------------------------------------------------------- dados
DB_PATH = os.environ.get("DB_PATH", os.path.join(AQUI, "cotacoes.db"))

# ---------------------------------------------------------------- sessão
SESSAO_HORAS = _int("SESSAO_HORAS", 8)
# Cookie Secure exige HTTPS. Em produção é ligado por padrão; atrás de um proxy
# que termina TLS, mantenha 1 e configure o proxy para enviar X-Forwarded-Proto.
COOKIE_SECURE = _bool("COOKIE_SECURE", "1" if PRODUCAO else "0")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")
SENHA_MIN = _int("SENHA_MIN", 10)

# ---------------------------------------------------------------- e-mail
DRY_RUN = _bool("DRY_RUN", "0" if PRODUCAO else "1")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "")

# ---------------------------------------------------------------- limites
LIMITE_LOGIN = _int("LIMITE_LOGIN", 15)
LIMITE_ENVIO = _int("LIMITE_ENVIO", 10)

# ---------------------------------------------------------------- multi-tenant
# Instalação corporativa roda com um tenant fixo. Quando MULTI_TENANT=1, o
# tenant passa a vir do usuário autenticado e o filtro é aplicado nas consultas.
MULTI_TENANT = _bool("MULTI_TENANT", "0")
TENANT_PADRAO = _int("TENANT_PADRAO", 1)

# ---------------------------------------------------------------- Entra ID
ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "")

# ---------------------------------------------------------------- identidade
# Nome exibido na tela de login, no menu e na assinatura dos e-mails de cotação.
# Antes estava escrito no código em três lugares; agora é configuração.
ORG_NOME = os.environ.get("ORG_NOME", "Portal de Cotações")
ORG_SUBTITULO = os.environ.get("ORG_SUBTITULO", "Compras e Almoxarifado")

# ---------------------------------------------------------------- app
PORT = _int("PORT", 8000)
VERSAO = os.environ.get("VERSAO", "1.0.0")

# Segredo do Flask. Em desenvolvimento é gerado a cada boot (derruba sessões de
# processos anteriores, o que é o comportamento desejado localmente).
APP_SECRET = os.environ.get("APP_SECRET") or ("" if PRODUCAO else secrets.token_hex(32))


OBRIGATORIAS_EM_PRODUCAO = [
    ("APP_SECRET", APP_SECRET, "segredo de assinatura do Flask (gere com: python -c \"import secrets;print(secrets.token_hex(32))\")"),
]


def validar():
    """Retorna a lista de problemas de configuração. Vazia = pronto para subir."""
    problemas = []
    for nome, valor, ajuda in (OBRIGATORIAS_EM_PRODUCAO if PRODUCAO else []):
        if not valor:
            problemas.append(f"{nome} não definida — {ajuda}")

    if PRODUCAO and not DRY_RUN and not SMTP_HOST:
        problemas.append("DRY_RUN=0 (envio real) mas SMTP_HOST está vazio — "
                         "defina SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/MAIL_FROM ou volte para DRY_RUN=1")

    if PRODUCAO and not COOKIE_SECURE:
        problemas.append("COOKIE_SECURE=0 em produção — o cookie de sessão trafegaria em HTTP puro")

    if not os.path.exists(DB_PATH):
        problemas.append(f"banco não encontrado em DB_PATH={DB_PATH}")

    return problemas


def exigir_config_valida():
    problemas = validar()
    if problemas:
        print("Configuração inválida:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(2)


def resumo():
    """Diagnóstico seguro — nunca imprime segredo."""
    return {
        "ambiente": AMBIENTE,
        "org_nome": ORG_NOME,
        "org_subtitulo": ORG_SUBTITULO,
        "versao": VERSAO,
        "banco": os.path.basename(DB_PATH),
        "dry_run": DRY_RUN,
        "multi_tenant": MULTI_TENANT,
        "cookie_secure": COOKIE_SECURE,
        "smtp_configurado": bool(SMTP_HOST),
        "entra_id": bool(ENTRA_TENANT_ID),
    }
