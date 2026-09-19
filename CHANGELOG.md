# Changelog

## 1.0.0 — 2026-09-18

Primeira versão preparada para produção. A Fase 1 (funcionalidades do portal)
já estava pronta; esta versão trata de **colocar no ar com segurança**.

### Segurança

- **Senhas de teste eliminadas.** `comprador123`, `almox123`, `gestor123` e
  `admin123` não existem mais — nem no código, nem no README, nem na tela de login,
  nem no banco. `seed_usuarios.py` gera senha aleatória por conta, imprime uma vez
  e exige troca no primeiro acesso.
- **Política de senha** — mínimo de 10 caracteres, lista de previsíveis recusadas,
  senha igual ao usuário recusada (`auth.validar_senha`).
- **Troca obrigatória de senha** — contas criadas pelo administrador e contas
  resetadas recebem 428 em toda a API até definirem a senha. Tela nova no frontend.
- **Endpoint `POST /api/senha`** — troca da própria senha, revoga as sessões abertas.
- **Cookie de sessão `Secure`** em produção, `SameSite` configurável.
- **Cabeçalhos de segurança** — CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, HSTS sob TLS, `Cache-Control: no-store` na API.
- **`ProxyFix`** — atrás de proxy reverso, o rate limit passa a ver o IP real.
- **Segredos fora do código** — `config.py` centraliza tudo em variáveis de ambiente
  e recusa o boot em produção sem `APP_SECRET`, sem SMTP com `DRY_RUN=0`, ou com
  `COOKIE_SECURE=0`.

### Infraestrutura

- **`Dockerfile`** — imagem de produção, usuário sem privilégio, healthcheck nativo.
- **`docker-compose.yml`** — app + volume persistente, Caddy opcional para HTTPS automático.
- **`entrypoint.sh`** — aplica migrações antes de servir; copia o banco para o volume
  na primeira subida.
- **`aplicar_migracoes.py`** — runner versionado. Corrige um problema real: rodar
  `migracao_01.sql` duas vezes derrubava a tabela `usuario`. Agora cada migração roda
  uma vez, registrada em `schema_migracao`, e bancos que já vieram migrados são
  reconhecidos sem reexecutar.
- **`backup.sh`** — backup consistente via API de backup do SQLite (um `cp` durante
  escrita geraria arquivo corrompido), com compressão e retenção.
- **`smoke_test.py`** — 24 verificações do caminho crítico: healthchecks, login, CSRF,
  RBAC, política de senha, troca obrigatória, integridade de tenant.
- **CI no GitHub Actions** — compila, prova que as migrações são idempotentes, roda o
  smoke test, constrói a imagem, sobe o contêiner e confere `/healthz`. Falha o build
  se alguma credencial de teste voltar ao código.
- **WAL ligado** no SQLite — leitores deixam de bloquear o escritor sob gunicorn.

### Multi-tenant (preparação)

- Tabela `tenant` e `tenant_id` nas entidades de negócio, com índice.
- Sessão carrega o tenant; `auth.tenant_atual()` nunca aceita tenant vindo do cliente.
- `auth.escopo()` como ponto único onde o filtro será aplicado.
- `MULTI_TENANT.md` documenta o que falta — e diz explicitamente que ligar a flag
  hoje **não** isola dados.

### Publicação aberta

- **`gerar_demo.py`** — gerador de dados sintéticos: 480 materiais, 42 fornecedores,
  1.868 movimentos, com distribuições que exercitam ruptura, divergência de preço,
  materiais sem fornecedor e escala inconsistente. Nenhum dado real.
- **`ORG_NOME` / `ORG_SUBTITULO`** — o nome da organização estava escrito no código em
  três lugares (login, menu, assinatura de e-mail). Agora é configuração.
- **Correção de migração** — `ALTER TABLE ... ADD COLUMN tenant_id ... REFERENCES tenant(id)`
  falha no SQLite quando `PRAGMA foreign_keys=ON` (ligada pela migração 01). O erro só
  aparecia ao criar o banco do zero, caminho que o banco já pronto nunca exercitava.
  As colunas passaram a declarar só tipo e default.
- Licença MIT; o ETL específico de planilhas internas ficou de fora.

### Documentação

- README reescrito com quick start, mapa do repositório e tabela de configuração.
- `DEPLOY.md`, `SECURITY.md`, `MULTI_TENANT.md` novos.

## 0.1.0 — Fase 1

Portal completo: login e perfis com RBAC no backend, Ficha 360º do material,
pesquisa universal, histórico SAP unificado, métricas com proveniência, fila de
pendências, vínculo de fornecedor com decisão humana, processo de cotação por SMTP,
mapa de cotação e auditoria.
