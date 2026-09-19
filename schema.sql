-- =====================================================================
-- Portal de Gestão de Cotações
-- Esquema centrado no PROCESSO DE COTAÇÃO.
-- Blocos: (A) mestres de fornecedor  (B) mestres de material
--         (C) histórico SAP          (D) processo de cotação
--         (E) usuários e auditoria
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------- (A) FORNECEDORES ----------
CREATE TABLE fornecedor (
  id              INTEGER PRIMARY KEY,
  codigo_sap      TEXT UNIQUE,
  razao_social    TEXT NOT NULL,
  nome_norm       TEXT NOT NULL,              -- normalizado p/ deduplicação
  nome_fantasia   TEXT,
  cnpj            TEXT,
  tipo            TEXT CHECK (tipo IN ('DIRETO','INDIRETO','AMBOS')),
  status          TEXT NOT NULL DEFAULT 'ATIVO'
                  CHECK (status IN ('ATIVO','BLOQUEADO','HOMOLOGADO','EM_AVALIACAO','INATIVO')),
  prazo_medio_entrega TEXT,
  lead_time_dias  INTEGER,
  cidade          TEXT,
  uf              TEXT,
  telefone        TEXT,
  condicao_pagamento TEXT,
  observacoes     TEXT,
  origem_dados    TEXT,                       -- planilha/aba de origem
  ultima_cotacao_em TEXT,
  criado_em       TEXT DEFAULT (datetime('now')),
  atualizado_em   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX ix_forn_nome ON fornecedor(nome_norm);

CREATE TABLE contato (
  id            INTEGER PRIMARY KEY,
  fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id) ON DELETE CASCADE,
  area          TEXT NOT NULL,                -- COMERCIAL, QUALIDADE, LOGISTICA, ...
  nome          TEXT,
  telefone      TEXT,
  email         TEXT,
  principal     INTEGER NOT NULL DEFAULT 0,
  ativo         INTEGER NOT NULL DEFAULT 1,
  origem_dados  TEXT
);
CREATE INDEX ix_contato_email ON contato(email);
CREATE INDEX ix_contato_forn  ON contato(fornecedor_id);

CREATE TABLE categoria (
  id           INTEGER PRIMARY KEY,
  nome         TEXT NOT NULL UNIQUE,
  subcategoria TEXT,
  origem       TEXT,          -- CLASSIFICACAO (tem e-mails de cotação) | CADASTRO
  ativo        INTEGER NOT NULL DEFAULT 1
);

-- e-mails de cotação por categoria (aba "Classificação - Fornecedores")
CREATE TABLE categoria_email (
  id            INTEGER PRIMARY KEY,
  categoria_id  INTEGER NOT NULL REFERENCES categoria(id) ON DELETE CASCADE,
  email         TEXT NOT NULL,
  fornecedor_id INTEGER REFERENCES fornecedor(id),   -- NULL = não identificado no cadastro
  ordem         INTEGER,
  ativo         INTEGER NOT NULL DEFAULT 1,
  UNIQUE (categoria_id, email)
);

-- categorias atendidas por fornecedor (n:n)
CREATE TABLE fornecedor_categoria (
  fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id) ON DELETE CASCADE,
  categoria_id  INTEGER NOT NULL REFERENCES categoria(id) ON DELETE CASCADE,
  origem        TEXT,
  PRIMARY KEY (fornecedor_id, categoria_id)
);

CREATE TABLE incoterm_fornecedor (
  id            INTEGER PRIMARY KEY,
  fornecedor_id INTEGER REFERENCES fornecedor(id),
  codigo_sap    TEXT,
  descricao     TEXT,
  origem        TEXT,           -- National / Import / Indirect
  impacto_fx    TEXT,
  commodity     TEXT,
  nova_categoria TEXT,
  incoterm      TEXT
);

-- ---------- (B) MATERIAIS ----------
CREATE TABLE material (
  pn                TEXT PRIMARY KEY,
  descricao         TEXT,
  tipo              TEXT,
  umb               TEXT,
  area              TEXT,
  origem            TEXT,
  tipo_material     TEXT,
  grupo_mercadorias TEXT,
  grupo_compradores TEXT,
  tipo_reposicao    TEXT,
  lead_time_dias    INTEGER,
  estoque_min       REAL,
  estoque_med       REAL,
  estoque_max       REAL,
  consumo_med_mes   REAL,
  estoque_atual     REAL,
  cobertura_meses   REAL,
  kanban            TEXT,
  pedido_atual      TEXT,
  preco_unitario    REAL,
  moeda             TEXT,
  preco_atualizado_em TEXT,
  fornecedor_texto  TEXT,       -- nome do fornecedor como consta na planilha
  fornecedor_id     INTEGER REFERENCES fornecedor(id),
  categoria_id      INTEGER REFERENCES categoria(id),
  categoria_confianca REAL,     -- 0-1, quão segura foi a classificação automática
  categoria_origem  TEXT,        -- AUTO | MANUAL | HISTORICO
  origem_dados      TEXT
);
CREATE INDEX ix_mat_forn ON material(fornecedor_id);
CREATE INDEX ix_mat_desc ON material(descricao);

