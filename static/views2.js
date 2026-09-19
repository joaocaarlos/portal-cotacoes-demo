/* Telas: estoque, consumo, preços, SAP, fornecedores, pendências, cotações, admin */

/* ======================= ESTOQUE ======================= */
function telaEstoque(c, visao){
  const titulos = {geral:['Estoque — visão geral','Materiais do almoxarifado ordenados por valor imobilizado.'],
    cobertura:['Cobertura de estoque','Quantos meses o estoque atual cobre, considerando o consumo médio dos últimos 12 meses.'],
    parado:['Materiais sem movimentação','Sem consumo nos últimos 12 meses — candidatos a obsolescência.'],
    ruptura:['Risco de ruptura','Cobertura abaixo do lead time de reposição. Cada linha mostra o motivo do alerta.']};
  const [tit,sub] = titulos[visao]||titulos.geral;
  const t = Tabela({rota:'/api/estoque', semExport:true, tela:'estoque-'+visao,
    filtrosIniciais:{visao}, placeholder:'PN ou descrição…',
    colunas:[
      {k:'pn',rot:'PN',largura:'110px',ord:false,fmt:l=>el('a',{class:'pn',style:'cursor:pointer',
        onclick:()=>location.hash='#/material/'+encodeURIComponent(l.pn)},l.pn)},
      {k:'descricao',rot:'Descrição',tipo:'trunc',ord:false,largura:'24%'},
      {k:'estoque_atual',rot:'Estoque',tipo:'num',ord:false,fmt:l=>int(l.estoque_atual)+' '+(l.umb||'')},
      {k:'estoque_min',rot:'Mín / Máx',tipo:'num',ord:false,fmt:l=>int(l.estoque_min)+' / '+int(l.estoque_max)},
      {k:'consumo_mes',rot:'Consumo médio',tipo:'num',ord:false,fmt:l=>l.consumo_mes?num(l.consumo_mes,1)+'/mês':'—'},
      {k:'cobertura_meses',rot:'Cobertura',tipo:'num',ord:false,
        fmt:l=>l.cobertura_meses!=null?el('span',{title:`${num(l.cobertura_meses*30,0)} dias`},num(l.cobertura_meses,1)+' m'):'—'},
      {k:'ponto_reposicao',rot:'Ponto de reposição',tipo:'num',ord:false,fmt:l=>num(l.ponto_reposicao,1)},
      {k:'valor_estoque',rot:'Valor em estoque',tipo:'num',ord:false,fmt:l=>dinheiro(l.valor_estoque)},
      {k:'classe_abc',rot:'ABC/XYZ',ord:false,fmt:l=>(l.classe_abc||'—')+'/'+(l.classe_xyz||'—')},
      {k:'risco',rot:'Situação',ord:false,fmt:l=>seloRisco(l.risco)},
      {k:'acoes',rot:'',ord:false,fmt:l=>el('button',{class:'btn pequeno',onclick:()=>verContexto(l.pn)},'Contexto')}]});
  c.replaceChildren(crumbs({rot:'Estoque'},{rot:tit}), cabecalho(tit,sub), t.node);
}

async function telaConsumo(c){
  const d = await api('/api/consumo');
  c.replaceChildren(crumbs({rot:'Estoque'},{rot:'Consumo'}),
    cabecalho('Consumo','Movimentos de saída do SAP, agregados por mês e por material.'),
    el('div',{class:'painel'}, el('h2',{},'Consumo mensal (valor)'),
      el('div',{class:'corpo'}, grafBarras({dados:d.meses.map(m=>({r:mesBR(m.ano_mes),v:m.valor})),formato:abrev}))),
    el('div',{class:'painel'}, el('h2',{},'Materiais mais consumidos (12 meses)'),
      el('div',{class:'rolagem'}, el('table',{class:'dados'},
        el('thead',{},el('tr',{},...['PN','Descrição','Quantidade','Valor','ABC','XYZ'].map((h,i)=>
          el('th',{class:i>1&&i<4?'right':''},h)))),
        el('tbody',{},...d.top.map(x=>el('tr',{},
          el('td',{},el('a',{class:'pn',style:'cursor:pointer',
            onclick:()=>location.hash='#/material/'+encodeURIComponent(x.pn)},x.pn)),
          el('td',{class:'trunc'},x.descricao||'—'),
          el('td',{class:'num'},int(x.qtd)), el('td',{class:'num'},dinheiro(x.valor)),
          el('td',{},x.classe_abc||'—'), el('td',{},x.classe_xyz||'—'))))))));
}

