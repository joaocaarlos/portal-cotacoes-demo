# Portal de Gestão de Cotações

Aplicação web para **compras industriais e almoxarifado**: ficha completa do material,
histórico de preços com proveniência, inteligência de estoque (curva ABC, ruptura,
cobertura) e processo de cotação com fornecedores por e-mail.

O centro não é o envio de e-mail — é o **Material**, o **Processo de Cotação** e o
**Fornecedor**. Dados de ERP/SAP alimentam essas três experiências.

Flask + SQLite, sem framework de frontend: a interface são três arquivos JavaScript
e um CSS, servidos do próprio domínio.

> **Este repositório acompanha um banco de demonstração com dados 100% sintéticos.**
> Nenhuma empresa, fornecedor, preço ou pessoa real. Gerado por `gerar_demo.py`.

## Testar em 4 comandos

```bash
git clone https://github.com/joaocaarlos/portal-cotacoes-demo.git
cd portal-cotacoes-demo
pip install -r requirements.txt
python app.py
```

Abra **http://localhost:8000**. O `demo.db` já vem pronto no repositório.

### Contas de demonstração

Senha para todas: **`demonstracao-2026`**

| Perfil | Usuário | O que vê |
|---|---|---|
| Almoxarife | `almoxarife@exemplo.com.br` | estoque, ruptura, consumo — **403 em preços** |
| Comprador | `comprador@exemplo.com.br` | cotações, preços, pendências, vínculo de fornecedor |
| Gestor | `gestor@exemplo.com.br` | KPIs, oportunidades, auditoria |
| Administrador | `admin@exemplo.com.br` | tudo, mais gestão de usuários |

Vale entrar como almoxarife e como comprador para ver a diferença: os perfis são
aplicados **no backend**, não escondendo botões. `curl` direto na API dá 403 igual.

### Com Docker

```bash
docker compose up -d --build
```

### Gerar outros dados

```bash
python gerar_demo.py           # regenera demo.db
SEMENTE=42 python gerar_demo.py    # outro sorteio, reproduzível
```

O gerador produz de propósito casos que exercitam as telas: materiais em ruptura,
divergência de preço, materiais sem fornecedor no cadastro e casos de escala
inconsistente entre o preço mestre e o preço pago.

## O que tem dentro

**Login e perfis** — sessão de 8 h, CSRF em toda escrita, rate limit em login e envio,
mascaramento de campos sensíveis na auditoria. Cinco perfis com permissões aplicadas
no backend.

**Ficha 360º do material** — cabeçalho, cards de resumo (estoque, consumo, cobertura,
último preço, preço mestre, diferença, lead time) e nove abas: Visão Geral, Estoque,
Consumo, Preços, Compras, SAP, Fornecedores, Cotações, Auditoria. Os alertas sempre
dizem *o motivo*: "Estoque atual: 8 UN. Consumo médio: 15 UN/mês. Cobertura: 16 dias."

**Preços** — evolução em 3M/6M/12M/24M mostrando preços pagos, média 12M ponderada e
preço mestre ao mesmo tempo. Cada média é clicável e abre **"Como foi calculada"**, com
a fórmula e os registros usados.

**Histórico de ERP** — pedidos, requisições e movimentos numa experiência só. A timeline
monta requisição → pedido → entrada → saída e calcula ciclos **apenas quando o vínculo
existe de fato no dado**. Nada é inferido.

