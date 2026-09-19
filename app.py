# -*- coding: utf-8 -*-
"""
Portal de Gestão de Cotações
Módulo Almoxarifado e Inteligência de Materiais (Fase 1).
API sobre o banco já consolidado; a interface está em templates/app.html.
"""
import os, io, csv, json, time, sqlite3, datetime, collections, smtplib, ssl, re
from email.message import EmailMessage
from flask import Flask, request, jsonify, g, render_template, make_response, Response
from werkzeug.middleware.proxy_fix import ProxyFix
import config
import auth
from auth import exige, pode

DB = config.DB_PATH
DRY_RUN = config.DRY_RUN
app = Flask(__name__)
app.secret_key = config.APP_SECRET
# Atrás de nginx/Caddy/Traefik: confia no X-Forwarded-Proto e X-Forwarded-For do
# primeiro proxy, para que o rate limit veja o IP real e o cookie Secure funcione.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ----------------------------------------------------------------- infra
def conectar():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")      # leitores não bloqueiam o escritor
    con.execute("PRAGMA busy_timeout=15000")
    return con

@app.before_request
def antes():
    g.con = conectar()
    g.usuario = auth.usuario_da_sessao(g.con)
    g.tenant_id = auth.tenant_atual()

@app.after_request
def cabecalhos(resp):
    """Cabeçalhos de segurança. A CSP é restritiva porque a interface serve todo o
    JS/CSS do próprio domínio — não há CDN nem script inline."""
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Content-Security-Policy",
                            "default-src 'self'; img-src 'self' data:; "
                            "style-src 'self' 'unsafe-inline'; object-src 'none'; "
                            "base-uri 'self'; frame-ancestors 'none'")
    if config.COOKIE_SECURE:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.teardown_request
def depois(exc):
    con = g.pop("con", None)
    if con: con.close()

# rate limiting simples em memória (por IP+rota), evita disparo acidental
_BALDE = collections.defaultdict(list)
LIMITES = {"/api/login": (config.LIMITE_LOGIN, 300),
           "/api/cotacoes/enviar": (config.LIMITE_ENVIO, 300),
           "/api/senha": (10, 300)}

@app.before_request
def limite():
    regra = LIMITES.get(request.path)
    if not regra: return
    max_req, janela = regra
    chave = (request.remote_addr, request.path)
    agora = time.time()
    _BALDE[chave] = [t for t in _BALDE[chave] if agora - t < janela]
    if len(_BALDE[chave]) >= max_req:
        return jsonify({"erro": "Muitas tentativas. Aguarde alguns minutos."}), 429
    _BALDE[chave].append(agora)

MASCARA = re.compile(r"(?i)(senha|password|token|csrf)")
def mascarar(d):
    return {k: ("***" if MASCARA.search(k) else v) for k, v in (d or {}).items()}

def auditar(acao, entidade, entidade_id, detalhe=None):
    u = g.get("usuario") or {}
    g.con.execute("""INSERT INTO auditoria (usuario_id,usuario_email,acao,entidade,entidade_id,
                     detalhe,ip) VALUES (?,?,?,?,?,?,?)""",
                  (u.get("id"), u.get("email"), acao, entidade, str(entidade_id),
                   json.dumps(mascarar(detalhe), ensure_ascii=False) if detalhe else None,
                   request.remote_addr))
    g.con.commit()

def q(sql, p=()):   return [dict(r) for r in g.con.execute(sql, p).fetchall()]
def q1(sql, p=()):
    r = g.con.execute(sql, p).fetchone()
    return dict(r) if r else None
def escalar(sql, p=()):
    r = g.con.execute(sql, p).fetchone()
    return r[0] if r else None

def paginar(sql_base, params, page, per_page, order_sql):
    total = escalar(f"SELECT COUNT(*) FROM ({sql_base})", params)
    linhas = q(f"{sql_base} ORDER BY {order_sql} LIMIT ? OFFSET ?",
               list(params) + [per_page, (page - 1) * per_page])
    return {"total": total, "pagina": page, "por_pagina": per_page, "linhas": linhas}

# ----------------------------------------------------------------- login
@app.route("/")
def index():
    return render_template("app.html")

@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json(force=True)
    u = q1("SELECT * FROM usuario WHERE lower(email)=lower(?) AND ativo=1", (d.get("email", ""),))
    if not u or not auth.confere_senha(d.get("senha", ""), u["senha_hash"]):
        return jsonify({"erro": "E-mail ou senha inválidos."}), 401
    token, csrf = auth.criar_sessao(g.con, u["id"], request.remote_addr)
    g.usuario = {"id": u["id"], "email": u["email"], "perfil": u["perfil"], "csrf": csrf}
    auditar("LOGIN", "usuario", u["id"], {"perfil": u["perfil"]})
    resp = make_response(jsonify({"nome": u["nome"], "email": u["email"], "perfil": u["perfil"],
                                  "csrf": csrf, "trocar_senha": bool(u["forcar_troca_senha"]),
                                  "permissoes": sorted(auth.PERMISSOES.get(u["perfil"], []))}))
    resp.set_cookie("sessao", token, httponly=True, samesite=config.COOKIE_SAMESITE,
                    secure=config.COOKIE_SECURE, max_age=auth.SESSAO_HORAS * 3600)
    return resp

@app.route("/api/logout", methods=["POST"])
def logout():
    if g.get("usuario"):
        g.con.execute("UPDATE sessao SET revogada=1 WHERE token=?", (g.usuario["token"],))
        g.con.commit()
    resp = make_response(jsonify({"ok": True})); resp.delete_cookie("sessao"); return resp

@app.route("/api/me")
def me():
    if not g.get("usuario"): return jsonify({"erro": "sem sessão"}), 401
    u = g.usuario
    return jsonify({"nome": q1("SELECT nome FROM usuario WHERE id=?", (u["id"],))["nome"],
                    "email": u["email"], "perfil": u["perfil"], "csrf": u["csrf"],
                    "trocar_senha": bool(u.get("forcar_troca_senha")),
                    "tenant": q1("SELECT nome FROM tenant WHERE id=?", (g.tenant_id,)),
                    "permissoes": sorted(auth.PERMISSOES.get(u["perfil"], []))})

# ----------------------------------------------------------------- navegação
@app.route("/api/nav")
@exige()
def nav():
    return jsonify({
        "sem_fornecedor": escalar("SELECT COUNT(*) FROM material WHERE fornecedor_id IS NULL AND "
                                  "(origem_dados LIKE '%BASE' OR origem_dados LIKE '%Controle')"),
        "divergencias": escalar("SELECT COUNT(*) FROM material_metrica WHERE ABS(COALESCE(divergencia_pct,0))>0.30"),
        "pendencias_criticas": escalar("SELECT COUNT(*) FROM pendencia WHERE status='ABERTA' AND severidade IN ('CRITICA','ALTA')"),
        "pendencias": escalar("SELECT COUNT(*) FROM pendencia WHERE status='ABERTA'"),
        "ruptura": escalar("SELECT COUNT(*) FROM material_metrica WHERE risco='RUPTURA'"),
        "sem_movimento": escalar("SELECT COUNT(*) FROM material_metrica WHERE risco='SEM_MOVIMENTO'"),
        "oportunidades": escalar("SELECT COUNT(*) FROM material_metrica WHERE oportunidade_ano>0"),
        "cotacoes_abertas": escalar("SELECT COUNT(*) FROM processo WHERE status NOT IN ('FINALIZADO','CANCELADO')"),
        "cotacoes_aguardando": escalar("SELECT COUNT(*) FROM processo WHERE status IN ('ENVIADO','AGUARDANDO')"),
    })