/* ======================= PREÇOS ======================= */
function telaPrecos(c, visao){
  const titulos={geral:['Preços','Último preço pago, média histórica e preço mestre por material.'],
    divergencias:['Divergências de preço','Materiais cuja última compra difere mais de 30% do preço mestre MM60.'],
    oportunidades:['Oportunidades de preço','Diferença anualizada potencial entre o preço mestre e o preço efetivamente pago. Não é saving: só vira economia com negociação ou compra que comprove.'],
    escala:['Escala de preço inconsistente','Preço mestre e preço pago em unidades diferentes (unidade de preço do MM60 x UM do movimento). A comparação fica suspensa até o cadastro ser conferido.']};
  const [tit,sub]=titulos[visao]||titulos.geral;
  const colunas=[
    {k:'pn',rot:'PN',largura:'110px',ord:false,fmt:l=>el('a',{class:'pn',style:'cursor:pointer',
      onclick:()=>location.hash='#/material/'+encodeURIComponent(l.pn)},l.pn)},
    {k:'descricao',rot:'Descrição',tipo:'trunc',ord:false,largura:'24%'},
    {k:'mm60',rot:'MM60',tipo:'num',ord:false,fmt:l=>dinheiro(l.mm60)},
    {k:'ultimo_preco',rot:'Último preço',tipo:'num',ord:false,fmt:l=>dinheiro(l.ultimo_preco)},
    {k:'media_12m',rot:'Média 12M',tipo:'num',ord:false,fmt:l=>dinheiro(l.media_12m)},
    {k:'divergencia_pct',rot:'Diferença',tipo:'num',ord:false,fmt:l=>seloDivergencia(l.divergencia_pct,l.escala_suspeita)},
    {k:'consumo_12m',rot:'Consumo anual',tipo:'num',ord:false,fmt:l=>int(l.consumo_12m)},
    {k:'oportunidade',rot:'Oportunidade indicativa',tipo:'num',ord:false,
      fmt:l=>l.oportunidade?el('span',{title:'(MM60 − último preço) × consumo 12M'},dinheiro(l.oportunidade)):'—'},
    {k:'ultimo_fornecedor',rot:'Último fornecedor',tipo:'trunc',ord:false},
    {k:'ultimo_preco_data',rot:'Última compra',tipo:'num',ord:false,fmt:l=>dataBR(l.ultimo_preco_data)},
    {k:'acoes',rot:'',ord:false,largura:'170px',fmt:l=>el('div',{style:'display:flex;gap:5px'},
      el('button',{class:'btn pequeno',onclick:()=>verContexto(l.pn)},'Analisar'),
      pode('cotacao.criar')?el('button',{class:'btn pequeno',onclick:()=>modalNovaCotacao(l.pn)},'Criar cotação'):null)}];
  const t = Tabela({rota:'/api/precos', semExport:true, tela:'precos-'+visao,
    filtrosIniciais:{visao}, placeholder:'PN ou descrição…', colunas});
  c.replaceChildren(crumbs({rot:'Preços'},{rot:tit}), cabecalho(tit,sub), t.node);
}

/* ======================= SAP ======================= */
function telaSap(c, tipo){
  const rotulos={compras:'Compras (pedidos)',requisicoes:'Requisições',movimentacoes:'Movimentações de estoque'};
  const t = Tabela({rota:'/api/sap', semExport:true, tela:'sap-'+tipo,
    filtrosIniciais:{tipo, ...S.params},
    placeholder:'PN, descrição, pedido ou requisição…',
    filtros:[{k:'fornecedor',tipo:'text',rot:'Fornecedor'},
             {k:'de',tipo:'date',rot:'De'},{k:'ate',tipo:'date',rot:'Até'},
             {k:'categoria',tipo:'text',rot:'Categoria'}],
    colunas:[
      {k:'data_documento',rot:'Data',ord:false,fmt:l=>dataBR(l.data_documento)},
      {k:'pn',rot:'PN',ord:false,fmt:l=>el('a',{class:'pn',style:'cursor:pointer',
        onclick:()=>location.hash='#/material/'+encodeURIComponent(l.pn)},l.pn)},
      {k:'descricao',rot:'Descrição',tipo:'trunc',ord:false,largura:'24%'},
      {k:'requisicao',rot:'Requisição',ord:false},
      {k:'pedido',rot:'Pedido',ord:false},
      {k:'fornecedor',rot:'Fornecedor',tipo:'trunc',ord:false,fmt:l=>(l.fornecedor||'').trim()||'—'},
      {k:'quantidade',rot:'Qtde',tipo:'num',ord:false,fmt:l=>int(l.quantidade)},
      {k:'preco_unitario',rot:'Preço unit.',tipo:'num',ord:false,fmt:l=>dinheiro(l.preco_unitario)},
      {k:'valor_total',rot:'Valor',tipo:'num',ord:false,fmt:l=>dinheiro(l.valor_total)},
      {k:'data_remessa',rot:'Remessa',ord:false,fmt:l=>dataBR(l.data_remessa)},
      {k:'status',rot:'Status',ord:false,tipo:'trunc'}]});
  c.replaceChildren(crumbs({rot:'Histórico SAP'},{rot:rotulos[tipo]||tipo}),
    cabecalho('Histórico SAP — '+(rotulos[tipo]||tipo),
      'Dados de ME2N, ME5A e MB51 consolidados. Você não precisa saber de qual transação veio o registro.'),
    t.node);
}