**Materiais sem fornecedor** — o sistema pesquisa o histórico e sugere o fornecedor
predominante com o motivo explícito ("17 compras · última em 15/09 · 100% das compras
deste PN"). **Nada altera o cadastro mestre sem decisão de uma pessoa**, e toda
confirmação grava auditoria com valor anterior, novo e origem.

**Pendências** — fila operacional com severidade, filtros, sugestão de correção e
resolução registrada. O motor reabre o que voltou a ocorrer e fecha o que foi
resolvido na origem.

**Cotação** — cria o processo COT-AAAA-NNNN, sugere fornecedores (histórico primeiro,
categoria depois, cada um com o motivo), envia por SMTP, registra respostas e monta o
mapa de cotação com menor preço destacado e o contexto histórico ao lado.

**Auditoria** — usuário, data/hora, entidade, ação, valor anterior, valor posterior,
IP e origem.

## Inteligência calculada

`metricas.py` grava em `material_metrica`, com proveniência:

| Indicador | Como é calculado |
|---|---|
| Média 3M/6M/12M | Σ(preço × quantidade) ÷ Σ(quantidade) — ponderada, não média simples |
| Cobertura | estoque atual ÷ consumo médio mensal dos últimos 12 meses |
| Ponto de reposição | consumo médio × lead time (em meses) |
| Risco | ruptura se cobertura < lead time; elevado se estoque > 1,5× máximo; sem movimentação se 12 meses sem consumo |
| Curva ABC | acumulado do valor consumido em 12M (A até 80%, B até 95%, C o resto) |
| Classe XYZ | coeficiente de variação do consumo mensal (X < 0,5; Y < 1,0; Z acima) |
| Divergência | (último preço − preço mestre) ÷ preço mestre |
| Oportunidade indicativa | (preço mestre − último preço) × consumo 12M |
| Lead time observado | dias entre data do pedido e remessa |

**Oportunidade indicativa nunca é chamada de saving.** A tela diz que só vira economia
quando houver negociação ou compra que comprove.

## Duas ressalvas que a interface mostra em vez de esconder

**Escala de preço.** Quando o preço mestre está em unidade de 1.000 e o movimento em
unidade simples, comparar daria divergência de −99%. Esses materiais são marcados como
"escala inconsistente", a divergência fica suspensa e eles não entram nas oportunidades.

**Classificação automática.** O vínculo material → categoria por palavra-chave tem
confiança variável; a ficha mostra a confiança e a origem. É por isso que a sugestão de
fornecedor usa **primeiro o histórico do material** e só depois a categoria.

## Mapa do repositório

```
app.py                 API Flask — auth, RBAC, auditoria, ~70 endpoints
auth.py                sessões, perfis, política de senha, escopo de tenant, Entra ID
config.py              configuração por ambiente; recusa boot inseguro em produção
metricas.py            motor de inteligência: métricas por material + fila de pendências
gerar_demo.py          gerador de dados sintéticos
schema.sql             esquema base
migracao_*.sql         migrações versionadas
aplicar_migracoes.py   runner idempotente
seed_usuarios.py       contas iniciais com senha aleatória (produção)
smoke_test.py          24 verificações do caminho crítico
backup.sh              backup consistente do SQLite
Dockerfile             imagem de produção, usuário sem root, healthcheck
docker-compose.yml     app + volume do banco (+ Caddy opcional para HTTPS)
templates/app.html + static/{app.css,core.js,views.js,views2.js}   interface
demo.db                banco de demonstração (dados sintéticos)
```

## Configuração

| Variável | Padrão | Para quê |
|---|---|---|
| `ORG_NOME` | `Portal de Cotações` | nome exibido no login, menu e assinatura de e-mail |
| `AMBIENTE` | `desenvolvimento` | `producao` ativa as exigências de segurança no boot |
| `APP_SECRET` | — | obrigatório em produção; a app não sobe sem |
| `DB_PATH` | `./cotacoes.db` | caminho do banco |
| `DRY_RUN` | `1` em dev | `1` simula o envio e registra tudo, sem tocar no SMTP |
| `COOKIE_SECURE` | `1` em produção | cookie de sessão só por HTTPS |
| `SENHA_MIN` | `10` | tamanho mínimo da senha |
| `MULTI_TENANT` | `0` | ver `MULTI_TENANT.md` antes de ligar |
| `SMTP_*`, `MAIL_FROM` | — | envio real das cotações |

Todas documentadas em `.env.example`.

## Usar com dados reais

1. `python gerar_demo.py` só para conhecer a estrutura; depois **apague o `demo.db`**
2. Crie o banco com `schema.sql` + `python aplicar_migracoes.py`
3. Escreva o seu ETL para carregar materiais, fornecedores e histórico de compras
4. `python metricas.py` após cada carga
5. `python seed_usuarios.py` — gera senhas aleatórias com troca obrigatória
6. Siga a checklist do **[DEPLOY.md](DEPLOY.md)**

O ETL de planilhas do projeto original não está aqui: era específico do formato
interno de uma empresa e não serviria para mais ninguém.

## Documentação

- **[DEPLOY.md](DEPLOY.md)** — Docker, Linux, Windows Server, HTTPS, backup, checklist
- **[SECURITY.md](SECURITY.md)** — controles implementados e limitações conhecidas
- **[MULTI_TENANT.md](MULTI_TENANT.md)** — o que existe, o que falta e quanto custa
- **[CHANGELOG.md](CHANGELOG.md)** — o que mudou em cada versão

## Licença

MIT — ver [LICENSE](LICENSE).