# ----------------------------------------------------------------- dashboard
@app.route("/api/dashboard")
@exige()
def dashboard():
    perfil = g.usuario["perfil"]
    cards = {
        "materiais": escalar("SELECT COUNT(*) FROM material"),
        "materiais_almox": escalar("SELECT COUNT(*) FROM material WHERE origem_dados LIKE '%BASE' OR origem_dados LIKE '%Controle'"),
        "valor_estoque": escalar("""SELECT ROUND(SUM(m.estoque_atual * m.preco_unitario),2) FROM material m
                                    WHERE m.estoque_atual>0 AND m.preco_unitario>0
                                      AND COALESCE((SELECT escala_suspeita FROM material_metrica mm WHERE mm.pn=m.pn),0)=0"""),
        "ruptura": escalar("SELECT COUNT(*) FROM material_metrica WHERE risco='RUPTURA'"),
        "sem_movimento": escalar("SELECT COUNT(*) FROM material_metrica WHERE risco='SEM_MOVIMENTO'"),
        "sem_fornecedor": escalar("SELECT COUNT(*) FROM material WHERE fornecedor_id IS NULL AND "
                                  "(origem_dados LIKE '%BASE' OR origem_dados LIKE '%Controle')"),
        "divergencias": escalar("SELECT COUNT(*) FROM material_metrica WHERE ABS(COALESCE(divergencia_pct,0))>0.30"),
        "oportunidade_valor": escalar("SELECT ROUND(SUM(oportunidade_ano),2) FROM material_metrica WHERE oportunidade_ano>0"),
        "cotacoes_abertas": escalar("SELECT COUNT(*) FROM processo WHERE status NOT IN ('FINALIZADO','CANCELADO')"),
        "cotacoes_aguardando": escalar("SELECT COUNT(*) FROM processo WHERE status IN ('ENVIADO','AGUARDANDO')"),
        "fornecedores": escalar("SELECT COUNT(*) FROM fornecedor WHERE status='ATIVO'"),
    }
    consumo = q("""SELECT ano_mes, ROUND(SUM(quantidade),0) qtd, ROUND(SUM(valor),2) valor
                   FROM material_consumo GROUP BY 1 ORDER BY 1 DESC LIMIT 12""")[::-1]
    precos = q("""SELECT substr(data_documento,1,7) mes, ROUND(SUM(valor_total),2) valor,
                         COUNT(*) n
                  FROM compra_historico WHERE valor_total IS NOT NULL AND data_documento IS NOT NULL
                  GROUP BY 1 ORDER BY 1 DESC LIMIT 12""")[::-1]
    categorias = q("""SELECT COALESCE(c.nome,'(sem categoria)') cat, ROUND(SUM(ABS(ch.valor_total)),2) valor
                      FROM compra_historico ch LEFT JOIN material m ON m.pn = ch.pn
                      LEFT JOIN categoria c ON c.id = m.categoria_id
                      WHERE ch.valor_total IS NOT NULL GROUP BY 1 ORDER BY valor DESC LIMIT 8""")
    fornecedores = q("""SELECT f.razao_social nome, COUNT(*) compras,
                          ROUND(SUM(ABS(ch.valor_total)),2) valor
                        FROM compra_historico ch JOIN fornecedor f ON f.id = ch.fornecedor_id
                        WHERE ch.valor_total IS NOT NULL GROUP BY 1 ORDER BY valor DESC LIMIT 8""")
    oportunidades = q("""SELECT mm.pn, m.descricao, m.preco_unitario mm60, mm.ultimo_preco,
                           mm.divergencia_pct, mm.consumo_12m, ROUND(mm.oportunidade_ano,2) oportunidade
                         FROM material_metrica mm JOIN material m ON m.pn = mm.pn
                         WHERE mm.oportunidade_ano > 0 ORDER BY mm.oportunidade_ano DESC LIMIT 8""")
    atencao = []
    if cards["divergencias"]:
        atencao.append({"texto": f"{cards['divergencias']} materiais com divergência de preço acima de 30%.",
                        "acao": "Ver materiais", "rota": "#/precos/divergencias"})
    if cards["sem_fornecedor"]:
        atencao.append({"texto": f"{cards['sem_fornecedor']} materiais do almoxarifado sem fornecedor cadastrado.",
                        "acao": "Resolver pendência", "rota": "#/materiais/sem-fornecedor"})
    crit = escalar("SELECT COUNT(*) FROM pendencia WHERE status='ABERTA' AND severidade IN ('CRITICA','ALTA')")
    if crit:
        atencao.append({"texto": f"{crit} pendências críticas aguardam revisão.",
                        "acao": "Resolver pendência", "rota": "#/pendencias"})
    if cards["ruptura"]:
        atencao.append({"texto": f"{cards['ruptura']} materiais com cobertura abaixo do lead time (risco de ruptura).",
                        "acao": "Ver materiais", "rota": "#/estoque/ruptura"})
    return jsonify({"perfil": perfil, "cards": cards, "consumo": consumo, "precos": precos,
                    "categorias": categorias, "fornecedores": fornecedores,
                    "oportunidades": oportunidades, "atencao": atencao})

# ----------------------------------------------------------------- busca universal
@app.route("/api/busca")
@exige()
def busca():
    termo = (request.args.get("q") or "").strip()
    if len(termo) < 2: return jsonify({"grupos": []})
    like = f"%{termo}%"
    grupos = []
    mats = q("""SELECT m.pn, m.descricao, c.nome categoria FROM material m
                LEFT JOIN categoria c ON c.id=m.categoria_id
                WHERE m.pn LIKE ? OR m.descricao LIKE ? LIMIT 8""", (like, like))
    if mats: grupos.append({"titulo": "Materiais", "tipo": "material", "itens": [
        {"id": m["pn"], "titulo": f"{m['pn']} — {m['descricao'] or ''}",
         "sub": m["categoria"] or ""} for m in mats]})
    forn = q("""SELECT id, razao_social, codigo_sap, cnpj FROM fornecedor
                WHERE razao_social LIKE ? OR codigo_sap LIKE ? OR COALESCE(cnpj,'') LIKE ? LIMIT 6""",
             (like, like, like))
    if forn: grupos.append({"titulo": "Fornecedores", "tipo": "fornecedor", "itens": [
        {"id": f["id"], "titulo": f["razao_social"], "sub": f"código {f['codigo_sap'] or '—'}"} for f in forn]})
    docs = q("""SELECT DISTINCT pedido, requisicao, pn FROM compra_historico
                WHERE pedido LIKE ? OR requisicao LIKE ? LIMIT 6""", (like, like))
    if docs: grupos.append({"titulo": "Documentos SAP", "tipo": "sap", "itens": [
        {"id": d["pedido"] or d["requisicao"],
         "titulo": f"Pedido {d['pedido'] or '—'} · RDA {d['requisicao'] or '—'}",
         "sub": f"PN {d['pn']}"} for d in docs]})
    procs = q("""SELECT id, numero, requisicao, status FROM processo
                 WHERE numero LIKE ? OR COALESCE(requisicao,'') LIKE ? LIMIT 5""", (like, like))
    if procs: grupos.append({"titulo": "Cotações", "tipo": "cotacao", "itens": [
        {"id": p["id"], "titulo": f"{p['numero']} · {p['requisicao'] or ''}",
         "sub": p["status"]} for p in procs]})
    cats = q("SELECT id, nome FROM categoria WHERE nome LIKE ? LIMIT 5", (like,))
    if cats: grupos.append({"titulo": "Categorias", "tipo": "categoria", "itens": [
        {"id": c["id"], "titulo": c["nome"], "sub": ""} for c in cats]})
    return jsonify({"grupos": grupos})

# ----------------------------------------------------------------- materiais
FILTRO_SQL = """
SELECT m.pn, m.descricao, m.umb, m.area, c.nome categoria, m.estoque_atual,
       mm.consumo_12m/12.0 consumo_mes, mm.ultimo_preco, m.preco_unitario mm60,
       mm.divergencia_pct, mm.cobertura_meses, mm.risco, mm.classe_abc, mm.classe_xyz,
       mm.escala_suspeita, mm.ultimo_preco_data ultima_compra,
       f.razao_social ultimo_fornecedor, m.fornecedor_id,
       fm.razao_social fornecedor_cadastro
FROM material m
LEFT JOIN material_metrica mm ON mm.pn = m.pn
LEFT JOIN categoria c ON c.id = m.categoria_id
LEFT JOIN fornecedor f ON f.id = mm.ultimo_fornecedor_id
LEFT JOIN fornecedor fm ON fm.id = m.fornecedor_id
WHERE 1=1
"""
ORDENAVEIS = {"pn": "m.pn", "descricao": "m.descricao", "categoria": "c.nome",
              "estoque_atual": "m.estoque_atual", "consumo_mes": "consumo_mes",
              "ultimo_preco": "mm.ultimo_preco", "mm60": "m.preco_unitario",
              "divergencia_pct": "mm.divergencia_pct", "ultima_compra": "mm.ultimo_preco_data",
              "cobertura_meses": "mm.cobertura_meses", "risco": "mm.risco"}

def filtros_materiais(a):
    sql, p = FILTRO_SQL, []
    if a.get("q"):
        sql += " AND (m.pn LIKE ? OR m.descricao LIKE ?)"; p += [f"%{a['q']}%"] * 2
    if a.get("categoria"):
        sql += " AND c.nome = ?"; p.append(a["categoria"])
    if a.get("area"):
        sql += " AND m.area = ?"; p.append(a["area"])
    if a.get("fornecedor"):
        sql += " AND (fm.razao_social LIKE ? OR f.razao_social LIKE ?)"; p += [f"%{a['fornecedor']}%"] * 2
    if a.get("risco"):
        sql += " AND mm.risco = ?"; p.append(a["risco"])
    if a.get("classe_abc"):
        sql += " AND mm.classe_abc = ?"; p.append(a["classe_abc"])
    if a.get("almoxarifado") == "1":
        sql += " AND (m.origem_dados LIKE '%BASE' OR m.origem_dados LIKE '%Controle')"
    if a.get("sem_fornecedor") == "1":
        sql += " AND m.fornecedor_id IS NULL"
    if a.get("com_fornecedor") == "1":
        sql += " AND m.fornecedor_id IS NOT NULL"
    if a.get("divergencia") == "1":
        sql += " AND ABS(COALESCE(mm.divergencia_pct,0)) > 0.30"
    if a.get("preco_min"):
        sql += " AND mm.ultimo_preco >= ?"; p.append(float(a["preco_min"]))
    if a.get("preco_max"):
        sql += " AND mm.ultimo_preco <= ?"; p.append(float(a["preco_max"]))
    if a.get("compra_desde"):
        sql += " AND mm.ultimo_preco_data >= ?"; p.append(a["compra_desde"])
    if a.get("estoque_zero") == "1":
        sql += " AND COALESCE(m.estoque_atual,0) = 0"
    return sql, p