CREATE TABLE material_consumo (
  pn         TEXT NOT NULL,
  ano_mes    TEXT NOT NULL,      -- AAAA-MM
  quantidade REAL,
  valor      REAL,
  PRIMARY KEY (pn, ano_mes)
);

-- ---------- (C) HISTÓRICO SAP ----------
CREATE TABLE compra_historico (
  id              INTEGER PRIMARY KEY,
  fonte           TEXT NOT NULL,          -- ME2N / ME5A / MB51
  pn              TEXT,
  descricao       TEXT,
  requisicao      TEXT,
  pedido          TEXT,
  fornecedor_codigo TEXT,
  fornecedor_texto  TEXT,
  fornecedor_id   INTEGER REFERENCES fornecedor(id),
  data_documento  TEXT,
  data_remessa    TEXT,
  quantidade      REAL,
  a_fornecer      REAL,
  valor_total     REAL,
  moeda           TEXT DEFAULT 'BRL',
  preco_unitario  REAL,
  status          TEXT,
  requisitante    TEXT,
  tipo_material   TEXT
);
CREATE INDEX ix_ch_pn   ON compra_historico(pn);
CREATE INDEX ix_ch_forn ON compra_historico(fornecedor_id);
CREATE INDEX ix_ch_data ON compra_historico(data_documento);

CREATE TABLE lead_time_contratado (
  id              INTEGER PRIMARY KEY,
  fornecedor_codigo TEXT,
  fornecedor_id   INTEGER REFERENCES fornecedor(id),
  documento       TEXT,
  data_documento  TEXT,
  contato_comercial TEXT,
  lead_time       TEXT
);

-- ---------- (D) PROCESSO DE COTAÇÃO ----------
CREATE TABLE processo (
  id             INTEGER PRIMARY KEY,
  numero         TEXT NOT NULL UNIQUE,        -- COT-2026-0001
  requisicao     TEXT,                        -- RDA / ReqC
  titulo         TEXT,
  status         TEXT NOT NULL DEFAULT 'RASCUNHO'
                 CHECK (status IN ('RASCUNHO','EM_APROVACAO','ENVIADO','AGUARDANDO',
                                   'RESPONDIDO','EM_NEGOCIACAO','FINALIZADO','CANCELADO')),
  comprador_id   INTEGER REFERENCES usuario(id),
  solicitante_id INTEGER REFERENCES usuario(id),
  aprovador_id   INTEGER REFERENCES usuario(id),
  prazo_resposta TEXT,                        -- data/hora
  observacoes    TEXT,
  valor_estimado REAL,
  criado_em      TEXT DEFAULT (datetime('now')),
  enviado_em     TEXT,
  finalizado_em  TEXT
);
CREATE INDEX ix_proc_status ON processo(status);
CREATE INDEX ix_proc_req    ON processo(requisicao);

CREATE TABLE processo_item (
  id           INTEGER PRIMARY KEY,
  processo_id  INTEGER NOT NULL REFERENCES processo(id) ON DELETE CASCADE,
  linha        INTEGER,
  pn           TEXT,
  descricao    TEXT,
  quantidade   REAL,
  um           TEXT,
  categoria_id INTEGER REFERENCES categoria(id),
  confianca    REAL,                          -- índice de confiança da classificação
  classificado_por TEXT,                      -- AUTO / MANUAL / HISTORICO
  observacao   TEXT
);

CREATE TABLE processo_fornecedor (
  id            INTEGER PRIMARY KEY,
  processo_id   INTEGER NOT NULL REFERENCES processo(id) ON DELETE CASCADE,
  fornecedor_id INTEGER REFERENCES fornecedor(id),
  email         TEXT NOT NULL,
  motivo_convite TEXT,                        -- por que foi sugerido
  status        TEXT NOT NULL DEFAULT 'CONVIDADO'
                CHECK (status IN ('CONVIDADO','ENVIADO','ERRO','RESPONDIDO','RECUSOU','SEM_RESPOSTA')),
  enviado_em    TEXT,
  respondido_em TEXT,
  lembretes     INTEGER NOT NULL DEFAULT 0,
  UNIQUE (processo_id, email)
);

