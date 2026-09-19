-- @ja-aplicada-se: SELECT COUNT(*) FROM pragma_table_info('usuario') WHERE name='tenant_id'
-- Migração 02 — preparação multi-tenant + endurecimento de contas.
--
-- Decisão de arquitetura: o portal continua servindo UMA empresa em produção
-- (uma instância, um banco). Esta migração instala a *estrutura* de tenant para
-- que virar multi-tenant depois seja ligar o filtro, não reescrever o schema.
--
-- Todas as linhas existentes ficam no tenant 1. A coluna tem DEFAULT 1, então
-- nenhum INSERT atual precisa mudar.
-- Idempotente: rodar duas vezes não quebra (ver aplicar_migracoes.py).

CREATE TABLE IF NOT EXISTS tenant (
  id         INTEGER PRIMARY KEY,
  slug       TEXT NOT NULL UNIQUE,      -- identificador curto, usado em URL/subdomínio
  nome       TEXT NOT NULL,
  dominio    TEXT,                      -- domínio de e-mail que resolve para este tenant
  ativo      INTEGER NOT NULL DEFAULT 1,
  plano      TEXT NOT NULL DEFAULT 'CORPORATIVO',
  criado_em  TEXT DEFAULT (datetime('now'))
);

INSERT INTO tenant (id, slug, nome, dominio)
SELECT 1, 'demo', 'Portal de Cotações', 'exemplo.com.br'
WHERE NOT EXISTS (SELECT 1 FROM tenant WHERE id = 1);

-- Sessão passa a carregar o tenant resolvido no login (evita join extra por request).
-- Usuário ganha controle de troca de senha obrigatória.
-- Nota sobre `REFERENCES tenant(id)`: o SQLite recusa ADD COLUMN com chave
-- estrangeira e DEFAULT não-nulo ("Cannot add a REFERENCES column with non-NULL
-- default value") quando `PRAGMA foreign_keys=ON` — que é o caso, porque a
-- migração 01 liga a pragma. Por isso as colunas abaixo declaram só o tipo e o
-- default; a integridade vem do default fixo em 1 e do tenant 1 criado acima.
ALTER TABLE sessao  ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE usuario ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE usuario ADD COLUMN forcar_troca_senha INTEGER NOT NULL DEFAULT 0;
ALTER TABLE usuario ADD COLUMN senha_trocada_em TEXT;

-- Entidades de negócio. tenant_id DEFAULT 1 mantém todo o dado atual no tenant existente.
ALTER TABLE material      ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE fornecedor    ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE categoria     ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE processo      ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE pendencia     ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE filtro_salvo  ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE auditoria     ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_material_tenant   ON material(tenant_id);
CREATE INDEX IF NOT EXISTS ix_fornecedor_tenant ON fornecedor(tenant_id);
CREATE INDEX IF NOT EXISTS ix_processo_tenant   ON processo(tenant_id);
CREATE INDEX IF NOT EXISTS ix_pendencia_tenant  ON pendencia(tenant_id);
CREATE INDEX IF NOT EXISTS ix_auditoria_tenant  ON auditoria(tenant_id);
CREATE INDEX IF NOT EXISTS ix_usuario_tenant    ON usuario(tenant_id);

-- Índices que faltavam e que a tela de sessão/login usa a cada request.
CREATE INDEX IF NOT EXISTS ix_sessao_usuario ON sessao(usuario_id, revogada);
