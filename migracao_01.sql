-- @ja-aplicada-se: SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='material_metrica'
-- Migração 01: módulo Almoxarifado e Inteligência de Materiais
-- Só acrescenta; nenhuma tabela existente é recriada e nenhum dado importado é perdido.
PRAGMA foreign_keys = ON;

-- Pendências viram registro operacional (antes eram linhas de planilha)
CREATE TABLE IF NOT EXISTS pendencia (
  id           INTEGER PRIMARY KEY,
  codigo       TEXT NOT NULL,            -- chave estável: tipo|registro
  severidade   TEXT NOT NULL CHECK (severidade IN ('CRITICA','ALTA','MEDIA','BAIXA')),
  tipo         TEXT NOT NULL,
  entidade     TEXT NOT NULL,            -- material | fornecedor | categoria | email
  registro     TEXT,                     -- PN, código do fornecedor, e-mail…
  problema     TEXT NOT NULL,
  sugestao     TEXT,
  status       TEXT NOT NULL DEFAULT 'ABERTA'
               CHECK (status IN ('ABERTA','EM_ANALISE','RESOLVIDA','IGNORADA')),
  responsavel_id INTEGER REFERENCES usuario(id),
  resolvido_por  INTEGER REFERENCES usuario(id),
  resolvido_em   TEXT,
  justificativa  TEXT,
  valor_anterior TEXT,
  valor_novo     TEXT,
  detectada_em   TEXT DEFAULT (datetime('now')),
  UNIQUE (codigo)
);
CREATE INDEX IF NOT EXISTS ix_pend_status ON pendencia(status, severidade);
CREATE INDEX IF NOT EXISTS ix_pend_reg    ON pendencia(entidade, registro);

-- Filtros salvos por usuário ("Minha visão: divergências >30% — Rolamentos")
CREATE TABLE IF NOT EXISTS filtro_salvo (
  id         INTEGER PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
  tela       TEXT NOT NULL,
  nome       TEXT NOT NULL,
  filtros    TEXT NOT NULL,             -- JSON
  criado_em  TEXT DEFAULT (datetime('now')),
  UNIQUE (usuario_id, tela, nome)
);

-- Vínculo PN -> fornecedor decidido por uma pessoa (nunca automático)
CREATE TABLE IF NOT EXISTS material_fornecedor (
  id            INTEGER PRIMARY KEY,
  pn            TEXT NOT NULL REFERENCES material(pn) ON DELETE CASCADE,
  fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id),
  principal     INTEGER NOT NULL DEFAULT 0,
  origem        TEXT,                    -- HISTORICO_SAP | MANUAL | PLANILHA
  confirmado_por INTEGER REFERENCES usuario(id),
  confirmado_em  TEXT,
  observacao    TEXT,
  UNIQUE (pn, fornecedor_id)
);

-- Sessões de login (permite expiração e revogação)
CREATE TABLE IF NOT EXISTS sessao (
  token      TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
  csrf       TEXT NOT NULL,
  ip         TEXT,
  criada_em  TEXT DEFAULT (datetime('now')),
  expira_em  TEXT NOT NULL,
  revogada   INTEGER NOT NULL DEFAULT 0
);

-- Perfil ALMOXARIFE não existia no CHECK original de usuario.
-- SQLite não altera CHECK; a tabela é recriada preservando as linhas.
CREATE TABLE IF NOT EXISTS usuario_novo (
  id           INTEGER PRIMARY KEY,
  email        TEXT NOT NULL UNIQUE,
  nome         TEXT NOT NULL,
  perfil       TEXT NOT NULL DEFAULT 'SOLICITANTE'
               CHECK (perfil IN ('SOLICITANTE','ALMOXARIFE','COMPRADOR','GESTOR','ADMIN')),
  senha_hash   TEXT,
  entra_oid    TEXT UNIQUE,
  ativo        INTEGER NOT NULL DEFAULT 1,
  ultimo_acesso TEXT,
  criado_em    TEXT DEFAULT (datetime('now'))
);
INSERT INTO usuario_novo (id,email,nome,perfil,senha_hash,entra_oid,ativo,ultimo_acesso,criado_em)
  SELECT id,email,nome,perfil,senha_hash,entra_oid,ativo,ultimo_acesso,criado_em FROM usuario;
DROP TABLE usuario;
ALTER TABLE usuario_novo RENAME TO usuario;

-- Métricas do material calculadas pelo motor de inteligência (cache com proveniência)
CREATE TABLE IF NOT EXISTS material_metrica (
  pn                TEXT PRIMARY KEY REFERENCES material(pn) ON DELETE CASCADE,
  ultimo_preco      REAL,
  ultimo_preco_data TEXT,
  ultimo_fornecedor_id INTEGER REFERENCES fornecedor(id),
  media_3m          REAL,
  media_6m          REAL,
  media_12m         REAL,
  menor_preco       REAL,
  maior_preco       REAL,
  compras_12m       INTEGER,
  consumo_3m        REAL,
  consumo_6m        REAL,
  consumo_12m       REAL,
  consumo_anual     REAL,
  meses_sem_consumo INTEGER,
  cobertura_meses   REAL,
  ponto_reposicao   REAL,
  risco             TEXT,               -- RUPTURA | BAIXO | OK | ELEVADO | SEM_MOVIMENTO
  classe_abc        TEXT,
  classe_xyz        TEXT,
  divergencia_pct   REAL,               -- MM60 x último preço
  oportunidade_ano  REAL,               -- diferença anualizada indicativa
  lead_time_obs     REAL,               -- dias entre pedido e recebimento
  ultima_entrada    TEXT,
  ultima_saida      TEXT,
  escala_suspeita   INTEGER DEFAULT 0,   -- MM60 e preço pago em unidades diferentes
  calculado_em      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_mm_risco ON material_metrica(risco);
CREATE INDEX IF NOT EXISTS ix_mm_div   ON material_metrica(divergencia_pct);
