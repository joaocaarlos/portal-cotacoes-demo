# Hospedar de graça

O portal é uma imagem Docker que respeita `$PORT` e não precisa de banco externo
— o SQLite de demonstração vem dentro da imagem. Isso faz ele caber em qualquer
hospedador gratuito de contêiner.

**Criar a conta é o único passo manual.** Depois disso o repositório já traz tudo
configurado.

---

## Render (recomendado)

Um clique, a partir do `render.yaml` que já está no repositório:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joaocaarlos/portal-cotacoes-demo)

Ou pelo painel: **New → Blueprint → selecione este repositório → Apply**.

Não há nada para preencher. O blueprint já define ambiente, `DRY_RUN=1`,
`COOKIE_SECURE=1` e gera o `APP_SECRET`.

A URL sai como `https://portal-cotacoes-demo.onrender.com`.

**O que esperar do plano gratuito:**

- A instância hiberna depois de ~15 minutos sem acesso. O primeiro request
  seguinte demora cerca de um minuto — não é travamento, é o contêiner subindo.
- O disco é efêmero: o banco volta ao estado original a cada boot. Para uma
  demonstração isso é conveniente — qualquer bagunça se desfaz sozinha.
- Sem cartão de crédito.

---

## Hugging Face Spaces

Também gratuito, sem cartão, e **não hiberna tão rápido** quanto o Render.

1. Crie um Space em https://huggingface.co/new-space
   - **SDK: Docker** (não Gradio nem Streamlit)
   - Visibilidade: Public
2. O Space vem com um repositório Git próprio. Envie o código para ele:

```bash
git remote add space https://huggingface.co/spaces/SEU_USUARIO/portal-cotacoes
git push space main
```

3. O Space precisa de um cabeçalho YAML no topo do `README.md`. Acrescente:

```yaml
---
title: Portal de Cotações
emoji: 📦
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

4. Nas **Settings → Variables** do Space, defina:
   `AMBIENTE=demonstracao`, `DRY_RUN=1`, `PORT=7860`

O `app_port: 7860` e a variável `PORT` têm que bater. A imagem lê `$PORT`, então
qualquer valor serve desde que os dois sejam iguais.

---

## Koyeb

Gratuito, sem cartão, uma instância.

1. https://app.koyeb.com → **Create Service → GitHub** → este repositório
2. Builder: **Dockerfile**
3. Porta: `8000` · Health check path: `/healthz`
4. Variáveis: `AMBIENTE=demonstracao`, `DRY_RUN=1`, `COOKIE_SECURE=1`

---

## Fly.io

Precisa de cartão para validar a conta, mesmo no uso gratuito.

```bash
fly launch --no-deploy        # detecta o Dockerfile
fly secrets set AMBIENTE=demonstracao DRY_RUN=1 COOKIE_SECURE=1
fly deploy
```

Ajuste o `internal_port` no `fly.toml` para `8000`.

---

## Antes de expor publicamente

A demonstração é pública e as senhas estão no README. Isso é intencional, mas
duas travas precisam continuar ligadas:

| Variável | Valor | Por quê |
|---|---|---|
| `DRY_RUN` | `1` | sem isto, qualquer visitante dispara cotação por e-mail de verdade |
| `AMBIENTE` | `demonstracao` | mantém o banco sintético e as contas abertas de propósito |

**Nunca aponte uma instalação pública para dados reais.** Para uso com dados de
verdade, siga o `DEPLOY.md`: banco próprio, `seed_usuarios.py` (senha aleatória e
troca obrigatória) e `AMBIENTE=producao`.

## Verificar que subiu

```bash
curl https://SUA-URL/healthz     # {"status":"ok","versao":"1.0.0"}
curl https://SUA-URL/readyz      # materiais > 0 e migracoes = 2
```

Se `/readyz` responder 503, o banco não foi encontrado — confira `DB_PATH`.
