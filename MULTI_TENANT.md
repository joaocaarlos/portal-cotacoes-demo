# Multi-tenant: o que já existe e o que falta

O portal roda hoje como **instalação corporativa**: uma empresa, uma instância,
um banco. `MULTI_TENANT=0`.

A estrutura de tenant já está no banco (migração 02) para que a virada seja
ligar um filtro, não refazer o schema. Este documento é honesto sobre a
diferença entre as duas coisas.

## O que já está pronto

| Item | Estado |
|---|---|
| Tabela `tenant` (slug, nome, domínio, plano, ativo) | pronto |
| `tenant_id` em `material`, `fornecedor`, `categoria`, `processo`, `pendencia`, `filtro_salvo`, `auditoria`, `usuario`, `sessao` | pronto, com índice |
| Sessão carrega o `tenant_id` resolvido no login | pronto |
| `g.tenant_id` disponível em todo request | pronto |
| `auth.tenant_atual()` — nunca lê tenant vindo do cliente | pronto |
| `auth.escopo(sql, alias)` — ponto único do filtro | pronto, inativo enquanto `MULTI_TENANT=0` |
| Criação de usuário grava o tenant de quem criou | pronto |

## O que falta para ser multi-tenant de verdade

Não ligue `MULTI_TENANT=1` esperando isolamento. Falta:

1. **Aplicar `escopo()` nas ~70 consultas de negócio do `app.py`.** Hoje elas leem
   a tabela inteira. Sem isso, dois tenants no mesmo banco enxergam um ao outro.
2. **Chaves primárias.** `material.pn` é PK global. Com dois tenants, dois PNs
   iguais em empresas diferentes colidem. Vira PK composta `(tenant_id, pn)` —
   e todas as FKs que apontam para `material(pn)` mudam junto.
3. **Views de apoio** (`vw_ultimo_preco` e as outras do `schema.sql`) precisam do
   `tenant_id` na projeção e no filtro.
4. **`metricas.py`** recalcula por material sem recorte de tenant.
5. **Resolução do tenant no login** por domínio de e-mail ou subdomínio.
6. **Cadastro de empresa, convite de usuário, planos e limites** — não existem.
7. **Teste de isolamento no CI**: dois tenants, um usuário em cada, provar que
   nenhum endpoint devolve linha do outro. Esse teste é o critério de aceite.

Estimativa honesta: é trabalho de semanas, não de horas, e o item 2 é o que dá
mais trabalho porque toca o schema inteiro.

## Como ligar, quando chegar a hora

```python
# antes
linhas = q("SELECT * FROM material WHERE tipo = ?", (tipo,))

# depois
linhas = q(auth.escopo("SELECT * FROM material WHERE tipo = :tipo", ""),
           {"tipo": tipo, "tenant_id": g.tenant_id})
```

`escopo()` acrescenta `AND tenant_id = :tenant_id` (ou `WHERE`, se não houver) e
devolve o SQL intacto enquanto `MULTI_TENANT=0` — dá para migrar endpoint por
endpoint sem quebrar a instalação corporativa em produção.

## A alternativa que costuma sair mais barata

Para poucas empresas, **uma instância por cliente** (um contêiner, um volume,
um `.env`) entrega isolamento real no dia 1, sem tocar em nenhuma query. O
`docker-compose.yml` já suporta isso: copie o serviço, mude o volume e a porta.
Só vale investir no isolamento por linha quando o número de clientes tornar o
custo por instância alto.