@app.route("/api/materiais")
@exige("material.ver")
def materiais():
    a = request.args
    sql, p = filtros_materiais(a)
    col = ORDENAVEIS.get(a.get("ordem"), "m.pn")
    dire = "DESC" if a.get("dir") == "desc" else "ASC"
    page = max(1, int(a.get("pagina", 1))); pp = min(200, int(a.get("por_pagina", 50)))
    return jsonify(paginar(sql, p, page, pp, f"{col} {dire} NULLS LAST"))

@app.route("/api/materiais/export")
@exige("material.ver")
def materiais_export():
    sql, p = filtros_materiais(request.args)
    linhas = q(sql + " ORDER BY m.pn LIMIT 20000", p)
    buf = io.StringIO(); w = csv.writer(buf, delimiter=";")
    cabec = ["PN", "Descrição", "Categoria", "UMB", "Área", "Estoque", "Consumo/mês",
             "Último preço", "MM60", "Divergência %", "Cobertura (meses)", "Risco",
             "ABC", "XYZ", "Último fornecedor", "Última compra"]
    w.writerow(cabec)
    for l in linhas:
        w.writerow([l["pn"], l["descricao"], l["categoria"], l["umb"], l["area"],
                    l["estoque_atual"], round(l["consumo_mes"] or 0, 2), l["ultimo_preco"],
                    l["mm60"], round((l["divergencia_pct"] or 0) * 100, 1),
                    round(l["cobertura_meses"] or 0, 1), l["risco"], l["classe_abc"],
                    l["classe_xyz"], l["ultimo_fornecedor"], l["ultima_compra"]])
    auditar("EXPORTOU", "material", "lista", {"filtros": dict(request.args), "linhas": len(linhas)})
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=materiais.csv"})

@app.route("/api/filtros/<tela>", methods=["GET", "POST"])
@exige()
def filtros(tela):
    if request.method == "POST":
        d = request.get_json(force=True)
        g.con.execute("""INSERT INTO filtro_salvo (usuario_id,tela,nome,filtros) VALUES (?,?,?,?)
                         ON CONFLICT(usuario_id,tela,nome) DO UPDATE SET filtros=excluded.filtros""",
                      (g.usuario["id"], tela, d["nome"], json.dumps(d.get("filtros", {}))))
        g.con.commit()
        return jsonify({"ok": True})
    return jsonify(q("SELECT id,nome,filtros FROM filtro_salvo WHERE usuario_id=? AND tela=? ORDER BY nome",
                     (g.usuario["id"], tela)))

# ----------------------------------------------------------------- ficha 360º
@app.route("/api/material/<pn>")
@exige("material.ver")
def material(pn):
    m = q1("""SELECT m.*, c.nome categoria, fm.razao_social fornecedor_cadastro,
                     fm.id fornecedor_cadastro_id
              FROM material m LEFT JOIN categoria c ON c.id=m.categoria_id
              LEFT JOIN fornecedor fm ON fm.id=m.fornecedor_id WHERE m.pn=?""", (pn,))
    if not m: return jsonify({"erro": "Material não encontrado."}), 404
    mm = q1("""SELECT mm.*, f.razao_social ultimo_fornecedor_nome
               FROM material_metrica mm LEFT JOIN fornecedor f ON f.id=mm.ultimo_fornecedor_id
               WHERE mm.pn=?""", (pn,)) or {}
    lt = mm.get("lead_time_obs") or m.get("lead_time_dias")
    alertas = []
    if mm.get("risco") == "RUPTURA":
        alertas.append({"nivel": "critico", "titulo": "Risco de ruptura",
                        "motivo": f"Estoque atual: {m.get('estoque_atual') or 0:g} {m.get('umb') or ''}. "
                                  f"Consumo médio: {(mm.get('consumo_12m') or 0)/12:.1f}/mês. "
                                  f"Cobertura estimada: {(mm.get('cobertura_meses') or 0)*30:.0f} dias."})
    if mm.get("risco") == "SEM_MOVIMENTO":
        alertas.append({"nivel": "atencao", "titulo": "Material sem movimentação",
                        "motivo": f"Sem consumo nos últimos 12 meses e {m.get('estoque_atual') or 0:g} "
                                  f"{m.get('umb') or ''} em estoque — possível obsolescência."})
    if mm.get("risco") == "ELEVADO":
        alertas.append({"nivel": "atencao", "titulo": "Estoque elevado",
                        "motivo": f"Estoque atual ({m.get('estoque_atual') or 0:g}) acima de 1,5× o máximo "
                                  f"({m.get('estoque_max') or 0:g})."})
    if mm.get("escala_suspeita"):
        alertas.append({"nivel": "info", "titulo": "Comparação de preço indisponível",
                        "motivo": "Preço mestre e preço pago estão em escalas diferentes "
                                  "(unidade de preço do MM60 x UM do movimento). Divergência não calculada."})
    elif mm.get("divergencia_pct") is not None and abs(mm["divergencia_pct"]) > 0.30:
        alertas.append({"nivel": "atencao", "titulo": f"Divergência de preço: {mm['divergencia_pct']:+.1%}",
                        "motivo": f"Preço mestre MM60 R$ {m.get('preco_unitario') or 0:,.2f} contra "
                                  f"último pago R$ {mm.get('ultimo_preco') or 0:,.2f}."})
    if not m.get("fornecedor_id"):
        alertas.append({"nivel": "atencao", "titulo": "Sem fornecedor no cadastro",
                        "motivo": "O material não tem fornecedor definido no cadastro mestre."})
    return jsonify({"material": m, "metricas": mm, "lead_time": lt, "alertas": alertas})

@app.route("/api/material/<pn>/precos")
@exige("preco.ver")
def material_precos(pn):
    periodo = request.args.get("periodo", "12")
    corte = None
    if periodo != "all":
        meses = int(periodo)
        d = datetime.date.today()
        a, mth = d.year, d.month - meses
        while mth <= 0: mth += 12; a -= 1
        corte = f"{a:04d}-{mth:02d}-01"
    sql = """SELECT ch.data_documento data, ch.preco_unitario preco, ch.quantidade qtd,
                    ch.pedido, ch.requisicao, ch.fonte, f.razao_social fornecedor
             FROM compra_historico ch LEFT JOIN fornecedor f ON f.id=ch.fornecedor_id
             WHERE ch.pn=? AND ch.preco_unitario>0 AND ch.data_documento IS NOT NULL"""
    p = [pn]
    if corte: sql += " AND ch.data_documento >= ?"; p.append(corte)
    pontos = q(sql + " ORDER BY ch.data_documento", p)
    mm = q1("SELECT * FROM material_metrica WHERE pn=?", (pn,)) or {}
    mat = q1("SELECT preco_unitario, moeda, preco_atualizado_em FROM material WHERE pn=?", (pn,)) or {}
    usados = [p_ for p_ in pontos]
    explicacao = None
    if mm.get("media_12m"):
        n = mm.get("compras_12m") or 0
        datas = [p_["data"] for p_ in pontos]
        explicacao = (f"Média 12M calculada com {n} compra(s)"
                      + (f" entre {min(datas)} e {max(datas)}" if datas else "")
                      + ", ponderada pela quantidade de cada compra.")
    return jsonify({"pontos": pontos, "metricas": mm, "mm60": mat.get("preco_unitario"),
                    "mm60_data": mat.get("preco_atualizado_em"), "explicacao": explicacao,
                    "registros": usados})

@app.route("/api/material/<pn>/consumo")
@exige("consumo.ver")
def material_consumo(pn):
    linhas = q("""SELECT ano_mes, quantidade, valor FROM material_consumo
                  WHERE pn=? ORDER BY ano_mes""", (pn,))
    mm = q1("SELECT * FROM material_metrica WHERE pn=?", (pn,)) or {}
    return jsonify({"meses": linhas, "metricas": mm})

@app.route("/api/material/<pn>/estoque")
@exige("estoque.ver")
def material_estoque(pn):
    m = q1("""SELECT estoque_atual, estoque_min, estoque_med, estoque_max, umb, kanban,
                     lead_time_dias, consumo_med_mes, tipo_reposicao FROM material WHERE pn=?""", (pn,))
    mm = q1("SELECT * FROM material_metrica WHERE pn=?", (pn,)) or {}
    return jsonify({"material": m, "metricas": mm})

@app.route("/api/material/<pn>/compras")
@exige("sap.ver")
def material_compras(pn):
    return jsonify(q("""SELECT ch.*, f.razao_social fornecedor_nome
                        FROM compra_historico ch LEFT JOIN fornecedor f ON f.id=ch.fornecedor_id
                        WHERE ch.pn=? ORDER BY ch.data_documento DESC LIMIT 300""", (pn,)))