/* ======================= FORNECEDORES ======================= */
function telaFornecedores(c, sub){
  const semEmail = sub==='sem-email';
  const t = Tabela({rota:'/api/fornecedores', semExport:true, tela:'fornecedores',
    filtrosIniciais: semEmail?{sem_email:'1'}:{},
    placeholder:'Razão social ou código SAP…',
    filtros:[{k:'tipo',tipo:'select',rot:'Tipo',opcoes:[{v:'DIRETO',r:'Direto'},{v:'INDIRETO',r:'Indireto'},{v:'AMBOS',r:'Ambos'}]},
             {k:'status',tipo:'select',rot:'Situação',opcoes:[{v:'ATIVO',r:'Ativo'},{v:'BLOQUEADO',r:'Bloqueado'},
               {v:'HOMOLOGADO',r:'Homologado'},{v:'EM_AVALIACAO',r:'Em avaliação'},{v:'INATIVO',r:'Inativo'}]},
             {k:'sem_email',tipo:'check',rot:'Sem e-mail'}],
    colunas:[
      {k:'razao_social',rot:'Fornecedor',ord:false,fmt:l=>el('a',{style:'cursor:pointer',
        onclick:()=>location.hash='#/fornecedor/'+l.id},l.razao_social)},
      {k:'codigo_sap',rot:'Código SAP',ord:false},
      {k:'tipo',rot:'Tipo',ord:false,fmt:l=>el('span',{class:'selo neutro'},(l.tipo||'—').toLowerCase())},
      {k:'status',rot:'Situação',ord:false,fmt:l=>seloStatus(l.status)},
      {k:'emails',rot:'E-mails',tipo:'num',ord:false,
        fmt:l=>l.emails?int(l.emails):el('span',{class:'selo crit'},'⚠ nenhum')},
      {k:'compras',rot:'Compras',tipo:'num',ord:false,fmt:l=>int(l.compras)},
      {k:'categorias',rot:'Categorias atendidas',tipo:'trunc',ord:false,largura:'22%'},
      {k:'prazo_medio_entrega',rot:'Prazo médio',ord:false,tipo:'trunc'},
      {k:'ultima_cotacao_em',rot:'Última compra/cotação',ord:false,fmt:l=>dataBR(l.ultima_cotacao_em)}]});
  c.replaceChildren(crumbs({rot:'Fornecedores'},{rot:semEmail?'Pendências de vínculo':'Cadastro'}),
    cabecalho(semEmail?'Fornecedores sem e-mail':'Fornecedores',
      semEmail?'Sem e-mail cadastrado, esses fornecedores nunca entram numa cotação automática.'
              :'Cadastro consolidado das abas de fornecedores diretos, indiretos e incoterms.'),
    t.node);
}

async function telaFornecedor(c, fid){
  const d = await api('/api/fornecedor/'+fid);
  const f = d.fornecedor;
  const contatos = el('div',{class:'painel'}, el('h2',{},'Contatos'),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['Área','Nome','Telefone','E-mail'].map(h=>el('th',{},h)))),
      el('tbody',{},...d.contatos.map(x=>el('tr',{},
        el('td',{},el('span',{class:'selo neutro'},(x.area||'').toLowerCase())),
        el('td',{},x.nome||'—'), el('td',{},x.telefone||'—'),
        el('td',{},x.email||el('span',{class:'muted'},'—'))))))));
  const materiais = el('div',{class:'painel'}, el('h2',{},'Materiais já fornecidos'),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['PN','Descrição','Compras','Última','Preço médio'].map((h,i)=>
        el('th',{class:i>1?'right':''},h)))),
      el('tbody',{},...d.materiais.map(x=>el('tr',{},
        el('td',{},el('a',{class:'pn',style:'cursor:pointer',
          onclick:()=>location.hash='#/material/'+encodeURIComponent(x.pn)},x.pn)),
        el('td',{class:'trunc'},x.descricao||'—'), el('td',{class:'num'},int(x.compras)),
        el('td',{class:'num'},dataBR(x.ultima)), el('td',{class:'num'},dinheiro(x.preco_medio))))))));
  c.replaceChildren(crumbs({rot:'Fornecedores',rota:'fornecedores'},{rot:f.razao_social}),
    el('div',{class:'ficha-topo'}, el('div',{class:'linha'},
      el('div',{}, el('div',{class:'pnum'},'Código SAP '+(f.codigo_sap||'—')),
        el('h1',{},f.razao_social),
        el('div',{class:'meta'}, el('span',{},'Tipo: '+(f.tipo||'—')),
          el('span',{},'Situação: '+(f.status||'—')),
          el('span',{},'Prazo médio: '+(f.prazo_medio_entrega||'—')),
          el('span',{},'Última compra: '+dataBR(f.ultima_cotacao_em)))))),
    el('div',{class:'kpis'},
      kpiSimples('Contatos',int(d.contatos.length)),
      kpiSimples('Categorias',int(d.categorias.length)),
      kpiSimples('Materiais fornecidos',int(d.materiais.length)),
      kpiSimples('Cotações',int(d.cotacoes.length)),
      kpiSimples('Incoterms',int(d.incoterms.length))),
    contatos, materiais,
    d.categorias.length?el('div',{class:'painel'}, el('h2',{},'Categorias atendidas'),
      el('div',{class:'corpo'}, ...d.categorias.map(x=>el('span',{class:'selo info',
        style:'margin:0 5px 5px 0'},x.nome)))):null);
}

