# -*- coding: utf-8 -*-
"""Gera um banco de demonstração com dados sintéticos.

Nenhuma informação real de empresa, fornecedor ou preço. Os números são
sorteados, mas com distribuições que fazem as telas mostrarem o que existe de
verdade no produto: curva ABC, materiais em ruptura, divergência de preço,
materiais sem fornecedor e casos de escala inconsistente.

    python gerar_demo.py                 # cria demo.db
    python gerar_demo.py meu_demo.db     # outro caminho
    SEMENTE=7 python gerar_demo.py       # reproduzível

Depois chama metricas.py, que calcula a camada de inteligência.
"""
import os, sys, random, sqlite3, datetime, subprocess, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "demo.db")
rnd = random.Random(int(os.environ.get("SEMENTE", "20260918")))

HOJE = datetime.date(2026, 9, 18)
N_FORNECEDORES = 42
N_MATERIAIS = 480
MESES = 24

EMPRESA = "Industria Demonstracao S.A."
DOMINIO = "exemplo.com.br"

# ---------------------------------------------------------------- vocabulário
CATEGORIAS = {
    "Rolamentos":    (["Rolamento rigido de esferas", "Rolamento de rolos conicos",
                       "Rolamento autocompensador", "Mancal de rolamento"],
                      ["6204 ZZ", "6205 2RS", "32008 X", "22210 EK", "UCP 205"]),
    "Correias":      (["Correia dentada", "Correia em V", "Correia plana", "Polia tensora"],
                      ["A-45", "B-60", "HTD 8M", "SPZ 1200", "XPA 1400"]),
    "Fixadores":     (["Parafuso sextavado", "Porca autotravante", "Arruela lisa", "Prisioneiro"],
                      ["M8x40", "M10x60", "M12x80", "M6x25", "M16x100"]),
    "Lubrificantes": (["Graxa de litio", "Oleo hidraulico", "Oleo de engrenagem", "Desmoldante"],
                      ["EP-2", "ISO 68", "ISO 220", "AW 46", "NLGI 2"]),
    "Ferramentas":   (["Broca helicoidal", "Fresa de topo", "Inserto de torneamento", "Macho de roscar"],
                      ["HSS 8mm", "MD 12mm", "CNMG 120408", "M10", "6mm 4 cortes"]),
    "Eletrica":      (["Contator tripolar", "Disjuntor motor", "Rele termico", "Sensor indutivo"],
                      ["25A 220V", "3RV 4-6A", "NPN M12", "IP67 24VDC", "63A"]),
    "Pneumatica":    (["Cilindro pneumatico", "Valvula solenoide", "Regulador de pressao", "Engate rapido"],
                      ["32x100", "5/2 vias", "1/4 BSP", "50x200", "1/2 NPT"]),
    "Filtros":       (["Filtro de ar", "Filtro hidraulico", "Elemento filtrante", "Filtro coalescente"],
                      ["10 um", "25 um", "G4", "HEPA H13", "5 um"]),
    "Vedacao":       (["Anel O-ring", "Retentor de eixo", "Junta de vedacao", "Gaxeta"],
                      ["NBR 2x20", "VITON 3x30", "35x52x7", "TC 25x40x7"]),
    "EPI":           (["Luva de protecao", "Oculos de seguranca", "Protetor auricular", "Bota de seguranca"],
                      ["CA 12345", "Tam. G", "Tam. 42", "Plug 20dB"]),
}
CAT_NOMES = list(CATEGORIAS)

RAZOES = ["Aurora", "Bandeirante", "Cristal", "Delta Sul", "Equatorial", "Ferrovia",
          "Guarani", "Horizonte", "Ipanema", "Jacaranda", "Kaiser", "Litoral",
          "Meridiano", "Nova Era", "Orion", "Patamar", "Quartzo", "Redentor",
          "Serrano", "Tucano", "Uirapuru", "Vanguarda", "Xingu", "Zenite"]
SUFIXOS = ["Comercio Ltda", "Industria Ltda", "Distribuidora S.A.", "Suprimentos Ltda",
           "Componentes Ltda", "Equipamentos Ltda"]