@app.route("/api/material/<pn>/timeline")
@exige("sap.ver")
def material_timeline(pn):
    eventos = []
    for r in q("""SELECT ch.*, f.razao_social fornecedor_nome FROM compra_historico ch
                  LEFT JOIN fornecedor f ON f.id=ch.fornecedor_id
                  WHERE ch.pn=? AND ch.data_documento IS NOT NULL
                  ORDER BY ch.data_documento""", (pn,)):
        if r["fonte"] == "ME5A":
            eventos.append({"data": r["data_documento"], "tipo": "Requisição criada",
                            "detalhe": f"RDA {r['requisicao'] or '—'} — {r['quantidade'] or 0:g} un",
                            "doc": r["requisicao"], "valor": r["valor_total"]})
        elif r["fonte"] == "ME2N":
            eventos.append({"data": r["data_documento"], "tipo": "Pedido emitido",
                            "detalhe": f"Pedido {r['pedido'] or '—'} · {r['fornecedor_nome'] or (r['fornecedor_texto'] or '').strip() or '—'}"
                                       + (f" · remessa prevista {r['data_remessa']}" if r["data_remessa"] else ""),
                            "doc": r["pedido"], "valor": r["valor_total"]})
        else:
            movimento = "Entrada de material" if (r["quantidade"] or 0) > 0 else "Saída de material"
            eventos.append({"data": r["data_documento"], "tipo": movimento,
                            "detalhe": f"{abs(r['quantidade'] or 0):g} un"
                                       + (f" · pedido {r['pedido']}" if r["pedido"] else ""),
                            "doc": r["pedido"], "valor": r["valor_total"]})
    eventos.sort(key=lambda e: e["data"], reverse=True)

    # métricas de ciclo: só quando o vínculo requisição↔pedido existe de fato
    ciclos = []
    reqs = {r["requisicao"]: r for r in q("SELECT * FROM compra_historico WHERE pn=? AND fonte='ME5A'", (pn,)) if r["requisicao"]}
    for p_ in q("SELECT * FROM compra_historico WHERE pn=? AND fonte='ME2N'", (pn,)):
        r = reqs.get(p_["requisicao"])
        if r and r["data_documento"] and p_["data_documento"]:
            try:
                d = (datetime.date.fromisoformat(p_["data_documento"]) -
                     datetime.date.fromisoformat(r["data_documento"])).days
                ciclos.append({"tipo": "Requisição → pedido", "dias": d,
                               "ref": f"RDA {r['requisicao']} → pedido {p_['pedido']}"})
            except Exception: pass
        if p_["data_remessa"] and p_["data_documento"]:
            try:
                d = (datetime.date.fromisoformat(p_["data_remessa"]) -
                     datetime.date.fromisoformat(p_["data_documento"])).days
                ciclos.append({"tipo": "Pedido → remessa prevista", "dias": d,
                               "ref": f"Pedido {p_['pedido']}"})
            except Exception: pass
    compras = [e for e in eventos if e["tipo"] == "Pedido emitido"]
    intervalo = None
    if len(compras) > 1:
        datas = sorted(datetime.date.fromisoformat(c["data"]) for c in compras)
        difs = [(datas[i + 1] - datas[i]).days for i in range(len(datas) - 1)]
        intervalo = round(sum(difs) / len(difs))
    return jsonify({"eventos": eventos[:200], "ciclos": ciclos[:20], "intervalo_medio_dias": intervalo,
                    "aviso": "Eventos exibidos conforme o histórico disponível (ME5A, ME2N e MB51). "
                             "Vínculos que o SAP não permite estabelecer com segurança não são inferidos."})

@app.route("/api/material/<pn>/fornecedores")
@exige("fornecedor.ver")
def material_fornecedores(pn):
    linhas = q("""SELECT f.id, f.razao_social nome, f.codigo_sap, f.status,
                    COUNT(*) compras, MAX(ch.data_documento) ultima,
                    ROUND(AVG(ch.preco_unitario),4) preco_medio,
                    ROUND(SUM(ABS(COALESCE(ch.valor_total,0))),2) valor,
                    f.lead_time_dias
                  FROM compra_historico ch JOIN fornecedor f ON f.id=ch.fornecedor_id
                  WHERE ch.pn=? GROUP BY f.id ORDER BY compras DESC""", (pn,))
    total = sum(l["compras"] for l in linhas) or 1
    mm = q1("SELECT ultimo_fornecedor_id FROM material_metrica WHERE pn=?", (pn,)) or {}
    cad = q1("SELECT fornecedor_id FROM material WHERE pn=?", (pn,)) or {}
    for l in linhas:
        l["participacao"] = round(l["compras"] / total * 100, 1)
        l["ultimo_preco"] = escalar("""SELECT preco_unitario FROM compra_historico
            WHERE pn=? AND fornecedor_id=? AND preco_unitario>0
            ORDER BY data_documento DESC LIMIT 1""", (pn, l["id"]))
        l["tags"] = []
        if l["id"] == cad.get("fornecedor_id"): l["tags"].append("Fornecedor cadastrado")
        if l["id"] == mm.get("ultimo_fornecedor_id"): l["tags"].append("Último fornecedor")
        if l["participacao"] >= 50: l["tags"].append("Predominante no histórico")
    categoria = q1("""SELECT c.id, c.nome FROM material m JOIN categoria c ON c.id=m.categoria_id
                      WHERE m.pn=?""", (pn,))
    da_categoria = q("""SELECT ce.email, f.id, f.razao_social nome FROM categoria_email ce
                        LEFT JOIN fornecedor f ON f.id=ce.fornecedor_id
                        WHERE ce.categoria_id=? AND ce.ativo=1""",
                     (categoria["id"],)) if categoria else []
    return jsonify({"historicos": linhas, "categoria": categoria, "da_categoria": da_categoria,
                    "aviso": "Participação histórica não significa melhor fornecedor — é só o volume "
                             "de compras registrado."})

@app.route("/api/material/<pn>/cotacoes")
@exige("cotacao.ver")
def material_cotacoes(pn):
    return jsonify(q("""SELECT p.id, p.numero, p.requisicao, p.status, p.criado_em, p.prazo_resposta,
                          pi.quantidade, pi.um,
                          (SELECT COUNT(*) FROM processo_fornecedor pf WHERE pf.processo_id=p.id) convidados,
                          (SELECT COUNT(*) FROM processo_fornecedor pf WHERE pf.processo_id=p.id
                             AND pf.status='RESPONDIDO') respostas
                        FROM processo_item pi JOIN processo p ON p.id=pi.processo_id
                        WHERE pi.pn=? ORDER BY p.criado_em DESC""", (pn,)))

@app.route("/api/material/<pn>/auditoria")
@exige("material.ver")
def material_auditoria(pn):
    return jsonify(q("""SELECT * FROM auditoria WHERE entidade='material' AND entidade_id=?
                        ORDER BY criado_em DESC LIMIT 100""", (pn,)))

@app.route("/api/material/<pn>/contexto")
@exige("material.ver")
def material_contexto(pn):
    """Painel lateral usado durante a cotação — resumo sem sair da tela."""
    m = q1("""SELECT m.pn, m.descricao, m.umb, m.estoque_atual, m.preco_unitario mm60,
                     m.lead_time_dias, f.razao_social fornecedor_cadastro
              FROM material m LEFT JOIN fornecedor f ON f.id=m.fornecedor_id WHERE m.pn=?""", (pn,))
    if not m: return jsonify({"erro": "Material não encontrado."}), 404
    mm = q1("""SELECT mm.*, f.razao_social ultimo_fornecedor_nome FROM material_metrica mm
               LEFT JOIN fornecedor f ON f.id=mm.ultimo_fornecedor_id WHERE mm.pn=?""", (pn,)) or {}
    return jsonify({"material": m, "metricas": mm})

# ------------------------------------------------- materiais sem fornecedor
@app.route("/api/sem-fornecedor")
@exige("material.ver")
def sem_fornecedor():
    a = request.args
    page = max(1, int(a.get("pagina", 1))); pp = min(100, int(a.get("por_pagina", 25)))
    sql = """
      SELECT m.pn, m.descricao, m.area, m.umb, m.estoque_atual,
             s.fornecedor_id sugerido_id, f.razao_social sugerido_nome,
             s.n compras_sugerido, s.ult ultima_compra, s.total compras_total
      FROM material m
      LEFT JOIN (
        SELECT h.pn, h.fornecedor_id, h.n, h.ult,
               (SELECT SUM(n) FROM (SELECT pn, fornecedor_id, COUNT(*) n FROM compra_historico
                                    WHERE fornecedor_id IS NOT NULL GROUP BY 1,2) t WHERE t.pn=h.pn) total
        FROM (SELECT pn, fornecedor_id, COUNT(*) n, MAX(data_documento) ult
              FROM compra_historico WHERE fornecedor_id IS NOT NULL GROUP BY 1,2) h
        WHERE h.n = (SELECT MAX(n) FROM (SELECT pn, fornecedor_id, COUNT(*) n FROM compra_historico
                     WHERE fornecedor_id IS NOT NULL GROUP BY 1,2) t WHERE t.pn = h.pn)
      ) s ON s.pn = m.pn
      LEFT JOIN fornecedor f ON f.id = s.fornecedor_id
      WHERE m.fornecedor_id IS NULL
        AND (m.origem_dados LIKE '%BASE' OR m.origem_dados LIKE '%Controle')
    """
    p = []
    if a.get("q"): sql += " AND (m.pn LIKE ? OR m.descricao LIKE ?)"; p += [f"%{a['q']}%"] * 2
    if a.get("com_sugestao") == "1": sql += " AND s.fornecedor_id IS NOT NULL"
    r = paginar(sql, p, page, pp, "s.n DESC NULLS LAST, m.pn")
    for l in r["linhas"]:
        if l["sugerido_id"]:
            pct = l["compras_sugerido"] / (l["compras_total"] or l["compras_sugerido"]) * 100
            l["motivo"] = (f"{l['compras_sugerido']} compra(s) encontradas · última em "
                           f"{l['ultima_compra']} · {pct:.0f}% das compras históricas deste PN")
    return jsonify(r)