async function telaCategorias(c){
  const cats = await api('/api/categorias');
  c.replaceChildren(crumbs({rot:'Materiais',rota:'materiais'},{rot:'Categorias'}),
    cabecalho('Categorias de material',
      'Categorias com origem CLASSIFICAÇÃO têm e-mails de cotação; as de origem CADASTRO vieram das abas de fornecedores e servem para busca.'),
    el('div',{class:'painel'}, el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['Categoria','Subcategoria','Origem','E-mails de cotação','Materiais'].map((h,i)=>
        el('th',{class:i>2?'right':''},h)))),
      el('tbody',{},...cats.map(x=>el('tr',{},
        el('td',{},x.nome), el('td',{class:'trunc'},x.subcategoria||'—'),
        el('td',{},el('span',{class:'selo '+(x.origem==='CLASSIFICACAO'?'ok':'neutro')},(x.origem||'—').toLowerCase())),
        el('td',{class:'num'},int(x.emails)),
        el('td',{class:'num'},el('a',{style:'cursor:pointer',
          onclick:()=>location.hash='#/materiais?categoria='+encodeURIComponent(x.nome)},int(x.materiais))))))))));
}

/* ======================= PENDÊNCIAS ======================= */
function telaPendencias(c){
  const resumo = el('div',{class:'cards'});
  const t = Tabela({rota:'/api/pendencias', semExport:true, tela:'pendencias',
    placeholder:'Registro ou descrição do problema…',
    filtros:[
      {k:'severidade',tipo:'select',rot:'Severidade',opcoes:[{v:'CRITICA',r:'Crítica'},{v:'ALTA',r:'Alta'},
        {v:'MEDIA',r:'Média'},{v:'BAIXA',r:'Baixa'}]},
      {k:'status',tipo:'select',rot:'Situação',opcoes:[{v:'ABERTA',r:'Abertas'},{v:'EM_ANALISE',r:'Em análise'},
        {v:'RESOLVIDA',r:'Resolvidas'},{v:'IGNORADA',r:'Ignoradas'}]}],
    colunas:[
      {k:'severidade',rot:'Sev.',ord:false,largura:'90px',fmt:l=>seloStatus(l.severidade)},
      {k:'tipo',rot:'Tipo',ord:false,tipo:'trunc',largura:'200px'},
      {k:'registro',rot:'Registro',ord:false,largura:'130px',fmt:l=>
        l.entidade==='material'?el('a',{class:'pn',style:'cursor:pointer',
          onclick:()=>location.hash='#/material/'+encodeURIComponent(l.registro)},l.registro):l.registro},
      {k:'problema',rot:'Problema',ord:false,tipo:'trunc',largura:'30%'},
      {k:'sugestao',rot:'Sugestão',ord:false,tipo:'trunc',largura:'24%'},
      {k:'status',rot:'Situação',ord:false,fmt:l=>seloStatus(l.status)},
      {k:'resolvido_por_nome',rot:'Responsável',ord:false,fmt:l=>l.resolvido_por_nome||'—'},
      {k:'acoes',rot:'',ord:false,largura:'110px',fmt:l=>
        (pode('pendencia.resolver') && ['ABERTA','EM_ANALISE'].includes(l.status))
          ? el('button',{class:'btn pequeno',onclick:()=>resolverPendencia(l,t)},'Resolver') : null}],
    aoCarregar:d=>{
      if(!d.resumo) return;
      const porSev = {};
      d.resumo.forEach(r=>porSev[r.severidade]=(porSev[r.severidade]||0)+r.n);
      resumo.replaceChildren(...['CRITICA','ALTA','MEDIA','BAIXA'].map(s=>
        el('div',{class:'card'+(s==='CRITICA'?' at-crit':s==='ALTA'?' at-warn':'')},
          el('div',{class:'rot'},'Severidade '+s.toLowerCase()),
          el('div',{class:'val'},int(porSev[s]||0)))));
    }});
  c.replaceChildren(crumbs({rot:'Pendências'}),
    cabecalho('Pendências','Fila operacional gerada pela consolidação. Resolver registra usuário, data, valores e justificativa na auditoria.'),
    resumo, t.node);
}

function resolverPendencia(l, t){
  const status = el('select',{},
    el('option',{value:'RESOLVIDA'},'Resolvida'),
    el('option',{value:'EM_ANALISE'},'Em análise'),
    el('option',{value:'IGNORADA'},'Ignorada (exige justificativa)'));
  const valorNovo = el('input',{placeholder:'Valor novo / o que foi corrigido'});
  const just = el('textarea',{rows:3,placeholder:'Justificativa'});
  modal('Resolver pendência',
    el('div',{},
      el('p',{}, seloStatus(l.severidade), ' ', el('b',{},l.tipo)),
      el('p',{},el('b',{},'Registro: '), l.registro),
      el('p',{},el('b',{},'Problema: '), l.problema),
      l.sugestao?el('p',{class:'muted'},'Sugestão: '+l.sugestao):null,
      el('div',{class:'campo'},el('label',{},'Nova situação'),status),
      el('div',{class:'campo'},el('label',{},'Valor novo (opcional)'),valorNovo),
      el('div',{class:'campo'},el('label',{},'Justificativa'),just)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       try{
         await api('/api/pendencia/'+l.id,{method:'POST',body:{status:status.value,
           justificativa:just.value, valor_anterior:l.problema, valor_novo:valorNovo.value}});
         fecharSobreposicoes(); toast('Pendência atualizada.'); t.recarregar();
       }catch(ex){ toast(ex.message); }
     }},'Salvar')]);
}

