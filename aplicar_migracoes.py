# -*- coding: utf-8 -*-
"""Aplica as migrações .sql em ordem, uma única vez cada.

Antes deste arquivo, `reconstruir.sh` rodava migracao_01.sql direto: rodar duas
vezes derrubava a tabela `usuario`. Agora cada migração fica registrada em
`schema_migracao` e é ignorada se já aplicada — o deploy pode chamar isto sempre.

    python aplicar_migracoes.py [caminho/do/banco.db]
"""
import sys, os, re, sqlite3, glob, hashlib

DB = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DB_PATH", "cotacoes.db")
AQUI = os.path.dirname(os.path.abspath(__file__))


def migracoes():
    return sorted(glob.glob(os.path.join(AQUI, "migracao_*.sql")))


def aplicar(con):
    con.execute("""CREATE TABLE IF NOT EXISTS schema_migracao (
                     arquivo    TEXT PRIMARY KEY,
                     sha256     TEXT NOT NULL,
                     aplicada_em TEXT DEFAULT (datetime('now')))""")
    con.commit()
    ja = {r[0]: r[1] for r in con.execute("SELECT arquivo, sha256 FROM schema_migracao")}

    for caminho in migracoes():
        nome = os.path.basename(caminho)
        sql = open(caminho, encoding="utf-8").read()
        digest = hashlib.sha256(sql.encode()).hexdigest()

        if nome in ja:
            if ja[nome] != digest:
                print(f"  ! {nome} já aplicada, mas o arquivo mudou desde então "
                      f"(crie uma migração nova em vez de editar esta)")
            else:
                print(f"  = {nome} (já aplicada)")
            continue

        # Banco que já veio com a migração aplicada (ex.: o cotacoes.db distribuído):
        # o marcador `-- @ja-aplicada-se:` diz como detectar isso sem reexecutar.
        m = re.search(r"--\s*@ja-aplicada-se:\s*(.+)", sql)
        if m:
            try:
                if con.execute(m.group(1).strip()).fetchone()[0]:
                    con.execute("INSERT INTO schema_migracao (arquivo, sha256) VALUES (?,?)",
                                (nome, digest))
                    con.commit()
                    print(f"  = {nome} (efeito já presente no banco, registrada sem reexecutar)")
                    continue
            except sqlite3.Error:
                pass    # detector não pôde rodar: segue para a aplicação normal

        try:
            con.executescript(sql)
            con.execute("INSERT INTO schema_migracao (arquivo, sha256) VALUES (?,?)", (nome, digest))
            con.commit()
            print(f"  + {nome} aplicada")
        except sqlite3.OperationalError as e:
            con.rollback()
            print(f"  x {nome} falhou: {e}", file=sys.stderr)
            raise


def main():
    if not os.path.exists(DB):
        print(f"banco não encontrado: {DB}", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(DB)
    print(f"migrando {DB}")
    aplicar(con)
    con.execute("PRAGMA journal_mode=WAL")      # leitura concorrente sob gunicorn
    con.execute("PRAGMA synchronous=NORMAL")
    con.close()
    print("ok")


if __name__ == "__main__":
    main()