@app.route("/api/material/<pn>/fornecedor", methods=["POST"])
@exige("vinculo.confirmar")
def confirmar_fornecedor(pn):
    d = request.get_json(force=True)
    fid, acao = d.get("fornecedor_id"), d.get("acao", "confirmar")
    atual = q1("""SELECT m.fornecedor_id, f.razao_social FROM material m
                  LEFT JOIN fornecedor f ON f.id=m.fornecedor_id WHERE m.pn=?""", (pn,))
    if not atual: return jsonify({"erro": "Material não encontrado."}), 404
    if acao == "ignorar":
        auditar("IGNOROU_SUGESTAO", "material", pn,
                {"origem": d.get("origem", "sugestão baseada no histórico SAP"),
                 "justificativa": d.get("justificativa")})
        return jsonify({"ok": True, "mensagem": "Sugestão ignorada e registrada na auditoria."})
    novo = q1("SELECT id, razao_social FROM fornecedor WHERE id=?", (fid,))
    if not novo: return jsonify({"erro": "Fornecedor inválido."}), 400
    g.con.execute("UPDATE material SET fornecedor_id=?, fornecedor_texto=COALESCE(fornecedor_texto,?) WHERE pn=?",
                  (fid, novo["razao_social"], pn))
    g.con.execute("""INSERT INTO material_fornecedor (pn,fornecedor_id,principal,origem,
                     confirmado_por,confirmado_em,observacao)
                     VALUES (?,?,1,?,?,datetime('now'),?)
                     ON CONFLICT(pn,fornecedor_id) DO UPDATE SET principal=1,
                       confirmado_por=excluded.confirmado_por, confirmado_em=excluded.confirmado_em""",
                  (pn, fid, d.get("origem", "HISTORICO_SAP"), g.usuario["id"], d.get("justificativa")))
    g.con.commit()
    auditar("ALTEROU", "material", pn,
            {"campo": "fornecedor principal", "anterior": atual["razao_social"] or "(vazio)",
             "novo": novo["razao_social"],
             "origem": d.get("origem_texto", "sugestão baseada no histórico SAP"),
             "justificativa": d.get("justificativa")})
    return jsonify({"ok": True, "fornecedor": novo["razao_social"]})

# ----------------------------------------------------------------- estoque / preços
@app.route("/api/estoque")
@exige("estoque.ver")
def estoque():
    a = request.args
    visao = a.get("visao", "geral")
    sql = """SELECT m.pn, m.descricao, m.umb, m.area, m.estoque_atual, m.estoque_min, m.estoque_max,
                    mm.consumo_12m/12.0 consumo_mes, mm.cobertura_meses, mm.risco, mm.classe_abc,
                    mm.classe_xyz, mm.ponto_reposicao, mm.ultima_entrada, mm.ultima_saida,
                    m.preco_unitario mm60, ROUND(m.estoque_atual*m.preco_unitario,2) valor_estoque
             FROM material m JOIN material_metrica mm ON mm.pn=m.pn
             WHERE (m.origem_dados LIKE '%BASE' OR m.origem_dados LIKE '%Controle')"""
    p = []
    if visao == "ruptura":  sql += " AND mm.risco IN ('RUPTURA','BAIXO')"
    if visao == "parado":   sql += " AND mm.risco='SEM_MOVIMENTO'"
    if visao == "cobertura": sql += " AND mm.cobertura_meses IS NOT NULL"
    if a.get("q"): sql += " AND (m.pn LIKE ? OR m.descricao LIKE ?)"; p += [f"%{a['q']}%"] * 2
    ordem = {"ruptura": "mm.cobertura_meses ASC", "parado": "valor_estoque DESC",
             "cobertura": "mm.cobertura_meses ASC"}.get(visao, "valor_estoque DESC")
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(200, int(a.get("por_pagina", 50))), ordem + " NULLS LAST"))

@app.route("/api/consumo")
@exige("consumo.ver")
def consumo_geral():
    return jsonify({
        "meses": q("""SELECT ano_mes, ROUND(SUM(quantidade),0) qtd, ROUND(SUM(valor),2) valor
                      FROM material_consumo GROUP BY 1 ORDER BY 1"""),
        "top": q("""SELECT mc.pn, m.descricao, ROUND(SUM(mc.quantidade),0) qtd,
                      ROUND(SUM(mc.valor),2) valor, mm.classe_abc, mm.classe_xyz
                    FROM material_consumo mc LEFT JOIN material m ON m.pn=mc.pn
                    LEFT JOIN material_metrica mm ON mm.pn=mc.pn
                    GROUP BY mc.pn ORDER BY valor DESC LIMIT 100""")})

@app.route("/api/precos")
@exige("preco.ver")
def precos():
    a = request.args
    visao = a.get("visao", "geral")
    sql = """SELECT m.pn, m.descricao, m.umb, m.preco_unitario mm60, mm.ultimo_preco,
                    mm.ultimo_preco_data, mm.media_12m, mm.divergencia_pct, mm.consumo_12m,
                    ROUND(mm.oportunidade_ano,2) oportunidade, mm.escala_suspeita,
                    f.razao_social ultimo_fornecedor, mm.compras_12m
             FROM material_metrica mm JOIN material m ON m.pn=mm.pn
             LEFT JOIN fornecedor f ON f.id=mm.ultimo_fornecedor_id WHERE 1=1"""
    p, ordem = [], "mm.ultimo_preco_data DESC"
    if visao == "divergencias":
        sql += " AND ABS(COALESCE(mm.divergencia_pct,0))>0.30"; ordem = "ABS(mm.divergencia_pct) DESC"
    elif visao == "oportunidades":
        sql += " AND mm.oportunidade_ano>0"; ordem = "mm.oportunidade_ano DESC"
    elif visao == "escala":
        sql += " AND mm.escala_suspeita=1"; ordem = "m.pn"
    else:
        sql += " AND mm.ultimo_preco IS NOT NULL"
    if a.get("q"): sql += " AND (m.pn LIKE ? OR m.descricao LIKE ?)"; p += [f"%{a['q']}%"] * 2
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(200, int(a.get("por_pagina", 50))), ordem + " NULLS LAST"))

# ----------------------------------------------------------------- SAP
@app.route("/api/sap")
@exige("sap.ver")
def sap():
    a = request.args
    sql = """SELECT ch.id, ch.fonte, ch.data_documento, ch.pn, ch.descricao, ch.requisicao,
                    ch.pedido, ch.quantidade, ch.valor_total, ch.preco_unitario, ch.status,
                    ch.requisitante, ch.data_remessa,
                    COALESCE(f.razao_social, ch.fornecedor_texto) fornecedor
             FROM compra_historico ch LEFT JOIN fornecedor f ON f.id=ch.fornecedor_id WHERE 1=1"""
    p = []
    if a.get("q"):
        sql += " AND (ch.pn LIKE ? OR ch.descricao LIKE ? OR ch.pedido LIKE ? OR ch.requisicao LIKE ?)"
        p += [f"%{a['q']}%"] * 4
    if a.get("pn"): sql += " AND ch.pn=?"; p.append(a["pn"])
    if a.get("fornecedor"):
        sql += " AND (f.razao_social LIKE ? OR ch.fornecedor_texto LIKE ?)"; p += [f"%{a['fornecedor']}%"] * 2
    if a.get("tipo"):
        mapa = {"compras": "ME2N", "requisicoes": "ME5A", "movimentacoes": "MB51"}
        sql += " AND ch.fonte=?"; p.append(mapa.get(a["tipo"], a["tipo"]))
    if a.get("de"):  sql += " AND ch.data_documento >= ?"; p.append(a["de"])
    if a.get("ate"): sql += " AND ch.data_documento <= ?"; p.append(a["ate"])
    if a.get("categoria"):
        sql += " AND ch.pn IN (SELECT pn FROM material m JOIN categoria c ON c.id=m.categoria_id WHERE c.nome=?)"
        p.append(a["categoria"])
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(200, int(a.get("por_pagina", 50))), "ch.data_documento DESC NULLS LAST"))

