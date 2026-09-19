# -*- coding: utf-8 -*-
"""Autenticação, perfis e permissões. O ponto de entrada do Entra ID (OIDC)
está isolado em `login_entra()` — o TI pluga ali sem mexer no resto."""
import os, re, hashlib, secrets, sqlite3, datetime, functools
from flask import request, jsonify, g
import config

SESSAO_HORAS = config.SESSAO_HORAS

# perfil -> permissões. Aplicadas no backend, não só escondendo botão.
PERMISSOES = {
    "ALMOXARIFE": {"material.ver", "estoque.ver", "consumo.ver", "sap.ver", "pendencia.ver"},
    "COMPRADOR":  {"material.ver", "material.editar", "estoque.ver", "consumo.ver", "preco.ver",
                   "sap.ver", "fornecedor.ver", "cotacao.ver", "cotacao.criar", "cotacao.enviar",
                   "pendencia.ver", "pendencia.resolver", "vinculo.confirmar"},
    "GESTOR":     {"material.ver", "estoque.ver", "consumo.ver", "preco.ver", "sap.ver",
                   "fornecedor.ver", "cotacao.ver", "cotacao.aprovar", "pendencia.ver",
                   "relatorio.ver", "auditoria.ver", "dashboard.gerencial"},
    "ADMIN":      {"*"},
    "SOLICITANTE": {"material.ver", "estoque.ver", "cotacao.ver"},
}

def hash_senha(senha, salt=None):
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2${salt}${h}"

def confere_senha(senha, guardado):
    try:
        _, salt, h = (guardado or "").split("$")
    except ValueError:
        return False
    return secrets.compare_digest(hash_senha(senha, salt).split("$")[2], h)

def pode(perfil, permissao):
    p = PERMISSOES.get(perfil or "", set())
    return "*" in p or permissao in p

def usuario_da_sessao(con):
    token = request.cookies.get("sessao")
    if not token: return None
    r = con.execute("""SELECT u.id, u.nome, u.email, u.perfil, u.tenant_id,
                              u.forcar_troca_senha, s.csrf, s.expira_em
                       FROM sessao s JOIN usuario u ON u.id = s.usuario_id
                       WHERE s.token=? AND s.revogada=0 AND u.ativo=1""", (token,)).fetchone()
    if not r: return None
    if r["expira_em"] < datetime.datetime.now().isoformat(timespec="seconds"):
        con.execute("UPDATE sessao SET revogada=1 WHERE token=?", (token,)); con.commit()
        return None
    return dict(r) | {"token": token}

def criar_sessao(con, usuario_id, ip, tenant_id=None):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    exp = (datetime.datetime.now() + datetime.timedelta(hours=SESSAO_HORAS)).isoformat(timespec="seconds")
    if tenant_id is None:
        r = con.execute("SELECT tenant_id FROM usuario WHERE id=?", (usuario_id,)).fetchone()
        tenant_id = (r["tenant_id"] if r else None) or config.TENANT_PADRAO
    con.execute("INSERT INTO sessao (token,usuario_id,csrf,ip,expira_em,tenant_id) VALUES (?,?,?,?,?,?)",
                (token, usuario_id, csrf, ip, exp, tenant_id))
    con.execute("UPDATE usuario SET ultimo_acesso=datetime('now') WHERE id=?", (usuario_id,))
    con.commit()
    return token, csrf

def exige(*permissoes):
    """Decorator: exige login, valida CSRF em escrita e checa permissão."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not g.get("usuario"):
                return jsonify({"erro": "Sessão expirada. Faça login novamente."}), 401
            if g.usuario.get("forcar_troca_senha"):
                return jsonify({"erro": "Defina uma nova senha antes de usar o portal.",
                                "trocar_senha": True}), 428
            if request.method in ("POST", "PUT", "DELETE"):
                if request.headers.get("X-CSRF") != g.usuario["csrf"]:
                    return jsonify({"erro": "Falha na validação CSRF."}), 403
            for p in permissoes:
                if not pode(g.usuario["perfil"], p):
                    return jsonify({"erro": f"Seu perfil ({g.usuario['perfil'].title()}) "
                                            f"não tem permissão para esta ação."}), 403
            return fn(*a, **kw)
        return wrapper
    return deco

def login_entra(con, id_token_claims):
    """Ponto de integração com o Entra ID: recebe os claims validados do OIDC e
    devolve o usuário local. Enquanto o TI não habilita, ninguém chama isto."""
    oid, email = id_token_claims.get("oid"), (id_token_claims.get("preferred_username") or "").lower()
    r = con.execute("SELECT id FROM usuario WHERE entra_oid=? OR email=?", (oid, email)).fetchone()
    if not r:
        return None            # provisionamento automático é decisão do TI
    con.execute("UPDATE usuario SET entra_oid=COALESCE(entra_oid,?) WHERE id=?", (oid, r["id"]))
    con.commit()
    return r["id"]


# --------------------------------------------------------------- política de senha
FRACAS = {"123456", "senha", "password", "admin", "mudar123", "portal", "cotacao",
          "comprador123", "almox123", "gestor123", "admin123", "12345678"}


def validar_senha(senha, email=""):
    """Devolve o motivo da recusa, ou None se a senha serve.

    Regras conscientemente simples: comprimento faz mais pelo risco real do que
    exigir símbolo, e a lista de fracas barra justamente as senhas de teste que
    vieram documentadas no README da Fase 1.
    """
    senha = senha or ""
    if len(senha) < config.SENHA_MIN:
        return f"A senha precisa de pelo menos {config.SENHA_MIN} caracteres."
    if senha.lower() in FRACAS:
        return "Esta senha é previsível demais. Escolha outra."
    if email and senha.lower() == email.split("@")[0].lower():
        return "A senha não pode ser igual ao seu usuário."
    if re.fullmatch(r"(.)\1+", senha):
        return "A senha não pode ser um único caractere repetido."
    return None


def trocar_senha(con, usuario_id, senha_nova):
    con.execute("""UPDATE usuario SET senha_hash=?, forcar_troca_senha=0,
                                      senha_trocada_em=datetime('now') WHERE id=?""",
                (hash_senha(senha_nova), usuario_id))
    con.execute("UPDATE sessao SET revogada=1 WHERE usuario_id=?", (usuario_id,))
    con.commit()


# --------------------------------------------------------------- escopo de tenant
def tenant_atual():
    """Tenant em vigor no request.

    Instalação corporativa (MULTI_TENANT=0): sempre TENANT_PADRAO.
    Quando MULTI_TENANT=1: o tenant do usuário autenticado — nunca um valor vindo
    do cliente, justamente para que trocar um parâmetro na URL não vaze dados.
    """
    if not config.MULTI_TENANT:
        return config.TENANT_PADRAO
    u = g.get("usuario") or {}
    return u.get("tenant_id") or config.TENANT_PADRAO


def escopo(sql, alias=""):
    """Acrescenta o filtro de tenant a um SELECT quando o modo multi-tenant está ligado.

    Este é o ponto único onde o isolamento será aplicado. Hoje devolve o SQL
    intacto (uma empresa, um banco); ligar MULTI_TENANT passa a exigir que as
    consultas de negócio usem este helper. Ver MULTI_TENANT.md.
    """
    if not config.MULTI_TENANT:
        return sql
    col = f"{alias}.tenant_id" if alias else "tenant_id"
    juncao = "AND" if re.search(r"\bWHERE\b", sql, re.I) else "WHERE"
    return f"{sql} {juncao} {col} = :tenant_id"
