# Colocar no ar

Três caminhos, do mais rápido ao mais completo. Todos partem do repositório clonado.

---

## 1. Docker (recomendado)

Pré-requisito: Docker Engine com o plugin Compose.

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # cole em APP_SECRET
docker compose up -d --build
docker compose logs -f portal
```

O `entrypoint.sh` copia o banco para o volume na primeira subida, aplica as migrações
pendentes e só então entrega o processo ao gunicorn. A app fica em `127.0.0.1:8000` —
de propósito: quem expõe para a rede é o proxy.

Criar as contas e ver as senhas geradas (uma vez só):

```bash
docker compose exec portal python seed_usuarios.py /dados/cotacoes.db
```

> Para apenas **experimentar**, o `demo.db` do repositório já tem contas prontas
> (ver README). O passo acima é para uso com dados reais.

### HTTPS com domínio

Descomente o serviço `proxy` no `docker-compose.yml`, crie o `Caddyfile` ao lado:

```
cotacoes.suaempresa.com.br {
    reverse_proxy portal:8000
}
```

Aponte o DNS para a máquina e `docker compose up -d`. O Caddy emite e renova o
certificado Let's Encrypt sozinho. Com TLS no proxy, mantenha `COOKIE_SECURE=1`:
o `ProxyFix` no `app.py` já lê o `X-Forwarded-Proto` que o Caddy envia.

---

## 2. Servidor Linux sem Docker

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env          # APP_SECRET, DB_PATH, SMTP
set -a && . ./.env && set +a
python aplicar_migracoes.py
python seed_usuarios.py
gunicorn --workers 2 --threads 4 --timeout 120 --bind 127.0.0.1:8000 app:app
```

Como serviço do systemd (`/etc/systemd/system/portal-cotacoes.service`):

```ini
[Unit]
Description=Portal de Gestão de Cotações
After=network.target

[Service]
User=portal
WorkingDirectory=/opt/portal-cotacoes
EnvironmentFile=/opt/portal-cotacoes/.env
ExecStart=/opt/portal-cotacoes/.venv/bin/gunicorn --workers 2 --threads 4 \
          --timeout 120 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now portal-cotacoes` e coloque nginx ou Caddy na frente.

---

## 3. Windows Server

`gunicorn` não roda em Windows. Use o `waitress`, que já está no `requirements.txt`:

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python aplicar_migracoes.py
.\.venv\Scripts\python seed_usuarios.py
.\.venv\Scripts\waitress-serve --listen=127.0.0.1:8000 app:app
```

Para virar serviço, use o NSSM apontando para o `waitress-serve`, e o IIS com
ARR/URL Rewrite como proxy reverso HTTPS.

---

## Depois de subir: a checklist

- [ ] `APP_SECRET` definido com valor gerado (não o do `.env.example`)
- [ ] `AMBIENTE=producao` — a app se recusa a subir sem `APP_SECRET`
- [ ] `COOKIE_SECURE=1` e HTTPS funcionando
- [ ] `python seed_usuarios.py` rodado e senhas distribuídas por canal seguro
- [ ] Primeiro login de cada pessoa trocou a senha (a API bloqueia até trocar)
- [ ] `DRY_RUN=1` até o TI liberar a conta SMTP de serviço
- [ ] `./backup.sh` no cron diário, com o destino fora da mesma máquina
- [ ] `/healthz` e `/readyz` monitorados
- [ ] `python metricas.py` agendado após cada carga de dados
- [ ] `demo.db` **removido** do servidor — ele tem senhas conhecidas

## Operação do dia a dia

| Tarefa | Comando |
|---|---|
| Recalcular métricas e pendências (após carga SAP) | `python metricas.py` |
| Regerar o banco de demonstração | `python gerar_demo.py` |
| Backup manual | `./backup.sh` |
| Resetar a senha de alguém | `python seed_usuarios.py --resetar pessoa@empresa.com.br` |
| Verificar se o deploy está sadio | `python smoke_test.py` |
| Ver o estado das migrações | `python aplicar_migracoes.py` |

## Restaurar um backup

```bash
docker compose stop portal
gunzip -c backups/cotacoes-20260918-0200.db.gz > /tmp/restaurado.db
docker compose cp /tmp/restaurado.db portal:/dados/cotacoes.db
docker compose start portal
docker compose exec portal python smoke_test.py /dados/cotacoes.db
```