/* ======================= COTAÇÕES ======================= */
function telaCotacoes(c, grupo){
  const rot={andamento:'Cotações em andamento',aguardando:'Aguardando fornecedor',finalizadas:'Cotações finalizadas'};
  const t = Tabela({rota:'/api/cotacoes', semExport:true, tela:'cotacoes-'+grupo,
    filtrosIniciais:{grupo}, placeholder:'Número do processo ou requisição…',
    colunas:[
      {k:'numero',rot:'Processo',ord:false,fmt:l=>el('a',{style:'cursor:pointer',
        onclick:()=>location.hash='#/cotacao/'+l.id},l.numero)},
      {k:'requisicao',rot:'Requisição',ord:false},
      {k:'titulo',rot:'Título',tipo:'trunc',ord:false,largura:'22%'},
      {k:'status',rot:'Status',ord:false,fmt:l=>seloStatus(l.status)},
      {k:'itens',rot:'Itens',tipo:'num',ord:false},
      {k:'convidados',rot:'Convidados',tipo:'num',ord:false},
      {k:'respostas',rot:'Respostas',tipo:'num',ord:false},
      {k:'comprador',rot:'Comprador',ord:false},
      {k:'prazo_resposta',rot:'Prazo',ord:false,fmt:l=>l.prazo_resposta||'—'},
      {k:'criado_em',rot:'Criada em',ord:false,fmt:l=>dataBR(l.criado_em)}]});
  c.replaceChildren(crumbs({rot:'Cotações'},{rot:rot[grupo]||grupo}),
    cabecalho(rot[grupo]||'Cotações','O processo de cotação é o centro da negociação: itens, convidados, disparos, respostas e decisão ficam vinculados a ele.',
      pode('cotacao.criar')?el('button',{class:'btn primario',onclick:()=>location.hash='#/cotacoes/nova'},'Nova cotação'):null),
    t.node);
}

function telaNovaCotacao(c){
  c.replaceChildren(crumbs({rot:'Cotações',rota:'cotacoes/andamento'},{rot:'Nova cotação'}),
    cabecalho('Nova cotação','Busque o material e o sistema sugere os fornecedores com o motivo de cada sugestão.'),
    el('div',{class:'painel'}, el('div',{class:'corpo'},
      el('p',{},'Comece pelo material: pesquise o PN no campo acima ou use o botão abaixo.'),
      el('div',{class:'campo'}, el('label',{},'PN do material'),
        el('input',{id:'pnNovo',placeholder:'ex.: MAN013681'})),
      el('button',{class:'btn primario',onclick:()=>{
        const pn = document.getElementById('pnNovo').value.trim();
        if(pn) modalNovaCotacao(pn); else toast('Informe o PN.');
      }},'Continuar'))));
}

