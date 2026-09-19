# -*- coding: utf-8 -*-
"""
Motor de inteligência de materiais: recalcula material_metrica e a fila de
pendências a partir dos dados já consolidados. Idempotente — pode rodar
quantas vezes quiser; pendências já resolvidas não voltam a abrir.

Uso:  python metricas.py [cotacoes.db]
"""
import sys, sqlite3, datetime, statistics

DB = sys.argv[1] if len(sys.argv) > 1 else "cotacoes.db"
HOJE = datetime.date.today()

def meses_atras(n):
    a, m = HOJE.year, HOJE.month - n
    while m <= 0: m += 12; a -= 1
    return f"{a:04d}-{m:02d}"

def media_ponderada(compras):
    """Preço médio ponderado pela quantidade — não é média simples de preços."""
    num = sum((c["preco"] or 0) * (c["qtd"] or 0) for c in compras)
    den = sum((c["qtd"] or 0) for c in compras)
    return (num / den) if den else (statistics.fmean([c["preco"] for c in compras]) if compras else None)

def recalcular(con):
    cur = con.cursor()
    cur.execute("DELETE FROM material_metrica")

    # --- compras por PN (preço unitário conhecido) -----------------------
    compras = {}
    for pn, dt, preco, qtd, fid in cur.execute("""
            SELECT pn, data_documento, preco_unitario, quantidade, fornecedor_id
            FROM compra_historico
            WHERE pn IS NOT NULL AND preco_unitario IS NOT NULL AND preco_unitario > 0
              AND data_documento IS NOT NULL
            ORDER BY data_documento""").fetchall():
        compras.setdefault(pn, []).append({"data": dt, "preco": abs(preco),
                                           "qtd": abs(qtd or 0), "forn": fid})

    # --- entradas e saídas (MB51) ---------------------------------------
    movs = {}
    for pn, dt, qtd in cur.execute("""
            SELECT pn, data_documento, quantidade FROM compra_historico
            WHERE fonte='MB51' AND data_documento IS NOT NULL""").fetchall():
        m = movs.setdefault(pn, {"entrada": None, "saida": None})
        chave = "entrada" if (qtd or 0) > 0 else "saida"
        if not m[chave] or dt > m[chave]: m[chave] = dt

    # --- consumo mensal --------------------------------------------------
    consumo = {}
    for pn, am, q, v in cur.execute("SELECT pn, ano_mes, quantidade, valor FROM material_consumo"):
        consumo.setdefault(pn, {})[am] = (q or 0, v or 0)

    lim3, lim6, lim12 = meses_atras(3), meses_atras(6), meses_atras(12)
    linhas, valor_anual = [], {}

    for pn, desc, mm60, est, emin, emax, lt, cons_planilha in cur.execute("""
            SELECT pn, descricao, preco_unitario, estoque_atual, estoque_min, estoque_max,
                   lead_time_dias, consumo_med_mes FROM material""").fetchall():
        cp = compras.get(pn, [])
        c12 = [c for c in cp if c["data"] >= lim12]
        ult = cp[-1] if cp else None

        cons = consumo.get(pn, {})
        q12 = [q for am, (q, v) in cons.items() if am >= lim12]
        q6  = [q for am, (q, v) in cons.items() if am >= lim6]
        q3  = [q for am, (q, v) in cons.items() if am >= lim3]
        v12 = sum(v for am, (q, v) in cons.items() if am >= lim12)
        consumo_12m = sum(q12)
        media_mes = (consumo_12m / 12) if q12 else (cons_planilha or 0)

        cobertura = (est / media_mes) if (media_mes and est is not None) else None
        lt_meses = ((lt or 30) / 30.0)
        ponto_rep = media_mes * lt_meses if media_mes else None

        if media_mes == 0 and (est or 0) > 0:
            risco = "SEM_MOVIMENTO"
        elif cobertura is None:
            risco = None
        elif cobertura < lt_meses:
            risco = "RUPTURA"
        elif cobertura < lt_meses * 1.5:
            risco = "BAIXO"
        elif emax and est and est > emax * 1.5:
            risco = "ELEVADO"
        else:
            risco = "OK"

        # Divergência só faz sentido quando as duas pontas estão na mesma escala.
        # Razões acima de ~50x indicam unidade de preço/medida diferente entre o
        # MM60 e o movimento (preço por 1.000, KG x UN etc.), não diferença comercial.
        divergencia, escala_suspeita = None, False
        if mm60 and ult and mm60 > 0:
            razao = ult["preco"] / mm60
            if razao > 50 or razao < 0.02:
                escala_suspeita = True
            else:
                divergencia = (ult["preco"] - mm60) / mm60
        oportunidade = None
        if divergencia is not None and divergencia < -0.05 and consumo_12m:
            # diferença anualizada indicativa — NÃO é saving realizado
            oportunidade = (mm60 - ult["preco"]) * consumo_12m

        # lead time observado: dias entre pedido (ME2N) e entrada (MB51)
        lead_obs = None
        ped = cur.execute("""SELECT data_documento, data_remessa FROM compra_historico
                             WHERE pn=? AND fonte='ME2N' AND data_remessa IS NOT NULL
                             ORDER BY data_documento DESC LIMIT 5""", (pn,)).fetchall()
        difs = []
        for d1, d2 in ped:
            try:
                difs.append((datetime.date.fromisoformat(d2) - datetime.date.fromisoformat(d1)).days)
            except Exception: pass
        if difs: lead_obs = statistics.fmean([d for d in difs if 0 <= d <= 400] or difs)

        mv = movs.get(pn, {})
        valor_anual[pn] = v12 or (consumo_12m * (ult["preco"] if ult else (mm60 or 0)))

        linhas.append(dict(
            pn=pn,
            ultimo_preco=ult["preco"] if ult else None,
            ultimo_preco_data=ult["data"] if ult else None,
            ultimo_fornecedor_id=ult["forn"] if ult else None,
            media_3m=media_ponderada([c for c in cp if c["data"] >= lim3]),
            media_6m=media_ponderada([c for c in cp if c["data"] >= lim6]),
            media_12m=media_ponderada(c12),
            menor_preco=min((c["preco"] for c in cp), default=None),
            maior_preco=max((c["preco"] for c in cp), default=None),
            compras_12m=len(c12),
            consumo_3m=sum(q3) or None, consumo_6m=sum(q6) or None,
            consumo_12m=consumo_12m or None, consumo_anual=consumo_12m or None,
            meses_sem_consumo=sum(1 for i in range(12) if meses_atras(i) not in cons),
            cobertura_meses=cobertura, ponto_reposicao=ponto_rep, risco=risco,
            divergencia_pct=divergencia, oportunidade_ano=oportunidade,
            lead_time_obs=lead_obs, escala_suspeita=1 if escala_suspeita else 0,
            ultima_entrada=mv.get("entrada"), ultima_saida=mv.get("saida"),
            classe_abc=None, classe_xyz=None))

    # --- curva ABC por valor de consumo 12M ------------------------------
    ordenado = sorted(valor_anual.items(), key=lambda x: -(x[1] or 0))
    total = sum(v or 0 for _, v in ordenado) or 1
    acum, classe = 0.0, {}
    for pn, v in ordenado:
        acum += (v or 0) / total
        classe[pn] = "A" if acum <= 0.8 else ("B" if acum <= 0.95 else "C")

    # --- XYZ por regularidade (coeficiente de variação do consumo) -------
    xyz = {}
    for pn, cons in consumo.items():
        qs = [cons.get(meses_atras(i), (0, 0))[0] for i in range(12)]
        m = statistics.fmean(qs)
        if m <= 0: xyz[pn] = "Z"; continue
        cv = statistics.pstdev(qs) / m
        xyz[pn] = "X" if cv < 0.5 else ("Y" if cv < 1.0 else "Z")

    for l in linhas:
        l["classe_abc"] = classe.get(l["pn"])
        l["classe_xyz"] = xyz.get(l["pn"])

    cols = list(linhas[0].keys()) if linhas else []
    cur.executemany(f"INSERT INTO material_metrica ({','.join(cols)}) "
                    f"VALUES ({','.join(':'+c for c in cols)})", linhas)
    con.commit()
    return len(linhas)

