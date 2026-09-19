# -*- coding: utf-8 -*-
"""Teste de fumaça: sobe a app em memória e exercita o caminho crítico.

Não substitui testes de unidade — verifica que o deploy não subiu quebrado:
banco acessível, login, CSRF, RBAC, troca de senha obrigatória e healthchecks.

    python smoke_test.py            # usa o DB_PATH configurado
    python smoke_test.py meu.db
"""
import os, sys, json, sqlite3, tempfile, shutil, secrets

if len(sys.argv) > 1:
    os.environ["DB_PATH"] = sys.argv[1]

falhas, passou = [], 0


def checar(nome, condicao, detalhe=""):
    global passou
    if condicao:
        passou += 1
        print(f"  ok   {nome}")
    else:
        falhas.append(f"{nome}{' — ' + detalhe if detalhe else ''}")
        print(f"  FALHA {nome}{' — ' + detalhe if detalhe else ''}")


def main():
    # Trabalha sobre uma cópia: o teste cria usuário e sessão, não suja o banco real.
    origem = os.environ.get("DB_PATH") or "cotacoes.db"
    if not os.path.exists(origem):
        print(f"banco não encontrado: {origem}", file=sys.stderr)
        sys.exit(1)
    tmp = os.path.join(tempfile.mkdtemp(), "teste.db")
    shutil.copy(origem, tmp)
    os.environ["DB_PATH"] = tmp
    os.environ.setdefault("AMBIENTE", "desenvolvimento")

    for m in ("config", "auth", "app"):
        sys.modules.pop(m, None)
    import auth, app as appmod

    senha = "Teste-" + secrets.token_urlsafe(12)
    con = sqlite3.connect(tmp)
    con.execute("DELETE FROM usuario WHERE email='smoke@teste.local'")
    con.execute("""INSERT INTO usuario (email,nome,perfil,senha_hash,tenant_id,forcar_troca_senha)
                   VALUES ('smoke@teste.local','Smoke','ALMOXARIFE',?,1,0)""",
                (auth.hash_senha(senha),))
    con.commit(); con.close()

    c = appmod.app.test_client()

    print("\ninfra")
    checar("/healthz responde 200", c.get("/healthz").status_code == 200)
    r = c.get("/readyz")
    checar("/readyz responde 200", r.status_code == 200, r.get_data(as_text=True)[:120])
    pronto = r.get_json() or {}
    checar("banco tem materiais", (pronto.get("materiais") or 0) > 0, str(pronto.get("materiais")))
    checar("migrações registradas", (pronto.get("migracoes") or 0) >= 2, str(pronto.get("migracoes")))
    checar("interface é servida", c.get("/").status_code == 200)

    print("\nautenticação")
    checar("API exige sessão", c.get("/api/nav").status_code == 401)
    checar("senha errada é recusada",
           c.post("/api/login", json={"email": "smoke@teste.local", "senha": "errada"}).status_code == 401)
    r = c.post("/api/login", json={"email": "smoke@teste.local", "senha": senha})
    checar("login válido entra", r.status_code == 200, r.get_data(as_text=True)[:120])
    sessao = r.get_json() or {}
    csrf = sessao.get("csrf")
    checar("cookie de sessão é HttpOnly",
           any("HttpOnly" in h for k, h in r.headers if k == "Set-Cookie"))
    checar("sessão traz permissões", bool(sessao.get("permissoes")))

    print("\nautorização (RBAC no backend)")
    checar("almoxarife entra em /api/nav", c.get("/api/nav").status_code == 200)
    checar("almoxarife recebe 403 em /api/precos",
           c.get("/api/precos").status_code == 403)
    checar("escrita sem CSRF é bloqueada",
           c.post("/api/senha", json={"senha_atual": senha, "senha_nova": "x"}).status_code == 403)

    print("\npolítica de senha")
    r = c.post("/api/senha", json={"senha_atual": senha, "senha_nova": "curta"},
               headers={"X-CSRF": csrf})
    checar("senha curta é recusada", r.status_code == 400, r.get_data(as_text=True)[:120])
    r = c.post("/api/senha", json={"senha_atual": senha, "senha_nova": "admin123"},
               headers={"X-CSRF": csrf})
    checar("senha da lista de fracas é recusada", r.status_code == 400)
    nova = "Nova-" + secrets.token_urlsafe(12)
    r = c.post("/api/senha", json={"senha_atual": senha, "senha_nova": nova},
               headers={"X-CSRF": csrf})
    checar("troca de senha válida funciona", r.status_code == 200, r.get_data(as_text=True)[:120])
    checar("sessão antiga é revogada após a troca", c.get("/api/nav").status_code == 401)
    checar("entra com a senha nova",
           c.post("/api/login", json={"email": "smoke@teste.local", "senha": nova}).status_code == 200)

    print("\ntroca obrigatória no primeiro acesso")
    con = sqlite3.connect(tmp)
    con.execute("UPDATE usuario SET forcar_troca_senha=1 WHERE email='smoke@teste.local'")
    con.commit(); con.close()
    checar("conta com senha pendente recebe 428", c.get("/api/nav").status_code == 428)

    print("\nmulti-tenant (preparação)")
    con = sqlite3.connect(tmp); con.row_factory = sqlite3.Row
    cols = {r["name"] for r in con.execute("PRAGMA table_info(material)")}
    checar("material tem tenant_id", "tenant_id" in cols)
    t = con.execute("SELECT COUNT(*) FROM tenant").fetchone()[0]
    checar("tenant cadastrado", t >= 1, f"{t} tenants")
    orfaos = con.execute("SELECT COUNT(*) FROM material WHERE tenant_id IS NULL").fetchone()[0]
    checar("nenhum material sem tenant", orfaos == 0, f"{orfaos} órfãos")
    con.close()

    print("\nconfiguração")
    import config
    checar("config valida sem erro em desenvolvimento", isinstance(config.validar(), list))
    checar("/api/config não vaza segredo",
           "SMTP_PASS" not in c.get("/api/config").get_data(as_text=True))

    shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)

    print(f"\n{passou} verificações passaram, {len(falhas)} falharam")
    if falhas:
        for f in falhas:
            print(f"  - {f}")
        sys.exit(1)
    print("smoke test ok")


if __name__ == "__main__":
    main()
