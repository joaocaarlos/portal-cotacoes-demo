# Segurança

## Reportar um problema

Abra uma *security advisory* privada no GitHub (aba Security → Report a vulnerability)
com passos para reproduzir. Não abra issue pública para falha de segurança.

## O que o portal faz

**Autenticação.** Senha com PBKDF2-HMAC-SHA256, 120.000 iterações, salt por
usuário. Comparação em tempo constante. Sessão em cookie `HttpOnly`, `SameSite=Lax`,
`Secure` em produção, com expiração de 8 h e revogação no logout e na troca de senha.

**Autorização.** Perfis (`ALMOXARIFE`, `COMPRADOR`, `GESTOR`, `ADMIN`, `SOLICITANTE`)
aplicados **no backend**, no decorator `@exige`. Esconder o botão não é o controle:
o almoxarife recebe 403 em `/api/precos` chamando a API direto — e há teste para isso.

**CSRF.** Todo POST/PUT/DELETE exige o cabeçalho `X-CSRF` com o token da sessão.

**Senhas.** Mínimo de 10 caracteres, lista de senhas previsíveis recusadas, senha
igual ao usuário recusada. Contas criadas pelo administrador e contas resetadas
nascem com troca obrigatória: a API devolve **428** em tudo até a senha ser trocada.

**Rate limit.** Por IP e rota, em janela de 5 min: login (15), envio de cotação (10),
troca de senha (10).

**Cabeçalhos.** CSP sem `unsafe-eval` e sem CDN, `X-Frame-Options: DENY`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, HSTS quando há TLS,
`Cache-Control: no-store` em toda a API.

**SQL.** Consultas parametrizadas em todo o código — nenhuma interpolação de
entrada do usuário em SQL.

**Auditoria.** Usuário, data/hora, entidade, ação, valor anterior, valor novo, IP e
origem. Campos com `senha`, `token` ou `csrf` no nome são mascarados antes de gravar.

**Segredos.** Nada de segredo no código. Em `AMBIENTE=producao` a app se recusa a
subir sem `APP_SECRET`, e sem SMTP configurado quando `DRY_RUN=0`.

## Limitações conhecidas

- **O rate limit é por processo, em memória.** Com vários workers do gunicorn, cada
  um tem o seu balde — o limite efetivo é `LIMITE × workers`. Para valer de verdade,
  aplique o limite no proxy (Caddy/nginx) ou troque por Redis.
- **Não há 2FA.** O caminho previsto é o Entra ID (`auth.login_entra()`), que traz o
  MFA corporativo junto. O endpoint está isolado e não é chamado enquanto o TI não liga.
- **Não há bloqueio de conta por tentativas.** Só rate limit por IP.
- **`MULTI_TENANT=1` não isola dados ainda.** Ver `MULTI_TENANT.md` — a estrutura
  existe, o filtro nas consultas não. Não ligue esperando isolamento.
- **O `demo.db` traz contas com senha conhecida e sem troca obrigatória** — de
  propósito, para que testar leve dez segundos. É um banco de demonstração com dados
  sintéticos. **Nunca suba o `demo.db` em produção**: crie um banco novo e rode
  `python seed_usuarios.py`, que gera senha aleatória e exige troca no primeiro acesso.

## Antes de cada deploy

`python smoke_test.py` — 24 verificações, incluindo RBAC, CSRF e política de senha.
O CI roda isso em todo push e falha se alguma credencial de teste voltar ao código.