CREATE TABLE cotacao_resposta (
  id              INTEGER PRIMARY KEY,
  processo_item_id INTEGER NOT NULL REFERENCES processo_item(id) ON DELETE CASCADE,
  processo_fornecedor_id INTEGER NOT NULL REFERENCES processo_fornecedor(id) ON DELETE CASCADE,
  preco_unitario  REAL,
  moeda           TEXT DEFAULT 'BRL',
  impostos        REAL,
  frete           REAL,
  lead_time_dias  INTEGER,
  condicao_pagamento TEXT,
  incoterm        TEXT,
  validade        TEXT,
  moq             REAL,
  total           REAL,
  escolhido       INTEGER NOT NULL DEFAULT 0,
  observacao      TEXT,
  registrado_em   TEXT DEFAULT (datetime('now')),
  UNIQUE (processo_item_id, processo_fornecedor_id)
);

CREATE TABLE anexo (
  id          INTEGER PRIMARY KEY,
  processo_id INTEGER NOT NULL REFERENCES processo(id) ON DELETE CASCADE,
  nome        TEXT NOT NULL,
  caminho     TEXT NOT NULL,
  mime        TEXT,
  tamanho     INTEGER,
  anexar_email INTEGER NOT NULL DEFAULT 1,
  enviado_em  TEXT
);

CREATE TABLE email_enviado (
  id          INTEGER PRIMARY KEY,
  processo_id INTEGER REFERENCES processo(id) ON DELETE CASCADE,
  processo_fornecedor_id INTEGER REFERENCES processo_fornecedor(id),
  destinatario TEXT NOT NULL,
  assunto     TEXT,
  corpo       TEXT,
  tipo        TEXT DEFAULT 'COTACAO',         -- COTACAO / LEMBRETE
  status      TEXT,                            -- ENVIADO / ERRO / SIMULADO
  detalhe     TEXT,
  enviado_em  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE template_email (
  id         INTEGER PRIMARY KEY,
  nome       TEXT NOT NULL UNIQUE,
  categoria_id INTEGER REFERENCES categoria(id),
  assunto    TEXT NOT NULL,
  corpo      TEXT NOT NULL,
  padrao     INTEGER NOT NULL DEFAULT 0
);

-- PN -> categoria -> fornecedores aprendido com as correções do comprador
CREATE TABLE aprendizado_classificacao (
  id           INTEGER PRIMARY KEY,
  pn           TEXT,
  descricao_norm TEXT,
  categoria_id INTEGER NOT NULL REFERENCES categoria(id),
  usuario_id   INTEGER REFERENCES usuario(id),
  peso         INTEGER NOT NULL DEFAULT 1,
  criado_em    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX ix_apr_pn ON aprendizado_classificacao(pn);

-- ---------- (E) USUÁRIOS E AUDITORIA ----------
CREATE TABLE usuario (
  id           INTEGER PRIMARY KEY,
  email        TEXT NOT NULL UNIQUE,
  nome         TEXT NOT NULL,
  perfil       TEXT NOT NULL DEFAULT 'SOLICITANTE'
               CHECK (perfil IN ('SOLICITANTE','COMPRADOR','GESTOR','ADMIN')),
  senha_hash   TEXT,                 -- login local
  entra_oid    TEXT UNIQUE,          -- object id do Entra ID (login corporativo)
  ativo        INTEGER NOT NULL DEFAULT 1,
  ultimo_acesso TEXT,
  criado_em    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE auditoria (
  id         INTEGER PRIMARY KEY,
  usuario_id INTEGER REFERENCES usuario(id),
  usuario_email TEXT,
  acao       TEXT NOT NULL,          -- CRIOU / ALTEROU / APROVOU / ENVIOU / EXCLUIU
  entidade   TEXT NOT NULL,          -- processo / fornecedor / usuario ...
  entidade_id TEXT,
  detalhe    TEXT,                   -- JSON com o antes/depois (mascarado)
  ip         TEXT,
  criado_em  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX ix_aud_entidade ON auditoria(entidade, entidade_id);

-- ---------- VIEWS de apoio ----------
CREATE VIEW vw_ultimo_preco AS
SELECT pn,
       MAX(data_documento)                        AS data_ultima_compra,
       (SELECT c2.preco_unitario FROM compra_historico c2
         WHERE c2.pn = c1.pn AND c2.preco_unitario IS NOT NULL
         ORDER BY c2.data_documento DESC LIMIT 1)  AS ultimo_preco_unitario,
       (SELECT c3.fornecedor_texto FROM compra_historico c3
         WHERE c3.pn = c1.pn ORDER BY c3.data_documento DESC LIMIT 1) AS ultimo_fornecedor
FROM compra_historico c1
GROUP BY pn;

CREATE VIEW vw_fornecedor_contatos AS
SELECT f.id, f.codigo_sap, f.razao_social, f.tipo, f.status,
       GROUP_CONCAT(DISTINCT c.email) AS emails
FROM fornecedor f LEFT JOIN contato c ON c.fornecedor_id = f.id AND c.email IS NOT NULL
GROUP BY f.id;