CIDADES = [("Campinas", "SP"), ("Joinville", "SC"), ("Caxias do Sul", "RS"),
           ("Betim", "MG"), ("Curitiba", "PR"), ("Sao Bernardo do Campo", "SP"),
           ("Sorocaba", "SP"), ("Cariacica", "ES"), ("Manaus", "AM")]
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fabio", "Gisele", "Heitor",
         "Iris", "Jonas", "Karina", "Lucas", "Marina", "Nelson", "Olivia", "Paulo"]
SOBRENOMES = ["Almeida", "Barros", "Cardoso", "Dias", "Esteves", "Farias",
              "Gomes", "Henrique", "Iglesias", "Junqueira", "Lopes", "Moura"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def mes_iso(delta):
    a, m = HOJE.year, HOJE.month - delta
    while m <= 0:
        m += 12
        a -= 1
    return f"{a:04d}-{m:02d}"


def data_iso(dias_atras):
    return (HOJE - datetime.timedelta(days=dias_atras)).isoformat()


# ---------------------------------------------------------------- construção
def criar_banco():
    for sufixo in ("", "-wal", "-shm"):
        try:
            os.remove(DESTINO + sufixo)
        except OSError:
            pass

    con = sqlite3.connect(DESTINO)
    con.executescript(open(os.path.join(AQUI, "schema.sql"), encoding="utf-8").read())
    con.commit()
    return con


def povoar(con):
    cur = con.cursor()

    # ---- categorias
    cat_id = {}
    for i, nome in enumerate(CAT_NOMES, 1):
        cur.execute("INSERT INTO categoria (id,nome,origem) VALUES (?,?,'CLASSIFICACAO')", (i, nome))
        cat_id[nome] = i

    # ---- fornecedores + contatos
    fornecedores = []
    usados = set()
    for i in range(1, N_FORNECEDORES + 1):
        while True:
            razao = f"{rnd.choice(RAZOES)} {rnd.choice(SUFIXOS)}"
            if razao not in usados:
                usados.add(razao)
                break
        cidade, uf = rnd.choice(CIDADES)
        lead = rnd.choice([7, 10, 15, 20, 30, 45, 60])
        cnpj = (f"{rnd.randint(10,99)}.{rnd.randint(100,999)}.{rnd.randint(100,999)}"
                f"/0001-{rnd.randint(10,99)}")
        cur.execute("""INSERT INTO fornecedor (id,codigo_sap,razao_social,nome_norm,nome_fantasia,
                         cnpj,tipo,status,lead_time_dias,cidade,uf,telefone,condicao_pagamento,
                         origem_dados)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'DEMO')""",
                    (i, f"F{100000 + i}", razao, norm(razao), razao.split()[0], cnpj,
                     rnd.choice(["DIRETO", "INDIRETO", "AMBOS"]),
                     rnd.choices(["ATIVO", "HOMOLOGADO", "EM_AVALIACAO", "BLOQUEADO"],
                                 weights=[70, 18, 9, 3])[0],
                     lead, cidade, uf,
                     f"({rnd.randint(11,99)}) {rnd.randint(3000,9999)}-{rnd.randint(1000,9999)}",
                     rnd.choice(["28 DDL", "30/60 DDL", "A vista", "45 DDL"])))

        slug = norm(razao).split()[0].lower()
        for area in rnd.sample(["COMERCIAL", "QUALIDADE", "LOGISTICA"], rnd.randint(1, 2)):
            pessoa = f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)}"
            cur.execute("""INSERT INTO contato (fornecedor_id,area,nome,telefone,email,principal,
                             origem_dados)
                           VALUES (?,?,?,?,?,?,'DEMO')""",
                        (i, area, pessoa,
                         f"({rnd.randint(11,99)}) 9{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}",
                         f"{area.lower()}@{slug}.{DOMINIO}", 1 if area == "COMERCIAL" else 0))

        for c in rnd.sample(CAT_NOMES, rnd.randint(1, 3)):
            cur.execute("INSERT OR IGNORE INTO fornecedor_categoria (fornecedor_id,categoria_id,origem) "
                        "VALUES (?,?,'DEMO')", (i, cat_id[c]))
            cur.execute("INSERT OR IGNORE INTO categoria_email (categoria_id,email,fornecedor_id,ativo) "
                        "VALUES (?,?,?,1)", (cat_id[c], f"comercial@{slug}.{DOMINIO}", i))
        fornecedores.append((i, razao, lead))

    # ---- materiais
    materiais = []
    for n in range(1, N_MATERIAIS + 1):
        cat = rnd.choice(CAT_NOMES)
        familia, medidas = CATEGORIAS[cat]
        descricao = f"{rnd.choice(familia)} {rnd.choice(medidas)}"
        pn = f"DM-{n:05d}"

        # 12% sem fornecedor no cadastro: alimenta a tela de vínculo pendente
        tem_forn = rnd.random() > 0.12
        forn = rnd.choice(fornecedores) if tem_forn else None
        lead = forn[2] if forn else rnd.choice([15, 30, 45])

        consumo_mes = round(rnd.choice([0, 0, 1, 3, 8, 15, 40, 120]) * rnd.uniform(0.6, 1.4), 2)
        preco_base = round(rnd.choice([2.5, 8.9, 24.0, 75.5, 180.0, 640.0, 1850.0]) *
                           rnd.uniform(0.7, 1.3), 4)

        # 8% com unidade de preço 1.000 no mestre: reproduz a escala inconsistente
        escala_mil = rnd.random() < 0.08
        preco_mestre = round(preco_base * (1000 if escala_mil else rnd.uniform(0.85, 1.25)), 4)

        est_min = round(consumo_mes * rnd.uniform(0.5, 1.5), 2)
        est_max = round(max(est_min * rnd.uniform(2.0, 4.0), 1), 2)
        if rnd.random() < 0.15:
            estoque = round(est_min * rnd.uniform(0.0, 0.6), 2)      # ruptura
        elif rnd.random() < 0.10:
            estoque = round(est_max * rnd.uniform(1.6, 3.0), 2)      # excesso
        else:
            estoque = round(rnd.uniform(est_min, est_max), 2)

        confianca = round(rnd.uniform(0.15, 0.95), 2)
        cur.execute("""INSERT INTO material (pn,descricao,tipo,umb,area,tipo_material,
                         grupo_mercadorias,lead_time_dias,estoque_min,estoque_med,estoque_max,
                         consumo_med_mes,estoque_atual,preco_unitario,moeda,preco_atualizado_em,
                         fornecedor_texto,fornecedor_id,categoria_id,categoria_confianca,
                         categoria_origem,origem_dados)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'BRL',?,?,?,?,?,?,'DEMO BASE')""",
                    (pn, descricao, rnd.choice(["MRO", "PRODUTIVO", "CONSUMO"]),
                     rnd.choice(["UN", "PC", "KG", "L", "M"]),
                     rnd.choice(["Manutencao", "Producao", "Utilidades", "Qualidade"]),
                     rnd.choice(["ZMRO", "ZPRD"]), cat,
                     lead, est_min, round((est_min + est_max) / 2, 2), est_max,
                     consumo_mes, estoque, preco_mestre, data_iso(rnd.randint(30, 400)),
                     forn[1] if forn else None, forn[0] if forn else None,
                     cat_id[cat], confianca,
                     "AUTO" if confianca < 0.5 else "HISTORICO"))
        materiais.append((pn, descricao, cat, forn, consumo_mes, preco_base, lead))

    # ---- consumo mensal
    for pn, _, _, _, consumo_mes, _, _ in materiais:
        if consumo_mes <= 0:
            continue
        for m in range(MESES):
            if rnd.random() < 0.25:
                continue
            qtd = round(max(consumo_mes * rnd.uniform(0.3, 1.9), 0), 2)
            cur.execute("INSERT OR IGNORE INTO material_consumo (pn,ano_mes,quantidade,valor) "
                        "VALUES (?,?,?,?)", (pn, mes_iso(m), qtd, round(qtd * rnd.uniform(1, 3), 2)))

    # ---- histórico SAP
    pedido_n, req_n = 4500000000, 1000000
    for pn, descricao, cat, forn, consumo_mes, preco_base, lead in materiais:
        if not forn:
            continue
        for _ in range(rnd.randint(0, 9)):
            dias = rnd.randint(5, 700)
            # preço caminha no tempo; às vezes com desvio grande, o que vira divergência
            fator = rnd.uniform(0.80, 1.35) if rnd.random() > 0.12 else rnd.uniform(1.4, 2.2)
            preco = round(preco_base * fator, 4)
            qtd = round(max(consumo_mes * rnd.uniform(1, 4), 1), 2)
            pedido_n += 1
            req_n += 1
            cur.execute("""INSERT INTO compra_historico (fonte,pn,descricao,requisicao,pedido,
                             fornecedor_codigo,fornecedor_texto,fornecedor_id,data_documento,
                             data_remessa,quantidade,valor_total,moeda,preco_unitario,status,
                             requisitante,tipo_material)
                           VALUES ('ME2N',?,?,?,?,?,?,?,?,?,?,?,'BRL',?,?,?,'ZMRO')""",
                        (pn, descricao, f"RDA{req_n}", str(pedido_n),
                         f"F{100000 + forn[0]}", forn[1], forn[0],
                         data_iso(dias), data_iso(max(dias - lead - rnd.randint(-3, 10), 0)),
                         qtd, round(qtd * preco, 2), preco,
                         rnd.choice(["ENTREGUE", "ENTREGUE", "ENTREGUE", "PARCIAL", "ABERTO"]),
                         f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)}"))

    con.commit()
    return len(materiais), len(fornecedores)