# ----------------------------------------------------------------- fornecedores
@app.route("/api/fornecedores")
@exige("fornecedor.ver")
def fornecedores():
    a = request.args
    sql = """SELECT f.id, f.codigo_sap, f.razao_social, f.tipo, f.status, f.prazo_medio_entrega,
                    f.lead_time_dias, f.ultima_cotacao_em,
                    (SELECT COUNT(*) FROM contato c WHERE c.fornecedor_id=f.id AND c.email IS NOT NULL) emails,
                    (SELECT COUNT(*) FROM compra_historico ch WHERE ch.fornecedor_id=f.id) compras,
                    (SELECT GROUP_CONCAT(c2.nome, ', ') FROM fornecedor_categoria fc
                       JOIN categoria c2 ON c2.id=fc.categoria_id WHERE fc.fornecedor_id=f.id) categorias
             FROM fornecedor f WHERE 1=1"""
    p = []
    if a.get("q"):
        sql += " AND (f.razao_social LIKE ? OR COALESCE(f.codigo_sap,'') LIKE ?)"; p += [f"%{a['q']}%"] * 2
    if a.get("tipo"):   sql += " AND f.tipo=?"; p.append(a["tipo"])
    if a.get("status"): sql += " AND f.status=?"; p.append(a["status"])
    if a.get("sem_email") == "1": sql += " AND NOT EXISTS (SELECT 1 FROM contato c WHERE c.fornecedor_id=f.id AND c.email IS NOT NULL)"
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(200, int(a.get("por_pagina", 50))), "f.razao_social"))

@app.route("/api/fornecedor/<int:fid>")
@exige("fornecedor.ver")
def fornecedor(fid):
    f = q1("SELECT * FROM fornecedor WHERE id=?", (fid,))
    if not f: return jsonify({"erro": "Fornecedor não encontrado."}), 404
    return jsonify({
        "fornecedor": f,
        "contatos": q("SELECT * FROM contato WHERE fornecedor_id=? ORDER BY area, principal DESC", (fid,)),
        "categorias": q("""SELECT c.nome, c.subcategoria FROM fornecedor_categoria fc
                           JOIN categoria c ON c.id=fc.categoria_id WHERE fc.fornecedor_id=?""", (fid,)),
        "incoterms": q("SELECT * FROM incoterm_fornecedor WHERE fornecedor_id=?", (fid,)),
        "materiais": q("""SELECT ch.pn, MAX(ch.descricao) descricao, COUNT(*) compras,
                            MAX(ch.data_documento) ultima, ROUND(AVG(ch.preco_unitario),4) preco_medio
                          FROM compra_historico ch WHERE ch.fornecedor_id=?
                          GROUP BY ch.pn ORDER BY compras DESC LIMIT 100""", (fid,)),
        "lead_times": q("SELECT * FROM lead_time_contratado WHERE fornecedor_id=?", (fid,)),
        "cotacoes": q("""SELECT p.numero, p.status, pf.status status_convite, pf.enviado_em
                         FROM processo_fornecedor pf JOIN processo p ON p.id=pf.processo_id
                         WHERE pf.fornecedor_id=? ORDER BY pf.enviado_em DESC LIMIT 50""", (fid,)),
    })

@app.route("/api/categorias")
@exige()
def categorias():
    return jsonify(q("""SELECT c.id, c.nome, c.subcategoria, c.origem,
                          (SELECT COUNT(*) FROM categoria_email ce WHERE ce.categoria_id=c.id) emails,
                          (SELECT COUNT(*) FROM material m WHERE m.categoria_id=c.id) materiais
                        FROM categoria c ORDER BY c.origem, c.nome"""))

# ----------------------------------------------------------------- pendências
@app.route("/api/pendencias")
@exige("pendencia.ver")
def pendencias():
    a = request.args
    sql = """SELECT p.*, u.nome resolvido_por_nome FROM pendencia p
             LEFT JOIN usuario u ON u.id=p.resolvido_por WHERE 1=1"""
    par = []
    if a.get("status"): sql += " AND p.status=?"; par.append(a["status"])
    else: sql += " AND p.status IN ('ABERTA','EM_ANALISE')"
    if a.get("severidade"): sql += " AND p.severidade=?"; par.append(a["severidade"])
    if a.get("tipo"): sql += " AND p.tipo=?"; par.append(a["tipo"])
    if a.get("q"): sql += " AND (p.registro LIKE ? OR p.problema LIKE ?)"; par += [f"%{a['q']}%"] * 2
    r = paginar(sql, par, max(1, int(a.get("pagina", 1))), min(200, int(a.get("por_pagina", 50))),
                "CASE p.severidade WHEN 'CRITICA' THEN 0 WHEN 'ALTA' THEN 1 WHEN 'MEDIA' THEN 2 ELSE 3 END, p.id")
    r["resumo"] = q("""SELECT severidade, tipo, COUNT(*) n FROM pendencia
                       WHERE status IN ('ABERTA','EM_ANALISE') GROUP BY 1,2 ORDER BY n DESC""")
    return jsonify(r)

@app.route("/api/pendencia/<int:pid>", methods=["POST"])
@exige("pendencia.resolver")
def resolver_pendencia(pid):
    d = request.get_json(force=True)
    p = q1("SELECT * FROM pendencia WHERE id=?", (pid,))
    if not p: return jsonify({"erro": "Pendência não encontrada."}), 404
    novo_status = d.get("status", "RESOLVIDA")
    if novo_status not in ("EM_ANALISE", "RESOLVIDA", "IGNORADA", "ABERTA"):
        return jsonify({"erro": "Status inválido."}), 400
    if novo_status in ("IGNORADA",) and not d.get("justificativa"):
        return jsonify({"erro": "Justificativa obrigatória para ignorar uma pendência."}), 400
    g.con.execute("""UPDATE pendencia SET status=?, resolvido_por=?, resolvido_em=datetime('now'),
                     justificativa=?, valor_anterior=?, valor_novo=? WHERE id=?""",
                  (novo_status, g.usuario["id"], d.get("justificativa"),
                   d.get("valor_anterior") or p["problema"], d.get("valor_novo"), pid))
    g.con.commit()
    auditar("RESOLVEU" if novo_status == "RESOLVIDA" else novo_status, "pendencia", pid,
            {"tipo": p["tipo"], "registro": p["registro"], "status_anterior": p["status"],
             "status_novo": novo_status, "justificativa": d.get("justificativa"),
             "valor_anterior": d.get("valor_anterior"), "valor_novo": d.get("valor_novo")})
    return jsonify({"ok": True})

# ----------------------------------------------------------------- auditoria
@app.route("/api/auditoria")
@exige("auditoria.ver")
def auditoria_lista():
    a = request.args
    sql = "SELECT * FROM auditoria WHERE 1=1"; p = []
    if a.get("entidade"): sql += " AND entidade=?"; p.append(a["entidade"])
    if a.get("usuario"): sql += " AND usuario_email LIKE ?"; p.append(f"%{a['usuario']}%")
    if a.get("q"): sql += " AND (entidade_id LIKE ? OR COALESCE(detalhe,'') LIKE ?)"; p += [f"%{a['q']}%"] * 2
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(200, int(a.get("por_pagina", 50))), "criado_em DESC"))

# ----------------------------------------------------------------- cotações
def proximo_numero():
    ano = datetime.date.today().year
    n = escalar("SELECT COUNT(*) FROM processo WHERE numero LIKE ?", (f"COT-{ano}-%",)) or 0
    return f"COT-{ano}-{n + 1:04d}"

@app.route("/api/cotacoes")
@exige("cotacao.ver")
def cotacoes():
    a = request.args
    sql = """SELECT p.*, u.nome comprador,
               (SELECT COUNT(*) FROM processo_item pi WHERE pi.processo_id=p.id) itens,
               (SELECT COUNT(*) FROM processo_fornecedor pf WHERE pf.processo_id=p.id) convidados,
               (SELECT COUNT(*) FROM processo_fornecedor pf WHERE pf.processo_id=p.id AND pf.status='RESPONDIDO') respostas
             FROM processo p LEFT JOIN usuario u ON u.id=p.comprador_id WHERE 1=1"""
    p = []
    grupo = a.get("grupo")
    if grupo == "andamento": sql += " AND p.status IN ('RASCUNHO','EM_APROVACAO','ENVIADO','EM_NEGOCIACAO')"
    elif grupo == "aguardando": sql += " AND p.status IN ('ENVIADO','AGUARDANDO')"
    elif grupo == "finalizadas": sql += " AND p.status IN ('FINALIZADO','CANCELADO')"
    if a.get("q"): sql += " AND (p.numero LIKE ? OR COALESCE(p.requisicao,'') LIKE ?)"; p += [f"%{a['q']}%"] * 2
    return jsonify(paginar(sql, p, max(1, int(a.get("pagina", 1))),
                           min(100, int(a.get("por_pagina", 25))), "p.criado_em DESC"))