async function modalNovaCotacao(pn){
  const m = await api('/api/material/'+encodeURIComponent(pn));
  const s = await api('/api/cotacoes/sugestao/'+encodeURIComponent(pn));
  const qtd = el('input',{type:'number',min:'1',value:'1'});
  const prazo = el('input',{type:'datetime-local'});
  const req = el('input',{placeholder:'RDA / requisição (opcional)'});
  const obs = el('textarea',{rows:2,placeholder:'Observações para o fornecedor'});
  const convidados = s.sugestoes.map(x=>({...x}));
  const lista = el('div',{});
  const pintarLista=()=>{
    lista.replaceChildren(...convidados.map((x,i)=>el('label',{class:'opcao'},
      el('input',{type:'checkbox',checked:x.marcado||null,'data-i':i,
        onchange:e=>convidados[i].marcado=e.target.checked}),
      el('div',{}, el('div',{class:'nm'},x.nome),
        el('div',{class:'mv'},x.email+' · '+x.motivo)))));
    if(!convidados.length) lista.append(el('div',{class:'muted'},
      'Nenhum fornecedor com e-mail encontrado no histórico nem na categoria deste material. '+
      'Use "Adicionar fornecedor" abaixo para convidar alguém do cadastro.'));
  };
  pintarLista();
  const buscaF = el('input',{placeholder:'Adicionar fornecedor: nome ou código SAP…'});
  const achados = el('div',{style:'max-height:150px;overflow:auto'});
  let tf=null;
  buscaF.addEventListener('input',()=>{clearTimeout(tf);tf=setTimeout(async()=>{
    if(buscaF.value.trim().length<2){achados.replaceChildren();return;}
    const r = await api('/api/fornecedores?por_pagina=10&q='+encodeURIComponent(buscaF.value.trim()));
    achados.replaceChildren(...r.linhas.map(f=>el('div',{class:'opcao',style:'cursor:pointer',
      onclick:async()=>{
        const det = await api('/api/fornecedor/'+f.id);
        const ct = det.contatos.find(c=>c.email);
        if(!ct){ toast('Esse fornecedor não tem e-mail cadastrado.'); return; }
        if(convidados.some(c=>c.email===ct.email)){ toast('Fornecedor já está na lista.'); return; }
        convidados.push({fornecedor_id:f.id, nome:f.razao_social, email:ct.email,
          motivo:'adicionado manualmente pelo comprador', marcado:true, origem:'MANUAL'});
        pintarLista(); achados.replaceChildren(); buscaF.value='';
      }},
      el('div',{}, el('div',{class:'nm'},f.razao_social),
        el('div',{class:'mv'},`código ${f.codigo_sap||'—'} · ${f.emails} e-mail(s) · ${f.compras} compra(s)`)))));
  },250);});
  const mm=m.metricas||{};
  modal('Nova cotação',
    el('div',{},
      el('p',{}, el('b',{},'Material: '), `${m.material.pn} — ${m.material.descricao||''}`),
      el('div',{class:'kpis'},
        kpiSimples('Último preço',dinheiro(mm.ultimo_preco),dataBR(mm.ultimo_preco_data)),
        kpiSimples('Estoque',int(m.material.estoque_atual)),
        kpiSimples('Consumo médio',mm.consumo_12m?num(mm.consumo_12m/12,1)+'/mês':'—'),
        kpiSimples('Cobertura',mm.cobertura_meses!=null?num(mm.cobertura_meses,1)+' m':'—')),
      el('div',{class:'linha2'},
        el('div',{class:'campo'},el('label',{},'Quantidade'),qtd),
        el('div',{class:'campo'},el('label',{},'Prazo de resposta'),prazo)),
      el('div',{class:'campo'},el('label',{},'Requisição'),req),
      el('div',{class:'campo'},el('label',{},'Observações'),obs),
      el('div',{class:'campo'},el('label',{},'Fornecedores sugeridos'),lista),
      el('div',{class:'campo'},el('label',{},'Adicionar fornecedor'),buscaF,achados)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       const marcados=convidados.filter(x=>x.marcado);
       if(!marcados.length){toast('Selecione ao menos um fornecedor.');return;}
       const r = await api('/api/cotacoes',{method:'POST',body:{
         requisicao:req.value, prazo_resposta:prazo.value, observacoes:obs.value,
         itens:[{pn:m.material.pn, descricao:m.material.descricao, quantidade:+qtd.value, um:m.material.umb}],
         fornecedores:marcados.map(x=>({fornecedor_id:x.fornecedor_id,email:x.email,motivo:x.motivo}))}});
       fecharSobreposicoes(); toast('Processo '+r.numero+' criado.');
       location.hash='#/cotacao/'+r.id;
     }},'Criar processo')]);
}

async function telaCotacao(c, id){
  const d = await api('/api/cotacao/'+id);
  const p = d.processo;
  const acoes = el('div',{class:'acoes'},
    pode('cotacao.enviar') && p.status==='RASCUNHO' ? el('button',{class:'btn primario',
      onclick:()=>confirmar('Enviar cotação',
        `Enviar a solicitação para ${d.fornecedores.length} fornecedor(es)?`, async()=>{
          const r = await api('/api/cotacoes/enviar',{method:'POST',body:{processo_id:p.id}});
          toast(r.dry_run?'Envio simulado (DRY_RUN ligado).':'Cotação enviada.');
          telaCotacao(c,id);
        },'Enviar')},'Enviar cotação') : null,
    el('button',{class:'btn',onclick:()=>abrirMapa(id)},'Mapa de cotação'),
    pode('cotacao.ver')?el('select',{onchange:async e=>{
      await api('/api/cotacao/'+id+'/status',{method:'POST',body:{status:e.target.value}});
      toast('Status atualizado.'); telaCotacao(c,id);
    }}, ...['RASCUNHO','EM_APROVACAO','ENVIADO','AGUARDANDO','RESPONDIDO','EM_NEGOCIACAO','FINALIZADO','CANCELADO']
      .map(s=>el('option',{value:s,selected:s===p.status||null},s.replace(/_/g,' ').toLowerCase()))):null);

  const itens = el('div',{class:'painel'}, el('h2',{},'Itens'),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['#','PN','Descrição','Qtde','UM','Contexto de compra'].map(h=>el('th',{},h)))),
      el('tbody',{},...d.itens.map(i=>el('tr',{},
        el('td',{},i.linha), el('td',{},el('a',{class:'pn',style:'cursor:pointer',
          onclick:()=>location.hash='#/material/'+encodeURIComponent(i.pn)},i.pn)),
        el('td',{class:'trunc'},i.descricao||'—'), el('td',{class:'num'},int(i.quantidade)),
        el('td',{},i.um||'—'),
        el('td',{},el('button',{class:'btn pequeno',onclick:()=>verContexto(i.pn)},'Ver histórico'))))))));

  const forns = el('div',{class:'painel'}, el('h2',{},'Fornecedores convidados'),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['Fornecedor','E-mail','Motivo do convite','Status','Enviado em','Registrar resposta'].map(h=>el('th',{},h)))),
      el('tbody',{},...d.fornecedores.map(f=>el('tr',{},
        el('td',{},f.nome||'—'), el('td',{},f.email),
        el('td',{class:'trunc'},f.motivo_convite||'—'), el('td',{},seloStatus(f.status)),
        el('td',{},dataBR(f.enviado_em)),
        el('td',{},el('button',{class:'btn pequeno',
          onclick:()=>registrarResposta(id,d,f)},'Registrar'))))))));

  const emails = d.emails.length?el('div',{class:'painel'}, el('h2',{},'E-mails disparados'),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['Data','Destinatário','Assunto','Status'].map(h=>el('th',{},h)))),
      el('tbody',{},...d.emails.map(e=>el('tr',{},
        el('td',{},dataBR(e.enviado_em)), el('td',{},e.destinatario),
        el('td',{class:'trunc'},e.assunto), el('td',{},seloStatus(e.status)))))))):null;

  c.replaceChildren(crumbs({rot:'Cotações',rota:'cotacoes/andamento'},{rot:p.numero}),
    el('div',{class:'ficha-topo'}, el('div',{class:'linha'},
      el('div',{}, el('div',{class:'pnum'},p.numero),
        el('h1',{},p.titulo||'Cotação'),
        el('div',{class:'meta'}, el('span',{},'Status: '), seloStatus(p.status),
          el('span',{},'Requisição: '+(p.requisicao||'—')),
          el('span',{},'Comprador: '+(p.comprador||'—')),
          el('span',{},'Prazo: '+(p.prazo_resposta||'—')),
          el('span',{},'Criada em '+dataBR(p.criado_em)))),
      acoes)),
    itens, forns, emails);
}