# ---------------------------------------------------------------- pendências
def sincronizar_pendencias(con):
    cur = con.cursor()
    achadas = []
    def add(sev, tipo, entidade, registro, problema, sugestao=None):
        achadas.append((f"{tipo}|{registro}", sev, tipo, entidade, str(registro),
                        problema, sugestao))

    # material sem fornecedor, mas com histórico que sugere um
    for pn, desc, forn, nome, n, ult, tot in cur.execute("""
        WITH h AS (SELECT ch.pn, ch.fornecedor_id, COUNT(*) n, MAX(ch.data_documento) ult
                   FROM compra_historico ch WHERE ch.fornecedor_id IS NOT NULL GROUP BY 1,2)
        SELECT m.pn, m.descricao, h.fornecedor_id, f.razao_social, h.n, h.ult,
               (SELECT SUM(n) FROM h h2 WHERE h2.pn = m.pn)
        FROM material m JOIN h ON h.pn = m.pn JOIN fornecedor f ON f.id = h.fornecedor_id
        WHERE m.fornecedor_id IS NULL
          AND h.n = (SELECT MAX(n) FROM h h3 WHERE h3.pn = m.pn)"""):
        pct = (n / tot * 100) if tot else 0
        add("ALTA", "Material sem fornecedor cadastrado", "material", pn,
            f"{desc or ''} — sem fornecedor no cadastro mestre",
            f"{nome}: {n} compra(s), {pct:.0f}% do histórico, última em {ult}")

    for pn, desc in cur.execute("""
        SELECT m.pn, m.descricao FROM material m
        WHERE m.fornecedor_id IS NULL
          AND (m.origem_dados LIKE '%BASE' OR m.origem_dados LIKE '%Controle')
          AND NOT EXISTS (SELECT 1 FROM compra_historico ch
                          WHERE ch.pn = m.pn AND ch.fornecedor_id IS NOT NULL)"""):
        add("MEDIA", "Material sem fornecedor e sem histórico", "material", pn,
            f"{desc or ''} — sem fornecedor e sem compra registrada",
            "Definir fornecedor manualmente ou abrir cotação para prospecção")

    for email, cat in cur.execute("""
        SELECT ce.email, c.nome FROM categoria_email ce JOIN categoria c ON c.id = ce.categoria_id
        WHERE ce.fornecedor_id IS NULL"""):
        add("CRITICA", "E-mail de cotação sem fornecedor", "email", email,
            f"Recebe cotação na categoria {cat} sem ficha de fornecedor",
            "Cadastrar o fornecedor e vincular o e-mail")

    for pn, desc, mm60, up in cur.execute("""
        SELECT m.pn, m.descricao, m.preco_unitario, mm.ultimo_preco
        FROM material_metrica mm JOIN material m ON m.pn = mm.pn
        WHERE mm.escala_suspeita = 1"""):
        add("MEDIA", "Escala de preço inconsistente", "material", pn,
            f"MM60 R$ {mm60:,.4f} x último pago R$ {up:,.4f} — diferença de escala, "
            "provável unidade de preço ou de medida diferente",
            "Conferir 'Unidade de preço' no MM60 e a UM do movimento antes de comparar")

    for pn, desc, div, mm60, up in cur.execute("""
        SELECT m.pn, m.descricao, mm.divergencia_pct, m.preco_unitario, mm.ultimo_preco
        FROM material_metrica mm JOIN material m ON m.pn = mm.pn
        WHERE ABS(COALESCE(mm.divergencia_pct,0)) > 0.30"""):
        add("MEDIA", "Divergência de preço acima de 30%", "material", pn,
            f"MM60 R$ {mm60:,.2f} x último pago R$ {up:,.2f} ({div:+.0%})",
            "Revisar preço mestre no SAP ou renegociar com o fornecedor")

    for pn, desc, cob in cur.execute("""
        SELECT m.pn, m.descricao, mm.cobertura_meses FROM material_metrica mm
        JOIN material m ON m.pn = mm.pn WHERE mm.risco = 'RUPTURA'"""):
        add("ALTA", "Risco de ruptura", "material", pn,
            f"{desc or ''} — cobertura de {cob:.1f} mês(es), abaixo do lead time",
            "Abrir cotação ou requisição de reposição")

    for razao, cod in cur.execute("""
        SELECT razao_social, codigo_sap FROM fornecedor f
        WHERE NOT EXISTS (SELECT 1 FROM contato c WHERE c.fornecedor_id=f.id AND c.email IS NOT NULL)"""):
        add("ALTA", "Fornecedor sem e-mail", "fornecedor", cod or razao,
            f"{razao} não tem nenhum e-mail cadastrado", "Cadastrar contato comercial")

    novas = 0
    for codigo, sev, tipo, ent, reg, prob, sug in achadas:
        r = cur.execute("SELECT id, status FROM pendencia WHERE codigo=?", (codigo,)).fetchone()
        if r is None:
            cur.execute("""INSERT INTO pendencia (codigo,severidade,tipo,entidade,registro,
                           problema,sugestao) VALUES (?,?,?,?,?,?,?)""",
                        (codigo, sev, tipo, ent, reg, prob, sug))
            novas += 1
        elif r[1] in ("ABERTA", "EM_ANALISE"):
            cur.execute("UPDATE pendencia SET problema=?, sugestao=?, severidade=? WHERE id=?",
                        (prob, sug, sev, r[0]))
    # o que não foi achado nesta rodada e continua aberto = resolvido na origem
    codigos = {c[0] for c in achadas}
    for pid, cod in cur.execute("SELECT id, codigo FROM pendencia WHERE status IN ('ABERTA','EM_ANALISE')").fetchall():
        if cod not in codigos:
            cur.execute("UPDATE pendencia SET status='RESOLVIDA', resolvido_em=datetime('now'), "
                        "justificativa=COALESCE(justificativa,'Resolvida na origem dos dados') WHERE id=?", (pid,))
    con.commit()
    return len(achadas), novas

if __name__ == "__main__":
    con = sqlite3.connect(DB)
    n = recalcular(con)
    tot, novas = sincronizar_pendencias(con)
    print(f"métricas: {n} materiais · pendências: {tot} ativas ({novas} novas)")
    for r in con.execute("SELECT severidade, COUNT(*) FROM pendencia WHERE status='ABERTA' GROUP BY 1"):
        print("  ", r[0], r[1])
    con.close()