def criar_usuarios(con, senha):
    """Contas de demonstração com senha conhecida e SEM troca obrigatória.

    Diferente do seed de produção de propósito: aqui o objetivo é alguém clonar
    o repositório e entrar em dez segundos. Está documentado no README.
    """
    from auth import hash_senha
    contas = [
        (f"comprador@{DOMINIO}",  "Comprador Demo",     "COMPRADOR"),
        (f"almoxarife@{DOMINIO}", "Almoxarife Demo",    "ALMOXARIFE"),
        (f"gestor@{DOMINIO}",     "Gestor Demo",        "GESTOR"),
        (f"admin@{DOMINIO}",      "Administrador Demo", "ADMIN"),
    ]
    for email, nome, perfil in contas:
        con.execute("""INSERT INTO usuario (email,nome,perfil,senha_hash,tenant_id,forcar_troca_senha)
                       VALUES (?,?,?,?,1,0)
                       ON CONFLICT(email) DO UPDATE SET senha_hash=excluded.senha_hash,
                                                        forcar_troca_senha=0""",
                    (email, nome, perfil, hash_senha(senha)))
    con.commit()
    return contas


def main():
    senha = os.environ.get("SENHA_DEMO", "demonstracao-2026")
    print(f"gerando {DESTINO}")

    con = criar_banco()
    n_mat, n_forn = povoar(con)
    con.close()
    print(f"  {n_mat} materiais, {n_forn} fornecedores")

    print("  aplicando migracoes")
    subprocess.check_call([sys.executable, os.path.join(AQUI, "aplicar_migracoes.py"), DESTINO])

    con = sqlite3.connect(DESTINO)
    con.execute("UPDATE tenant SET slug='demo', nome=?, dominio=? WHERE id=1", (EMPRESA, DOMINIO))
    con.commit()
    contas = criar_usuarios(con, senha)
    con.close()

    print("  calculando metricas e pendencias")
    env = dict(os.environ, DB_PATH=DESTINO)
    subprocess.check_call([sys.executable, os.path.join(AQUI, "metricas.py"), DESTINO], env=env)

    con = sqlite3.connect(DESTINO)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    resumo = {
        "materiais":      con.execute("SELECT COUNT(*) FROM material").fetchone()[0],
        "fornecedores":   con.execute("SELECT COUNT(*) FROM fornecedor").fetchone()[0],
        "movimentos SAP": con.execute("SELECT COUNT(*) FROM compra_historico").fetchone()[0],
        "metricas":       con.execute("SELECT COUNT(*) FROM material_metrica").fetchone()[0],
        "pendencias":     con.execute("SELECT COUNT(*) FROM pendencia").fetchone()[0],
        "sem fornecedor": con.execute("SELECT COUNT(*) FROM material WHERE fornecedor_id IS NULL").fetchone()[0],
    }
    con.close()

    print("\nbanco de demonstracao pronto:")
    for k, v in resumo.items():
        print(f"  {v:>6}  {k}")
    print(f"\ncontas (senha: {senha}):")
    for email, _, perfil in contas:
        print(f"  {email:<28} {perfil}")


if __name__ == "__main__":
    main()