function registrarResposta(pid, d, f){
  const item = el('select',{}, ...d.itens.map(i=>el('option',{value:i.id},`${i.pn} — ${i.descricao||''}`)));
  const preco=el('input',{type:'number',step:'0.0001'}), frete=el('input',{type:'number',step:'0.01'});
  const imp=el('input',{type:'number',step:'0.01'}), lt=el('input',{type:'number'});
  const cond=el('input',{placeholder:'ex.: 28 ddl'}), inco=el('input',{placeholder:'ex.: FOB'});
  const val=el('input',{type:'date'}), moq=el('input',{type:'number'});
  modal('Registrar resposta — '+(f.nome||f.email),
    el('div',{},
      el('div',{class:'campo'},el('label',{},'Item'),item),
      el('div',{class:'linha2'},
        el('div',{class:'campo'},el('label',{},'Preço unitário (BRL)'),preco),
        el('div',{class:'campo'},el('label',{},'Lead time (dias)'),lt)),
      el('div',{class:'linha2'},
        el('div',{class:'campo'},el('label',{},'Frete'),frete),
        el('div',{class:'campo'},el('label',{},'Impostos'),imp)),
      el('div',{class:'linha2'},
        el('div',{class:'campo'},el('label',{},'Condição de pagamento'),cond),
        el('div',{class:'campo'},el('label',{},'Incoterm'),inco)),
      el('div',{class:'linha2'},
        el('div',{class:'campo'},el('label',{},'Validade'),val),
        el('div',{class:'campo'},el('label',{},'MOQ'),moq))),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       const it = d.itens.find(x=>x.id==item.value);
       await api('/api/cotacao/'+pid+'/resposta',{method:'POST',body:{
         processo_item_id:+item.value, processo_fornecedor_id:f.id,
         preco_unitario:+preco.value||null, quantidade:it.quantidade,
         frete:+frete.value||null, impostos:+imp.value||null, lead_time_dias:+lt.value||null,
         condicao_pagamento:cond.value, incoterm:inco.value, validade:val.value, moq:+moq.value||null}});
       fecharSobreposicoes(); toast('Resposta registrada.'); telaCotacao($('#conteudo'), pid);
     }},'Salvar resposta')]);
}

async function abrirMapa(id){
  const m = await api('/api/cotacao/'+id+'/mapa');
  const cab = el('tr',{}, el('th',{},'Item'), el('th',{class:'right'},'Referência'),
    ...m.fornecedores.map(f=>el('th',{class:'right'},f.nome)));
  const corpo = m.linhas.map(l=>el('tr',{},
    el('td',{}, el('div',{},el('b',{},l.item.pn)), el('div',{class:'muted trunc'},l.item.descricao||''),
      el('div',{class:'muted'},int(l.item.quantidade)+' '+(l.item.um||''))),
    el('td',{class:'num'},
      el('div',{title:'último preço pago'},dinheiro(l.contexto.ultimo_preco)),
      el('div',{class:'muted',title:'preço mestre MM60'},'MM60 '+dinheiro(l.contexto.mm60)),
      el('div',{class:'muted',title:'média ponderada 12 meses'},'12M '+dinheiro(l.contexto.media_12m))),
    ...l.celulas.map(cl=>el('td',{class:'num'},
      cl.preco==null?el('span',{class:'muted'},'sem resposta'):
        el('div',{},
          el('div',{}, cl.menor?el('span',{class:'selo ok',title:'menor preço deste item'},'▼ '):null,
            dinheiro(cl.preco)),
          cl.lead_time?el('div',{class:'muted'},cl.lead_time+' dias'):null,
          cl.condicao?el('div',{class:'muted'},cl.condicao):null,
          l.contexto.ultimo_preco?el('div',{class:'muted',title:'contra o último preço pago'},
            pctSinal((cl.preco-l.contexto.ultimo_preco)/l.contexto.ultimo_preco)):null)))));
  drawer('Mapa de cotação',
    el('div',{},
      el('div',{class:'muted',style:'margin-bottom:8px;font-size:12px'},
        'Menor preço destacado por item. A escolha do fornecedor continua sendo do comprador — preço não é o único critério.'),
      el('div',{style:'overflow:auto'}, el('table',{class:'dados'},
        el('thead',{},cab), el('tbody',{},...corpo)))));
}