@app.route("/api/cotacoes/sugestao/<pn>")
@exige("cotacao.criar")
def sugestao_fornecedores(pn):
    """Sugere fornecedores com o motivo explícito — histórico primeiro, categoria depois."""
    sug = []
    for l in q("""SELECT f.id, f.razao_social nome, COUNT(*) compras, MAX(ch.data_documento) ultima,
                    (SELECT c.email FROM contato c WHERE c.fornecedor_id=f.id AND c.email IS NOT NULL
                      ORDER BY c.principal DESC, c.id LIMIT 1) email
                  FROM compra_historico ch JOIN fornecedor f ON f.id=ch.fornecedor_id
                  WHERE ch.pn=? GROUP BY f.id ORDER BY compras DESC LIMIT 6""", (pn,)):
        if not l["email"]: continue
        meses = ""
        if l["ultima"]:
            try:
                d = (datetime.date.today() - datetime.date.fromisoformat(l["ultima"])).days
                meses = f"última compra há {d // 30} mês(es)" if d >= 30 else f"última compra há {d} dia(s)"
            except Exception: pass
        sug.append({"fornecedor_id": l["id"], "nome": l["nome"], "email": l["email"],
                    "motivo": f"{l['compras']} compra(s) anteriores deste PN" + (f" · {meses}" if meses else ""),
                    "marcado": True, "origem": "HISTORICO"})
    vistos = {s["email"] for s in sug}
    for l in q("""SELECT ce.email, f.id, f.razao_social nome, c.nome categoria
                  FROM material m JOIN categoria c ON c.id=m.categoria_id
                  JOIN categoria_email ce ON ce.categoria_id=c.id
                  LEFT JOIN fornecedor f ON f.id=ce.fornecedor_id
                  WHERE m.pn=? AND ce.ativo=1""", (pn,)):
        if l["email"] in vistos: continue
        sug.append({"fornecedor_id": l["id"], "nome": l["nome"] or l["email"], "email": l["email"],
                    "motivo": f"atende à categoria {l['categoria']}", "marcado": False,
                    "origem": "CATEGORIA"})
    return jsonify({"sugestoes": sug})

@app.route("/api/cotacoes", methods=["POST"])
@exige("cotacao.criar")
def criar_cotacao():
    d = request.get_json(force=True)
    itens = d.get("itens") or []
    if not itens: return jsonify({"erro": "Informe ao menos um item."}), 400
    numero = proximo_numero()
    cur = g.con.cursor()
    cur.execute("""INSERT INTO processo (numero,requisicao,titulo,status,comprador_id,
                   prazo_resposta,observacoes) VALUES (?,?,?,'RASCUNHO',?,?,?)""",
                (numero, d.get("requisicao"), d.get("titulo") or f"Cotação {numero}",
                 g.usuario["id"], d.get("prazo_resposta"), d.get("observacoes")))
    pid = cur.lastrowid
    for i, it in enumerate(itens, 1):
        m = q1("SELECT descricao, umb, categoria_id FROM material WHERE pn=?", (it.get("pn"),)) or {}
        cur.execute("""INSERT INTO processo_item (processo_id,linha,pn,descricao,quantidade,um,
                       categoria_id,classificado_por) VALUES (?,?,?,?,?,?,?,?)""",
                    (pid, i, it.get("pn"), it.get("descricao") or m.get("descricao"),
                     it.get("quantidade"), it.get("um") or m.get("umb"),
                     m.get("categoria_id"), "CADASTRO"))
    for f in d.get("fornecedores") or []:
        cur.execute("""INSERT OR IGNORE INTO processo_fornecedor (processo_id,fornecedor_id,email,
                       motivo_convite) VALUES (?,?,?,?)""",
                    (pid, f.get("fornecedor_id"), f.get("email"), f.get("motivo")))
    g.con.commit()
    auditar("CRIOU", "processo", pid, {"numero": numero, "itens": len(itens),
                                       "convidados": len(d.get("fornecedores") or [])})
    return jsonify({"id": pid, "numero": numero})

@app.route("/api/cotacao/<int:pid>")
@exige("cotacao.ver")
def cotacao(pid):
    p = q1("""SELECT p.*, u.nome comprador FROM processo p
              LEFT JOIN usuario u ON u.id=p.comprador_id WHERE p.id=?""", (pid,))
    if not p: return jsonify({"erro": "Cotação não encontrada."}), 404
    itens = q("SELECT * FROM processo_item WHERE processo_id=? ORDER BY linha", (pid,))
    forns = q("""SELECT pf.*, f.razao_social nome FROM processo_fornecedor pf
                 LEFT JOIN fornecedor f ON f.id=pf.fornecedor_id WHERE pf.processo_id=?""", (pid,))
    respostas = q("""SELECT r.*, pf.email FROM cotacao_resposta r
                     JOIN processo_fornecedor pf ON pf.id=r.processo_fornecedor_id
                     WHERE pf.processo_id=?""", (pid,))
    return jsonify({"processo": p, "itens": itens, "fornecedores": forns, "respostas": respostas,
                    "emails": q("SELECT * FROM email_enviado WHERE processo_id=? ORDER BY enviado_em DESC", (pid,))})

@app.route("/api/cotacao/<int:pid>/status", methods=["POST"])
@exige("cotacao.ver")
def cotacao_status(pid):
    d = request.get_json(force=True)
    novo = d.get("status")
    validos = ("RASCUNHO", "EM_APROVACAO", "ENVIADO", "AGUARDANDO", "RESPONDIDO",
               "EM_NEGOCIACAO", "FINALIZADO", "CANCELADO")
    if novo not in validos: return jsonify({"erro": "Status inválido."}), 400
    if novo in ("EM_APROVACAO", "FINALIZADO") and not pode(g.usuario["perfil"], "cotacao.criar"):
        return jsonify({"erro": "Sem permissão para mudar este status."}), 403
    ant = escalar("SELECT status FROM processo WHERE id=?", (pid,))
    g.con.execute("UPDATE processo SET status=?, finalizado_em=CASE WHEN ?='FINALIZADO' "
                  "THEN datetime('now') ELSE finalizado_em END WHERE id=?", (novo, novo, pid))
    g.con.commit()
    auditar("ALTEROU", "processo", pid, {"campo": "status", "anterior": ant, "novo": novo})
    return jsonify({"ok": True})

@app.route("/api/cotacao/<int:pid>/resposta", methods=["POST"])
@exige("cotacao.ver")
def registrar_resposta(pid):
    d = request.get_json(force=True)
    preco, qtd = d.get("preco_unitario"), d.get("quantidade") or 0
    total = (preco or 0) * (qtd or 0) + (d.get("frete") or 0) + (d.get("impostos") or 0)
    g.con.execute("""INSERT INTO cotacao_resposta (processo_item_id,processo_fornecedor_id,
        preco_unitario,impostos,frete,lead_time_dias,condicao_pagamento,incoterm,validade,moq,total,observacao)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(processo_item_id,processo_fornecedor_id) DO UPDATE SET
          preco_unitario=excluded.preco_unitario, impostos=excluded.impostos, frete=excluded.frete,
          lead_time_dias=excluded.lead_time_dias, condicao_pagamento=excluded.condicao_pagamento,
          incoterm=excluded.incoterm, validade=excluded.validade, moq=excluded.moq, total=excluded.total""",
        (d["processo_item_id"], d["processo_fornecedor_id"], preco, d.get("impostos"), d.get("frete"),
         d.get("lead_time_dias"), d.get("condicao_pagamento"), d.get("incoterm"), d.get("validade"),
         d.get("moq"), total, d.get("observacao")))
    g.con.execute("""UPDATE processo_fornecedor SET status='RESPONDIDO', respondido_em=datetime('now')
                     WHERE id=?""", (d["processo_fornecedor_id"],))
    g.con.commit()
    auditar("REGISTROU_RESPOSTA", "processo", pid, {"item": d["processo_item_id"],
                                                    "fornecedor": d["processo_fornecedor_id"],
                                                    "preco": preco})
    return jsonify({"ok": True})

@app.route("/api/cotacao/<int:pid>/mapa")
@exige("cotacao.ver")
def mapa_cotacao(pid):
    itens = q("SELECT * FROM processo_item WHERE processo_id=? ORDER BY linha", (pid,))
    forns = q("""SELECT pf.id, pf.email, COALESCE(f.razao_social, pf.email) nome, pf.status
                 FROM processo_fornecedor pf LEFT JOIN fornecedor f ON f.id=pf.fornecedor_id
                 WHERE pf.processo_id=?""", (pid,))
    resp = {(r["processo_item_id"], r["processo_fornecedor_id"]): r for r in
            q("""SELECT r.* FROM cotacao_resposta r JOIN processo_fornecedor pf
                 ON pf.id=r.processo_fornecedor_id WHERE pf.processo_id=?""", (pid,))}
    linhas = []
    for it in itens:
        ctx = q1("""SELECT mm.ultimo_preco, mm.media_12m, m.preco_unitario mm60,
                      mm.ultimo_preco_data FROM material m LEFT JOIN material_metrica mm ON mm.pn=m.pn
                    WHERE m.pn=?""", (it["pn"],)) or {}
        celulas = []
        for f in forns:
            r = resp.get((it["id"], f["id"]))
            celulas.append({"fornecedor_id": f["id"],
                            "preco": r["preco_unitario"] if r else None,
                            "total": r["total"] if r else None,
                            "lead_time": r["lead_time_dias"] if r else None,
                            "condicao": r["condicao_pagamento"] if r else None,
                            "escolhido": bool(r and r["escolhido"])})
        precos = [c["preco"] for c in celulas if c["preco"]]
        menor = min(precos) if precos else None
        for c in celulas: c["menor"] = (c["preco"] is not None and c["preco"] == menor)
        linhas.append({"item": it, "contexto": ctx, "celulas": celulas, "menor_preco": menor})
    return jsonify({"fornecedores": forns, "linhas": linhas})

