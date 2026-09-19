# -*- coding: utf-8 -*-
"""Cria ou reseta os usuários iniciais com senhas aleatórias.

Mudança em relação à Fase 1: as senhas não estão mais escritas no código nem no
README. Cada execução gera uma senha forte, imprime UMA vez no terminal e marca
a conta para troca obrigatória no primeiro acesso.

    python seed_usuarios.py                    # banco padrão, senhas geradas
    python seed_usuarios.py cotacoes.db        # banco específico
    SENHA_ADMIN=... python seed_usuarios.py    # senha do admin vinda do ambiente

Para resetar a senha de uma conta existente:
    python seed_usuarios.py --resetar admin@empresa.com.br
"""
import sqlite3, sys, os, secrets, string
from auth import hash_senha, validar_senha

ALFABETO = string.ascii_letters + string.digits + "!@#$%&*-_=+?"

# Domínio das contas iniciais. Defina ORG_DOMINIO antes de rodar em produção.
DOMINIO = os.environ.get("ORG_DOMINIO", "exemplo.com.br")

USUARIOS = [
    # (usuário, nome, perfil, variável de ambiente opcional com a senha)
    ("comprador",  "Comprador",     "COMPRADOR",  "SENHA_COMPRADOR"),
    ("almoxarife", "Almoxarife",    "ALMOXARIFE", "SENHA_ALMOXARIFE"),
    ("gestor",     "Gestor",        "GESTOR",     "SENHA_GESTOR"),
    ("admin",      "Administrador", "ADMIN",      "SENHA_ADMIN"),
]


def gerar(n=16):
    while True:
        s = "".join(secrets.choice(ALFABETO) for _ in range(n))
        if not validar_senha(s):
            return s


def upsert(con, email, nome, perfil, senha, tenant_id=1):
    con.execute("""INSERT INTO usuario (email,nome,perfil,senha_hash,tenant_id,forcar_troca_senha)
                   VALUES (?,?,?,?,?,1)
                   ON CONFLICT(email) DO UPDATE SET
                     nome=excluded.nome, perfil=excluded.perfil,
                     senha_hash=excluded.senha_hash, forcar_troca_senha=1""",
                (email, nome, perfil, hash_senha(senha), tenant_id))


def main():
    args = [a for a in sys.argv[1:]]
    resetar = None
    if "--resetar" in args:
        i = args.index("--resetar")
        resetar = args[i + 1]
        del args[i:i + 2]

    db = args[0] if args else os.environ.get("DB_PATH", "cotacoes.db")
    if not os.path.exists(db):
        print(f"banco não encontrado: {db}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    geradas = []

    if resetar:
        u = con.execute("SELECT id, nome FROM usuario WHERE lower(email)=lower(?)", (resetar,)).fetchone()
        if not u:
            print(f"usuário não encontrado: {resetar}", file=sys.stderr)
            sys.exit(1)
        senha = os.environ.get("SENHA_NOVA") or gerar()
        con.execute("""UPDATE usuario SET senha_hash=?, forcar_troca_senha=1 WHERE id=?""",
                    (hash_senha(senha), u["id"]))
        con.execute("UPDATE sessao SET revogada=1 WHERE usuario_id=?", (u["id"],))
        geradas.append((resetar, senha))
    else:
        for usuario, nome, perfil, var in USUARIOS:
            email = f"{usuario}@{DOMINIO}"
            senha = os.environ.get(var) or gerar()
            motivo = validar_senha(senha, email)
            if motivo:
                print(f"{var}: {motivo}", file=sys.stderr)
                sys.exit(1)
            upsert(con, email, nome, perfil, senha)
            geradas.append((email, senha))

    con.commit()

    print("\nSenhas geradas — anote agora, não são exibidas de novo:\n")
    largura = max(len(e) for e, _ in geradas)
    for email, senha in geradas:
        print(f"  {email:<{largura}}  {senha}")
    print("\nTodas exigem troca no primeiro acesso.\n")

    print("Contas no banco:")
    for r in con.execute("SELECT email, nome, perfil, ativo FROM usuario ORDER BY perfil, nome"):
        estado = "ativo" if r["ativo"] else "inativo"
        print(f"  {r['email']:<{largura}}  {r['perfil']:<11} {estado}")


if __name__ == "__main__":
    main()