/* ======================= RELATÓRIOS / ADMIN ======================= */
async function telaRelatorios(c){
  const d = await api('/api/dashboard');
  c.replaceChildren(crumbs({rot:'Relatórios'}),
    cabecalho('Relatórios','Exportações rápidas com os filtros já aplicados nas telas operacionais.'),
    el('div',{class:'cards'},
      ...[['Materiais do almoxarifado','/api/materiais/export?almoxarifado=1'],
          ['Materiais sem fornecedor','/api/materiais/export?sem_fornecedor=1&almoxarifado=1'],
          ['Materiais com divergência de preço','/api/materiais/export?divergencia=1'],
          ['Risco de ruptura','/api/materiais/export?risco=RUPTURA'],
          ['Sem movimentação','/api/materiais/export?risco=SEM_MOVIMENTO']]
        .map(([rot,url])=>el('div',{class:'card clicavel',onclick:()=>location.href=url},
          el('div',{class:'rot'},rot), el('div',{class:'val',style:'font-size:14px'},'Exportar CSV/Excel')))),
    el('div',{class:'painel'}, el('h2',{},'Indicadores atuais'),
      el('div',{class:'corpo'}, el('table',{class:'dados'}, el('tbody',{},
        ...Object.entries(d.cards).map(([k,v])=>el('tr',{},
          el('td',{class:'muted'},k.replace(/_/g,' ')),
          el('td',{class:'num'}, k.includes('valor')||k.includes('oportunidade')?dinheiro(v):int(v)))))))));
}

async function telaUsuarios(c){
  const us = await api('/api/usuarios');
  const linhas = us.map(u=>el('tr',{},
    el('td',{},u.nome), el('td',{},u.email),
    el('td',{},el('span',{class:'selo info'},u.perfil.toLowerCase())),
    el('td',{},u.ativo?el('span',{class:'selo ok'},'ativo'):el('span',{class:'selo neutro'},'inativo')),
    el('td',{},dataBR(u.ultimo_acesso))));
  c.replaceChildren(crumbs({rot:'Administração'},{rot:'Usuários'}),
    cabecalho('Usuários','Perfis definem as permissões, aplicadas também no backend.',
      el('button',{class:'btn primario',onclick:()=>novoUsuario(c)},'Novo usuário')),
    el('div',{class:'painel'}, el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['Nome','E-mail','Perfil','Situação','Último acesso'].map(h=>el('th',{},h)))),
      el('tbody',{},...linhas)))));
}

function novoUsuario(c){
  const nome=el('input',{}), email=el('input',{type:'email'}), senha=el('input',{type:'password'});
  const perfil=el('select',{},...['SOLICITANTE','ALMOXARIFE','COMPRADOR','GESTOR','ADMIN']
    .map(p=>el('option',{value:p},p.toLowerCase())));
  modal('Novo usuário', el('div',{},
    el('div',{class:'campo'},el('label',{},'Nome'),nome),
    el('div',{class:'campo'},el('label',{},'E-mail'),email),
    el('div',{class:'campo'},el('label',{},'Perfil'),perfil),
    el('div',{class:'campo'},el('label',{},'Senha provisória'),senha)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       await api('/api/usuarios',{method:'POST',body:{nome:nome.value,email:email.value,
         perfil:perfil.value,senha:senha.value}});
       fecharSobreposicoes(); toast('Usuário criado.'); telaUsuarios(c);
     }},'Criar')]);
}

function telaAuditoria(c){
  const t = Tabela({rota:'/api/auditoria', semExport:true, tela:'auditoria',
    placeholder:'Registro ou detalhe…',
    filtros:[{k:'entidade',tipo:'select',rot:'Entidade',
        opcoes:[{v:'material',r:'Material'},{v:'fornecedor',r:'Fornecedor'},{v:'processo',r:'Cotação'},
                {v:'pendencia',r:'Pendência'},{v:'usuario',r:'Usuário'}]},
      {k:'usuario',tipo:'text',rot:'Usuário'}],
    colunas:[
      {k:'criado_em',rot:'Data/hora',ord:false,fmt:l=>dataBR(l.criado_em)+' '+String(l.criado_em||'').slice(11,16)},
      {k:'usuario_email',rot:'Usuário',ord:false},
      {k:'entidade',rot:'Entidade',ord:false},
      {k:'entidade_id',rot:'Registro',ord:false},
      {k:'acao',rot:'Ação',ord:false},
      {k:'detalhe',rot:'Detalhe',ord:false,fmt:l=>detalheAuditoria(l.detalhe)},
      {k:'ip',rot:'Origem',ord:false}]});
  c.replaceChildren(crumbs({rot:'Administração'},{rot:'Auditoria'}),
    cabecalho('Auditoria','Toda alteração relevante registra usuário, data/hora, entidade, ação, valor anterior e posterior.'),
    t.node);
}