# --- envio de e-mail (SMTP corporativo) ---------------------------------
def montar_email(itens, proc, solicitante):
    linhas = [f"{i+1:>2}. {it['pn'] or ''} | {it['descricao'] or ''} | Qtde: {it['quantidade'] or ''} {it['um'] or ''}"
              for i, it in enumerate(itens)]
    return f"""Prezado(a) fornecedor,

Solicitamos cotação para os itens abaixo, referente ao processo {proc['numero']}
{('(requisição ' + proc['requisicao'] + ')') if proc.get('requisicao') else ''}.

{chr(10).join(linhas)}

Favor retornar com:
  - Preço unitário (BRL) e condição de pagamento
  - Prazo de entrega (lead time) e MOQ
  - Incoterm / frete
  - Validade da proposta

Prazo para retorno: {proc.get('prazo_resposta') or 'a combinar'}
{('Observações: ' + proc['observacoes']) if proc.get('observacoes') else ''}

Atenciosamente,
{solicitante}
Compras — {config.ORG_NOME}
"""

@app.route("/api/cotacoes/enviar", methods=["POST"])
@exige("cotacao.enviar")
def enviar_cotacao():
    d = request.get_json(force=True)
    pid = d.get("processo_id")
    proc = q1("SELECT * FROM processo WHERE id=?", (pid,))
    if not proc: return jsonify({"erro": "Cotação não encontrada."}), 404
    itens = q("SELECT * FROM processo_item WHERE processo_id=? ORDER BY linha", (pid,))
    convidados = q("SELECT * FROM processo_fornecedor WHERE processo_id=?", (pid,))
    if not convidados: return jsonify({"erro": "Nenhum fornecedor convidado."}), 400
    corpo = montar_email(itens, proc, q1("SELECT nome FROM usuario WHERE id=?", (g.usuario["id"],))["nome"])
    assunto = f"Solicitação de Cotação {proc['numero']}" + (f" — {proc['requisicao']}" if proc["requisicao"] else "")
    servidor, resultados = None, []
    try:
        if not DRY_RUN:
            host, porta = os.environ.get("SMTP_HOST", ""), int(os.environ.get("SMTP_PORT", "587"))
            servidor = smtplib.SMTP(host, porta, timeout=30)
            if os.environ.get("SMTP_TLS", "starttls") == "starttls":
                servidor.starttls(context=ssl.create_default_context())
            if os.environ.get("SMTP_USER"):
                servidor.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
        for c in convidados:
            status, detalhe = "SIMULADO", None
            if not DRY_RUN:
                try:
                    msg = EmailMessage()
                    msg["Subject"] = assunto
                    msg["From"] = os.environ.get("MAIL_FROM", os.environ.get("SMTP_USER", ""))
                    msg["To"] = c["email"]
                    msg.set_content(corpo)
                    servidor.send_message(msg); status = "ENVIADO"
                except Exception as ex:
                    status, detalhe = "ERRO", str(ex)
            g.con.execute("""INSERT INTO email_enviado (processo_id,processo_fornecedor_id,destinatario,
                             assunto,corpo,status,detalhe) VALUES (?,?,?,?,?,?,?)""",
                          (pid, c["id"], c["email"], assunto, corpo, status, detalhe))
            if status != "ERRO":
                g.con.execute("UPDATE processo_fornecedor SET status='ENVIADO', enviado_em=datetime('now') WHERE id=?",
                              (c["id"],))
                if c["fornecedor_id"]:
                    g.con.execute("UPDATE fornecedor SET ultima_cotacao_em=date('now') WHERE id=?", (c["fornecedor_id"],))
            resultados.append({"email": c["email"], "status": status, "detalhe": detalhe})
    finally:
        if servidor:
            try: servidor.quit()
            except Exception: pass
    g.con.execute("UPDATE processo SET status='ENVIADO', enviado_em=datetime('now') WHERE id=?", (pid,))
    g.con.commit()
    auditar("ENVIOU", "processo", pid, {"numero": proc["numero"], "destinatarios": len(convidados),
                                        "modo": "simulação" if DRY_RUN else "SMTP"})
    return jsonify({"resultados": resultados, "dry_run": DRY_RUN})

@app.route("/api/senha", methods=["POST"])
def trocar_senha():
    """Troca a própria senha. Exigida no primeiro acesso de cada conta criada.

    Não usa @exige porque precisa funcionar justamente quando a conta está com
    troca pendente — que é o estado em que todo o resto da API está bloqueado.
    """
    if not g.get("usuario"):
        return jsonify({"erro": "Sessão expirada. Faça login novamente."}), 401
    if request.headers.get("X-CSRF") != g.usuario["csrf"]:
        return jsonify({"erro": "Falha na validação CSRF."}), 403

    d = request.get_json(force=True)
    u = q1("SELECT * FROM usuario WHERE id=?", (g.usuario["id"],))
    if not auth.confere_senha(d.get("senha_atual", ""), u["senha_hash"]):
        return jsonify({"erro": "Senha atual incorreta."}), 401

    nova = d.get("senha_nova", "")
    motivo = auth.validar_senha(nova, u["email"])
    if motivo:
        return jsonify({"erro": motivo}), 400
    if auth.confere_senha(nova, u["senha_hash"]):
        return jsonify({"erro": "A nova senha precisa ser diferente da atual."}), 400

    auditar("TROCOU_SENHA", "usuario", u["id"], {"email": u["email"]})
    auth.trocar_senha(g.con, u["id"], nova)
    resp = make_response(jsonify({"ok": True, "mensagem": "Senha alterada. Entre novamente."}))
    resp.delete_cookie("sessao")
    return resp


@app.route("/healthz")
def healthz():
    """Liveness: o processo responde. Usado pelo Docker/orquestrador."""
    return jsonify({"status": "ok", "versao": config.VERSAO})


@app.route("/readyz")
def readyz():
    """Readiness: o banco responde e tem as migrações esperadas."""
    try:
        materiais = escalar("SELECT COUNT(*) FROM material")
        migracoes = escalar("SELECT COUNT(*) FROM schema_migracao")
    except sqlite3.Error as e:
        return jsonify({"status": "indisponivel", "erro": str(e)}), 503
    return jsonify({"status": "ok", "materiais": materiais, "migracoes": migracoes,
                    "ambiente": config.AMBIENTE})


# ----------------------------------------------------------------- administração
@app.route("/api/usuarios", methods=["GET", "POST"])
@exige("*")
def usuarios():
    if request.method == "POST":
        d = request.get_json(force=True)
        if d.get("id"):
            g.con.execute("UPDATE usuario SET nome=?, perfil=?, ativo=? WHERE id=?",
                          (d["nome"], d["perfil"], 1 if d.get("ativo", True) else 0, d["id"]))
            acao, alvo = "ALTEROU", d["id"]
        else:
            motivo = auth.validar_senha(d.get("senha", ""), d.get("email", ""))
            if motivo:
                return jsonify({"erro": motivo}), 400
            cur = g.con.cursor()
            cur.execute("""INSERT INTO usuario (email,nome,perfil,senha_hash,tenant_id,forcar_troca_senha)
                           VALUES (?,?,?,?,?,1)""",
                        (d["email"].lower(), d["nome"], d["perfil"],
                         auth.hash_senha(d["senha"]), g.tenant_id))
            acao, alvo = "CRIOU", cur.lastrowid
        g.con.commit()
        auditar(acao, "usuario", alvo, {"email": d.get("email"), "perfil": d.get("perfil")})
        return jsonify({"ok": True})
    return jsonify(q("SELECT id,email,nome,perfil,ativo,ultimo_acesso FROM usuario ORDER BY nome"))

@app.route("/api/config")
def configuracao():
    return jsonify(config.resumo())

# Em produção a checagem roda na importação, porque sob gunicorn ninguém passa
# pelo __main__. Falhar no boot é melhor do que servir com configuração insegura.
if config.PRODUCAO:
    config.exigir_config_valida()

if __name__ == "__main__":
    if not config.PRODUCAO:
        for p in config.validar():
            print(f"aviso: {p}")
    print(f"portal em http://localhost:{config.PORT}  ({config.AMBIENTE}, "
          f"{'envio simulado' if config.DRY_RUN else 'ENVIO REAL DE E-MAIL'})")
    app.run(host="0.0.0.0", port=config.PORT, debug=False, threaded=True)
