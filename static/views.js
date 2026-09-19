/* Portal de Cotações — telas */

async function renderizar(rota, c){
  const p = rota.split('/');
  if(rota==='dashboard')                 return telaDashboard(c);
  if(p[0]==='materiais' && p[1]==='sem-fornecedor') return telaSemFornecedor(c);
  if(p[0]==='materiais')                 return telaMateriais(c);
  if(p[0]==='material')                  return telaFicha(c, decodeURIComponent(p.slice(1).join('/')));
  if(p[0]==='categorias')                return telaCategorias(c);
  if(p[0]==='estoque' && p[1]==='consumo') return telaConsumo(c);
  if(p[0]==='estoque')                   return telaEstoque(c, p[1]||'geral');
  if(p[0]==='precos')                    return telaPrecos(c, p[1]||'geral');
  if(p[0]==='sap')                       return telaSap(c, p[1]||'compras');
  if(p[0]==='fornecedores')              return telaFornecedores(c, p[1]);
  if(p[0]==='fornecedor')                return telaFornecedor(c, p[1]);
  if(p[0]==='pendencias')                return telaPendencias(c);
  if(p[0]==='relatorios')                return telaRelatorios(c);
  if(p[0]==='admin' && p[1]==='usuarios')  return telaUsuarios(c);
  if(p[0]==='admin' && p[1]==='auditoria') return telaAuditoria(c);
  if(p[0]==='cotacoes' && p[1]==='nova')   return telaNovaCotacao(c);
  if(p[0]==='cotacoes')                  return telaCotacoes(c, p[1]||'andamento');
  if(p[0]==='cotacao')                   return telaCotacao(c, p[1]);
  c.replaceChildren(el('div',{class:'vazio'},'Tela não encontrada.'));
}

/* ======================= DASHBOARD ======================= */
async function telaDashboard(c){
  const d = await api('/api/dashboard');
  const perfil = d.perfil;
  const card=(rot,val,pe,cls,rota)=>el('div',{class:'card'+(cls?' '+cls:'')+(rota?' clicavel':''),
    onclick:rota?()=>location.hash='#/'+rota:null},
    el('div',{class:'rot'},rot), el('div',{class:'val'},val), pe?el('div',{class:'pe'},pe):null);

  const cardsPorPerfil = {
    ALMOXARIFE:[
      card('Materiais do almoxarifado',int(d.cards.materiais_almox),'cadastrados na BASE/Controle',null,'materiais?almoxarifado=1'),
      card('Risco de ruptura',int(d.cards.ruptura),'cobertura abaixo do lead time','at-crit','estoque/ruptura'),
      card('Sem movimentação',int(d.cards.sem_movimento),'12 meses sem consumo','at-warn','estoque/parado'),
      card('Valor em estoque',dinheiro(d.cards.valor_estoque),'estoque × preço mestre',null,'estoque/geral'),
      card('Sem fornecedor',int(d.cards.sem_fornecedor),'sem cadastro mestre','at-warn','materiais/sem-fornecedor')],
    COMPRADOR:[
      card('Cotações abertas',int(d.cards.cotacoes_abertas),'em andamento',null,'cotacoes/andamento'),
      card('Aguardando fornecedor',int(d.cards.cotacoes_aguardando),'enviadas sem resposta','at-warn','cotacoes/aguardando'),
      card('Oportunidade indicativa',dinheiro(d.cards.oportunidade_valor),'diferença anualizada potencial','at-ok','precos/oportunidades'),
      card('Divergências de preço',int(d.cards.divergencias),'acima de 30%','at-warn','precos/divergencias'),
      card('Sem fornecedor',int(d.cards.sem_fornecedor),'materiais a vincular','at-warn','materiais/sem-fornecedor'),
      card('Risco de ruptura',int(d.cards.ruptura),'antecipar compra','at-crit','estoque/ruptura')],
    GESTOR:[
      card('Valor em estoque',dinheiro(d.cards.valor_estoque),'estoque × preço mestre'),
      card('Oportunidade indicativa',dinheiro(d.cards.oportunidade_valor),'não é saving realizado','at-ok','precos/oportunidades'),
      card('Cotações abertas',int(d.cards.cotacoes_abertas),null,null,'cotacoes/andamento'),
      card('Fornecedores ativos',int(d.cards.fornecedores),null,null,'fornecedores'),
      card('Materiais cadastrados',int(d.cards.materiais)),
      card('Risco de ruptura',int(d.cards.ruptura),null,'at-crit','estoque/ruptura')],
  };
  const cards = cardsPorPerfil[perfil] || [
    card('Materiais cadastrados',int(d.cards.materiais)),
    card('Cotações abertas',int(d.cards.cotacoes_abertas),null,null,'cotacoes/andamento'),
    card('Risco de ruptura',int(d.cards.ruptura),null,'at-crit','estoque/ruptura')];

  const avisos = d.atencao.map(a=>el('div',{class:'aviso'+(a.texto.includes('crítica')?' critico':'')},
    el('span',{},'⚠'), el('div',{class:'txt'},a.texto),
    el('button',{onclick:()=>location.hash=a.rota},a.acao)));

  const consumo = el('div',{class:'painel'},
    el('h2',{},'Consumo mensal — últimos 12 meses',
      el('div',{class:'acoes'}, el('button',{class:'btn pequeno',
        onclick:()=>location.hash='#/estoque/consumo'},'Detalhar'))),
    el('div',{class:'corpo'},
      grafBarras({dados:d.consumo.map(m=>({r:mesBR(m.ano_mes),v:m.valor})),formato:abrev}),
      el('div',{class:'legenda'},el('span',{},'Valor consumido por mês (movimentos de saída do SAP).'))));

  const precos = el('div',{class:'painel'},
    el('h2',{},'Compras por mês'),
    el('div',{class:'corpo'},
      grafLinha({series:[{cor:'var(--brand)',pontos:d.precos.map(m=>({y:m.valor,dica:`${mesBR(m.mes)}: ${dinheiro(m.valor)} em ${m.n} documento(s)`}))}],
        labels:d.precos.map(m=>mesBR(m.mes)), formato:abrev}),
      el('div',{class:'legenda'},el('span',{},el('i',{style:'background:var(--brand)'}),'Valor comprado (ME2N/ME5A/MB51)'))));

  const cats = el('div',{class:'painel'}, el('h2',{},'Compras por categoria'),
    el('div',{class:'corpo'}, barrasH({dados:d.categorias.map(x=>({r:x.cat,v:x.valor}))})));
  const forns = el('div',{class:'painel'}, el('h2',{},'Principais fornecedores'),
    el('div',{class:'corpo'}, barrasH({dados:d.fornecedores.map(x=>({r:x.nome,v:x.valor}))})));

  const oport = el('div',{class:'painel'},
    el('h2',{},'Oportunidades indicativas',
      el('div',{class:'acoes'},el('button',{class:'btn pequeno',onclick:()=>location.hash='#/precos/oportunidades'},'Ver todas'))),
    el('div',{class:'rolagem'}, el('table',{class:'dados'},
      el('thead',{},el('tr',{},...['PN','Descrição','MM60','Último preço','Diferença','Consumo 12M','Oportunidade indicativa']
        .map((h,i)=>el('th',{class:i>1?'right':''},h)))),
      el('tbody',{}, ...d.oportunidades.map(o=>el('tr',{},
        el('td',{},el('a',{class:'pn',onclick:()=>location.hash='#/material/'+o.pn,style:'cursor:pointer'},o.pn)),
        el('td',{class:'trunc',title:o.descricao},o.descricao||'—'),
        el('td',{class:'num'},dinheiro(o.mm60)),
        el('td',{class:'num'},dinheiro(o.ultimo_preco)),
        el('td',{class:'num'},pctSinal(o.divergencia_pct)),
        el('td',{class:'num'},int(o.consumo_12m)),
        el('td',{class:'num'},dinheiro(o.oportunidade)))))) ),
    el('div',{class:'rodape-tab'},'Diferença anualizada potencial entre o preço mestre e o último preço pago. '+
      'Não é saving: só vira economia quando houver negociação ou compra que comprove.'));

  c.replaceChildren(
    cabecalho(`${(h=>h<12?'Bom dia':h<18?'Boa tarde':'Boa noite')(new Date().getHours())}, ${S.user.nome.split(' ')[0]}`,
      `Visão de ${perfil.charAt(0)+perfil.slice(1).toLowerCase()} · dados consolidados do SAP e do almoxarifado`),
    ...avisos,
    el('div',{class:'cards'}, ...cards),
    el('div',{class:'grid2'}, consumo, precos),
    el('div',{class:'grid2'}, cats, forns),
    oport);
}

/* ======================= MATERIAIS ======================= */
function telaMateriais(c){
  const t = Tabela({
    rota:'/api/materiais', rotaExport:'/api/materiais/export', tela:'materiais',
    filtrosIniciais:S.params, ordemPadrao:'pn',
    placeholder:'PN ou descrição…',
    filtros:[
      {k:'categoria',tipo:'text',rot:'Categoria'},
      {k:'fornecedor',tipo:'text',rot:'Fornecedor'},
      {k:'risco',tipo:'select',rot:'Situação de estoque',
        opcoes:[{v:'RUPTURA',r:'Risco de ruptura'},{v:'BAIXO',r:'Estoque baixo'},{v:'OK',r:'Normal'},
                {v:'ELEVADO',r:'Estoque elevado'},{v:'SEM_MOVIMENTO',r:'Sem movimentação'}]},
      {k:'classe_abc',tipo:'select',rot:'Curva ABC',opcoes:[{v:'A',r:'Classe A'},{v:'B',r:'Classe B'},{v:'C',r:'Classe C'}]},
      {k:'preco_min',tipo:'number',rot:'Preço mín.'},
      {k:'preco_max',tipo:'number',rot:'Preço máx.'},
      {k:'compra_desde',tipo:'date',rot:'Comprado desde'},
      {k:'almoxarifado',tipo:'check',rot:'Só almoxarifado'},
      {k:'sem_fornecedor',tipo:'check',rot:'Sem fornecedor'},
      {k:'divergencia',tipo:'check',rot:'Com divergência'}],
    colunas:[
      {k:'pn',rot:'PN',largura:'110px',fmt:l=>el('a',{class:'pn',style:'cursor:pointer',
        onclick:()=>location.hash='#/material/'+encodeURIComponent(l.pn)},l.pn)},
      {k:'descricao',rot:'Descrição',tipo:'trunc',largura:'24%'},
      {k:'categoria',rot:'Categoria',tipo:'trunc',largura:'140px'},
      {k:'estoque_atual',rot:'Estoque',tipo:'num',fmt:l=>int(l.estoque_atual)},
      {k:'consumo_mes',rot:'Consumo médio',tipo:'num',fmt:l=>l.consumo_mes?num(l.consumo_mes,1)+'/mês':'—'},
      {k:'ultimo_preco',rot:'Último preço',tipo:'num',fmt:l=>dinheiro(l.ultimo_preco)},
      {k:'mm60',rot:'MM60',tipo:'num',fmt:l=>dinheiro(l.mm60)},
      {k:'divergencia_pct',rot:'Diferença',tipo:'num',fmt:l=>seloDivergencia(l.divergencia_pct,l.escala_suspeita)},
      {k:'ultimo_fornecedor',rot:'Último fornecedor',tipo:'trunc',largura:'150px',
        fmt:l=>l.ultimo_fornecedor||l.fornecedor_cadastro||'—'},
      {k:'ultima_compra',rot:'Última compra',tipo:'num',fmt:l=>dataBR(l.ultima_compra)},
      {k:'risco',rot:'Situação',fmt:l=>seloRisco(l.risco)}],
  });
  c.replaceChildren(crumbs({rot:'Materiais'},{rot:'Consultar materiais'}),
    cabecalho('Materiais','Base consolidada: cadastro do almoxarifado, dados mestre MM60, estoque, consumo e histórico de compras.'),
    t.node);
}

async function telaSemFornecedor(c){
  const t = Tabela({
    rota:'/api/sem-fornecedor', semExport:true, tela:'sem-fornecedor',
    placeholder:'PN ou descrição…',
    filtros:[{k:'com_sugestao',tipo:'check',rot:'Só com sugestão do histórico'}],
    colunas:[
      {k:'pn',rot:'PN',largura:'110px',ord:false,fmt:l=>el('a',{class:'pn',style:'cursor:pointer',
        onclick:()=>location.hash='#/material/'+encodeURIComponent(l.pn)},l.pn)},
      {k:'descricao',rot:'Descrição',tipo:'trunc',ord:false,largura:'24%'},
      {k:'estoque_atual',rot:'Estoque',tipo:'num',ord:false,fmt:l=>int(l.estoque_atual)},
      {k:'sugerido_nome',rot:'Fornecedor sugerido',ord:false,tipo:'trunc',largura:'190px',
        fmt:l=>l.sugerido_nome?el('span',{},l.sugerido_nome):el('span',{class:'muted'},'sem sugestão')},
      {k:'motivo',rot:'Motivo',ord:false,tipo:'trunc',largura:'26%',fmt:l=>l.motivo||'Nenhuma compra registrada para este PN'},
      {k:'acoes',rot:'',ord:false,largura:'250px',fmt:l=>el('div',{style:'display:flex;gap:5px'},
        l.sugerido_id && pode('vinculo.confirmar') ? el('button',{class:'btn pequeno',
          onclick:()=>confirmarVinculo(l,t)},'Confirmar vínculo') : null,
        pode('vinculo.confirmar') ? el('button',{class:'btn pequeno',
          onclick:()=>escolherOutro(l,t)},'Outro fornecedor') : null,
        l.sugerido_id && pode('vinculo.confirmar') ? el('button',{class:'btn pequeno',
          onclick:()=>ignorarSugestao(l,t)},'Ignorar') : null,
        el('button',{class:'btn pequeno',onclick:()=>verContexto(l.pn)},'Ver histórico'))}],
  });
  c.replaceChildren(crumbs({rot:'Materiais',rota:'materiais'},{rot:'Sem fornecedor'}),
    cabecalho('Materiais sem fornecedor',
      'O sistema pesquisa o histórico de compras e sugere o fornecedor predominante. '+
      'Nada é alterado no cadastro mestre sem a decisão de uma pessoa — toda confirmação gera auditoria.'),
    t.node);
}

function confirmarVinculo(l, t){
  const just = el('textarea',{rows:2,placeholder:'Observação (opcional)'});
  modal('Confirmar fornecedor do material',
    el('div',{},
      el('p',{},el('b',{},l.pn+' — '), l.descricao||''),
      el('div',{class:'kpis'},
        el('div',{class:'kpi'},el('div',{class:'r'},'Fornecedor cadastrado'),el('div',{class:'v',style:'font-size:14px'},'Não definido')),
        el('div',{class:'kpi'},el('div',{class:'r'},'Fornecedor sugerido'),el('div',{class:'v',style:'font-size:14px'},l.sugerido_nome))),
      el('p',{class:'muted'},'Motivo: '+(l.motivo||'')),
      el('div',{class:'campo'},el('label',{},'Justificativa / observação'),just)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       await api('/api/material/'+encodeURIComponent(l.pn)+'/fornecedor',{method:'POST',
         body:{fornecedor_id:l.sugerido_id, origem:'HISTORICO_SAP',
               origem_texto:'sugestão baseada no histórico SAP', justificativa:just.value}});
       fecharSobreposicoes(); toast('Vínculo confirmado e registrado na auditoria.'); t.recarregar();
     }},'Confirmar vínculo')]);
}

async function escolherOutro(l, t){
  const busca = el('input',{placeholder:'Buscar fornecedor pelo nome ou código…'});
  const lista = el('div',{style:'max-height:260px;overflow:auto;margin-top:8px'});
  let escolhido=null;
  let tm=null;
  busca.addEventListener('input',()=>{clearTimeout(tm);tm=setTimeout(async()=>{
    const d = await api('/api/fornecedores?por_pagina=20&q='+encodeURIComponent(busca.value));
    lista.replaceChildren(...d.linhas.map(f=>el('label',{class:'opcao'},
      el('input',{type:'radio',name:'forn',onchange:()=>escolhido=f.id}),
      el('div',{},el('div',{class:'nm'},f.razao_social),
        el('div',{class:'mv'},`código ${f.codigo_sap||'—'} · ${f.emails} e-mail(s) · ${f.compras} compra(s) no histórico`)))));
  },250);});
  const just = el('textarea',{rows:2,placeholder:'Justificativa'});
  modal('Selecionar outro fornecedor para '+l.pn,
    el('div',{}, busca, lista, el('div',{class:'campo',style:'margin-top:10px'},
      el('label',{},'Justificativa'), just)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       if(!escolhido){toast('Selecione um fornecedor.');return;}
       await api('/api/material/'+encodeURIComponent(l.pn)+'/fornecedor',{method:'POST',
         body:{fornecedor_id:escolhido, origem:'MANUAL', origem_texto:'seleção manual do comprador',
               justificativa:just.value}});
       fecharSobreposicoes(); toast('Fornecedor vinculado.'); t.recarregar();
     }},'Vincular')]);
}

function ignorarSugestao(l, t){
  const just = el('textarea',{rows:2,placeholder:'Por que a sugestão não serve?'});
  modal('Ignorar sugestão', el('div',{}, el('p',{},`PN ${l.pn} — sugestão: ${l.sugerido_nome}`),
      el('div',{class:'campo'},el('label',{},'Justificativa'),just)),
    [el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
     el('button',{class:'btn primario',onclick:async()=>{
       await api('/api/material/'+encodeURIComponent(l.pn)+'/fornecedor',{method:'POST',
         body:{acao:'ignorar', justificativa:just.value}});
       fecharSobreposicoes(); toast('Registrado na auditoria.'); t.recarregar();
     }},'Ignorar sugestão')]);
}

/* ======================= FICHA 360º ======================= */
async function telaFicha(c, pn){
  const d = await api('/api/material/'+encodeURIComponent(pn));
  const m = d.material, mm = d.metricas||{};
  const acoes = el('div',{class:'acoes'},
    pode('cotacao.criar')?el('button',{class:'btn primario',onclick:()=>modalNovaCotacao(pn)},'Nova cotação'):null,
    el('button',{class:'btn',onclick:()=>location.hash='#/sap/compras?pn='+encodeURIComponent(pn)},'Exportar histórico'),
    pode('vinculo.confirmar')?el('button',{class:'btn',onclick:()=>escolherOutro({pn,descricao:m.descricao},
      {recarregar:()=>telaFicha(c,pn)})},'Adicionar fornecedor'):null);

  const topo = el('div',{class:'ficha-topo'},
    el('div',{class:'linha'},
      el('div',{},
        el('div',{class:'pnum'},'PN '+m.pn),
        el('h1',{},m.descricao||'(sem descrição)'),
        el('div',{class:'meta'},
          el('span',{},'Categoria: '+(m.categoria||'não classificado')),
          el('span',{},'Unidade: '+(m.umb||'—')),
          el('span',{},'Área: '+(m.area||'—')),
          el('span',{},'Curva: '+(mm.classe_abc||'—')+(mm.classe_xyz?' / '+mm.classe_xyz:'')),
          el('span',{},'Fornecedor: '+(m.fornecedor_cadastro||'não definido')))),
      acoes));

  const alertas = el('div',{}, ...d.alertas.map(a=>el('div',{class:'aviso'+(a.nivel==='critico'?' critico':a.nivel==='info'?' info':'')},
    el('span',{},a.nivel==='critico'?'⚠':a.nivel==='info'?'ℹ':'▲'),
    el('div',{class:'txt'}, el('b',{},a.titulo), el('div',{class:'muted'},a.motivo)))));

  const kpi=(r,v,s,cls)=>el('div',{class:'kpi'+(cls?' '+cls:'')},
    el('div',{class:'r'},r), el('div',{class:'v'},v), s?el('div',{class:'s'},s):null);
  const consumoMes = mm.consumo_12m ? mm.consumo_12m/12 : (m.consumo_med_mes||null);
  const kpis = el('div',{class:'kpis'},
    kpi('Estoque atual', int(m.estoque_atual)+' '+(m.umb||''), 'mín '+int(m.estoque_min)+' · máx '+int(m.estoque_max)),
    kpi('Consumo médio', consumoMes?num(consumoMes,1)+'/mês':'—', mm.consumo_12m?int(mm.consumo_12m)+' em 12 meses':'sem consumo registrado'),
    kpi('Cobertura', mm.cobertura_meses!=null?num(mm.cobertura_meses,1)+' meses':'—',
        mm.cobertura_meses!=null?num(mm.cobertura_meses*30,0)+' dias':null,
        mm.risco==='RUPTURA'?'crit':(mm.risco==='BAIXO'?'warn':null)),
    kpi('Último preço', dinheiro(mm.ultimo_preco), mm.ultimo_preco_data?'em '+dataBR(mm.ultimo_preco_data):null),
    kpi('Preço MM60', dinheiro(m.preco_unitario), m.preco_atualizado_em?'atualizado em '+dataBR(m.preco_atualizado_em):null),
    kpi('Diferença', mm.escala_suspeita?'indisponível':pctSinal(mm.divergencia_pct),
        mm.escala_suspeita?'escalas diferentes':'último x MM60',
        (!mm.escala_suspeita && Math.abs(mm.divergencia_pct||0)>0.3)?'warn':null),
    kpi('Último fornecedor', mm.ultimo_fornecedor_nome||m.fornecedor_cadastro||'—'),
    kpi('Lead time', d.lead_time?num(d.lead_time,0)+' dias':'—',
        mm.lead_time_obs?'observado no SAP':'cadastro'));

  const abas = ['Visão Geral','Estoque','Consumo','Preços','Compras','SAP','Fornecedores','Cotações','Auditoria'];
  const painel = el('div',{});
  const barra = el('div',{class:'abas'}, ...abas.map(a=>el('button',{onclick:e=>{
      barra.querySelectorAll('button').forEach(b=>b.classList.remove('ativa'));
      e.target.classList.add('ativa'); abrirAba(a, painel, pn, d);
    }},a)));
  barra.firstChild.classList.add('ativa');
  c.replaceChildren(crumbs({rot:'Materiais',rota:'materiais'},{rot:pn}), topo, alertas, kpis, barra, painel);
  abrirAba('Visão Geral', painel, pn, d);
}

async function abrirAba(aba, painel, pn, d){
  painel.replaceChildren(el('div',{}, ...Array.from({length:4},()=>el('div',{class:'sk'}))));
  const m=d.material, mm=d.metricas||{};
  try{
    if(aba==='Visão Geral'){
      const campos=[['PN',m.pn],['Descrição',m.descricao],['Categoria',m.categoria],['Tipo',m.tipo],
        ['Tipo de material',m.tipo_material],['Unidade',m.umb],['Área',m.area],['Origem',m.origem],
        ['Grupo de mercadorias',m.grupo_mercadorias],['Grupo de compradores',m.grupo_compradores],
        ['Tipo de reposição',m.tipo_reposicao],['Kanban',m.kanban],['Pedido em aberto',m.pedido_atual],
        ['Lead time cadastro',m.lead_time_dias?m.lead_time_dias+' dias':null],
        ['Fornecedor do cadastro',m.fornecedor_cadastro],['Origem do dado',m.origem_dados],
        ['Classificação automática', m.categoria_confianca!=null?
          `${m.categoria||'—'} (confiança ${pct(m.categoria_confianca)}, origem ${m.categoria_origem||'—'})`:null]];
      painel.replaceChildren(el('div',{class:'painel'}, el('h2',{},'Dados do material'),
        el('div',{class:'corpo'}, el('table',{class:'dados'}, el('tbody',{},
          ...campos.filter(f=>f[1]!==null&&f[1]!==undefined&&f[1]!=='').map(f=>el('tr',{},
            el('td',{class:'muted',style:'width:200px'},f[0]), el('td',{},String(f[1]))))))) ));
    }
    else if(aba==='Estoque'){
      const e = await api('/api/material/'+encodeURIComponent(pn)+'/estoque');
      const mt=e.metricas||{}, mat=e.material||{};
      const motivo = mt.risco==='RUPTURA'
        ? `Estoque atual: ${int(mat.estoque_atual)} ${mat.umb||''}. Consumo médio: ${num((mt.consumo_12m||0)/12,1)}/mês. Cobertura estimada: ${num((mt.cobertura_meses||0)*30,0)} dias.`
        : mt.risco==='SEM_MOVIMENTO' ? 'Sem consumo nos últimos 12 meses — avaliar obsolescência.'
        : mt.risco==='ELEVADO' ? `Estoque (${int(mat.estoque_atual)}) acima de 1,5× o máximo (${int(mat.estoque_max)}).`
        : 'Cobertura dentro do esperado para o lead time.';
      painel.replaceChildren(
        el('div',{class:'aviso'+(mt.risco==='RUPTURA'?' critico':mt.risco==='OK'?' info':'')},
          el('span',{},'▣'), el('div',{class:'txt'}, el('b',{},'Situação: '), seloRisco(mt.risco),
          el('div',{class:'muted'},motivo))),
        el('div',{class:'kpis'},
          kpiSimples('Estoque atual',int(mat.estoque_atual)+' '+(mat.umb||'')),
          kpiSimples('Estoque mínimo',int(mat.estoque_min)),
          kpiSimples('Estoque máximo',int(mat.estoque_max)),
          kpiSimples('Consumo médio',num((mt.consumo_12m||0)/12,1)+'/mês'),
          kpiSimples('Cobertura',mt.cobertura_meses!=null?num(mt.cobertura_meses,1)+' meses':'—'),
          kpiSimples('Ponto de reposição',mt.ponto_reposicao!=null?num(mt.ponto_reposicao,1):'—',
            'consumo médio × lead time'),
          kpiSimples('Última entrada',dataBR(mt.ultima_entrada)),
          kpiSimples('Última saída',dataBR(mt.ultima_saida))));
    }
    else if(aba==='Consumo'){
      const cs = await api('/api/material/'+encodeURIComponent(pn)+'/consumo');
      let modo='qtd';
      const box = el('div',{class:'corpo'});
      const desenha=()=>box.replaceChildren(
        grafBarras({dados:cs.meses.map(x=>({r:mesBR(x.ano_mes),v:modo==='qtd'?x.quantidade:x.valor})),
          formato:modo==='qtd'?abrevInt:abrev}),
        el('div',{class:'legenda'},el('span',{},modo==='qtd'?'Quantidade consumida por mês':'Valor consumido por mês')));
      const mt=cs.metricas||{};
      painel.replaceChildren(
        el('div',{class:'painel'},
          el('h2',{},'Consumo mensal', el('div',{class:'acoes'},
            el('button',{class:'btn pequeno',onclick:e=>{modo='qtd';desenha();}},'Quantidade'),
            el('button',{class:'btn pequeno',onclick:e=>{modo='valor';desenha();}},'Valor'))),
          box),
        el('div',{class:'kpis'},
          kpiSimples('Consumo 3M',int(mt.consumo_3m)),
          kpiSimples('Consumo 6M',int(mt.consumo_6m)),
          kpiSimples('Consumo 12M',int(mt.consumo_12m)),
          kpiSimples('Maior mês',int(Math.max(0,...cs.meses.map(x=>x.quantidade||0)))),
          kpiSimples('Meses sem consumo',int(mt.meses_sem_consumo),'nos últimos 12'),
          kpiSimples('Curva ABC',mt.classe_abc||'—','por valor de consumo'),
          kpiSimples('Classe XYZ',mt.classe_xyz||'—','regularidade do consumo')));
      desenha();
    }
    else if(aba==='Preços'){
      let periodo='12';
      const box=el('div',{});
      const carregar=async()=>{
        box.replaceChildren(el('div',{class:'sk'}));
        const p = await api(`/api/material/${encodeURIComponent(pn)}/precos?periodo=${periodo}`);
        const mt=p.metricas||{};
        const info = el('div',{class:'muted',style:'min-height:34px;font-size:12px'});
        const serie = {cor:'var(--brand)', pontos:p.pontos.map(x=>({y:x.preco, dados:x,
          dica:`Data: ${dataBR(x.data)}\nFornecedor: ${x.fornecedor||'—'}\nQuantidade: ${int(x.qtd)}\n`+
               `Preço unitário: ${dinheiro(x.preco)}\nPedido: ${x.pedido||x.requisicao||'—'}`}))};
        const series=[serie];
        if(mt.media_12m) series.push({tipo:'reta',valor:mt.media_12m,cor:'var(--ok)'});
        if(p.mm60 && !mt.escala_suspeita) series.push({tipo:'reta',valor:p.mm60,cor:'var(--warn)',tracejado:'2 3'});
        box.replaceChildren(
          el('div',{class:'painel'},
            el('h2',{},'Evolução do preço de compra',
              el('div',{class:'acoes'}, ...['3','6','12','24','all'].map(x=>
                el('button',{class:'btn pequeno'+(periodo===x?' primario':''),
                  onclick:()=>{periodo=x;carregar();}}, x==='all'?'Tudo':x+'M')))),
            el('div',{class:'corpo'},
              p.pontos.length?grafLinha({series, formato:abrev, labels:p.pontos.map(x=>dataBR(x.data).slice(0,5)),
                aoPassar:(pt)=>{ info.textContent = pt ?
                  `${dataBR(pt.dados.data)} · ${pt.dados.fornecedor||'fornecedor não identificado'} · `+
                  `${int(pt.dados.qtd)} un · ${dinheiro(pt.dados.preco)} · pedido ${pt.dados.pedido||'—'}` : ''; }})
                :el('div',{class:'vazio'},'Nenhuma compra com preço no período.'),
              info,
              el('div',{class:'legenda'},
                el('span',{},el('i',{style:'background:var(--brand)'}),'Preço pago'),
                mt.media_12m?el('span',{},el('i',{style:'background:var(--ok)'}),'Média 12M ponderada'):null,
                (p.mm60&&!mt.escala_suspeita)?el('span',{},el('i',{style:'background:var(--warn)'}),'Preço mestre MM60'):null))),
          el('div',{class:'kpis'},
            kpiSimples('Último preço',dinheiro(mt.ultimo_preco),dataBR(mt.ultimo_preco_data)),
            kpiRastro('Média 3M',dinheiro(mt.media_3m),p,'3'),
            kpiRastro('Média 6M',dinheiro(mt.media_6m),p,'6'),
            kpiRastro('Média 12M',dinheiro(mt.media_12m),p,'12'),
            kpiSimples('Menor preço',dinheiro(mt.menor_preco)),
            kpiSimples('Maior preço',dinheiro(mt.maior_preco)),
            kpiSimples('MM60',dinheiro(p.mm60),dataBR(p.mm60_data)),
            kpiSimples('Variação',mt.escala_suspeita?'indisponível':pctSinal(mt.divergencia_pct),
              mt.escala_suspeita?'escalas diferentes':'último x MM60')));
      };
      painel.replaceChildren(box); carregar();
    }
    else if(aba==='Compras'){
      const linhas = await api('/api/material/'+encodeURIComponent(pn)+'/compras');
      painel.replaceChildren(el('div',{class:'painel'},
        el('h2',{},`Compras e movimentos — ${linhas.length} registro(s)`),
        el('div',{class:'rolagem'}, el('table',{class:'dados'},
          el('thead',{},el('tr',{},...['Data','Origem','Documento','Fornecedor','Qtde','Preço unit.','Valor total','Status']
            .map((h,i)=>el('th',{class:i>3?'right':''},h)))),
          el('tbody',{},...linhas.map(l=>el('tr',{},
            el('td',{},dataBR(l.data_documento)),
            el('td',{},el('span',{class:'selo neutro'},l.fonte)),
            el('td',{class:'mono'},l.pedido||l.requisicao||'—'),
            el('td',{class:'trunc'},l.fornecedor_nome||(l.fornecedor_texto||'').trim()||'—'),
            el('td',{class:'num'},int(l.quantidade)),
            el('td',{class:'num'},dinheiro(l.preco_unitario)),
            el('td',{class:'num'},dinheiro(l.valor_total)),
            el('td',{},l.status||'—'))))))));
    }
    else if(aba==='SAP'){
      const t = await api('/api/material/'+encodeURIComponent(pn)+'/timeline');
      painel.replaceChildren(
        el('div',{class:'kpis'},
          ...t.ciclos.slice(0,3).map(cc=>kpiSimples(cc.tipo, cc.dias+' dias', cc.ref)),
          t.intervalo_medio_dias?kpiSimples('Intervalo entre compras',t.intervalo_medio_dias+' dias','média dos pedidos'):null),
        el('div',{class:'painel'}, el('h2',{},'Timeline SAP'),
          el('div',{class:'corpo'},
            el('div',{class:'tl'}, ...t.eventos.map(e=>el('div',{class:'ev'},
              el('div',{class:'d'},dataBR(e.data)),
              el('div',{class:'t'},e.tipo),
              el('div',{class:'muted'},e.detalhe + (e.valor?` · ${dinheiro(e.valor)}`:''))))),
            el('div',{class:'muted',style:'margin-top:10px;font-size:11.5px'},t.aviso))));
    }
    else if(aba==='Fornecedores'){
      const f = await api('/api/material/'+encodeURIComponent(pn)+'/fornecedores');
      painel.replaceChildren(
        el('div',{class:'painel'}, el('h2',{},'Fornecedores históricos deste PN'),
          el('div',{class:'rolagem'}, el('table',{class:'dados'},
            el('thead',{},el('tr',{},...['Fornecedor','Compras','Última compra','Último preço','Preço médio','Participação','Lead time','']
              .map((h,i)=>el('th',{class:(i>0&&i<7)?'right':''},h)))),
            el('tbody',{},...f.historicos.map(l=>el('tr',{},
              el('td',{}, el('a',{style:'cursor:pointer',onclick:()=>location.hash='#/fornecedor/'+l.id},l.nome),
                el('div',{style:'margin-top:2px'}, ...l.tags.map(t=>el('span',{class:'selo info',style:'margin-right:4px'},t)))),
              el('td',{class:'num'},int(l.compras)),
              el('td',{class:'num'},dataBR(l.ultima)),
              el('td',{class:'num'},dinheiro(l.ultimo_preco)),
              el('td',{class:'num'},dinheiro(l.preco_medio)),
              el('td',{class:'num'},num(l.participacao,1)+'%'),
              el('td',{class:'num'},l.lead_time_dias?l.lead_time_dias+'d':'—'),
              el('td',{}, pode('cotacao.criar')?el('button',{class:'btn pequeno',
                onclick:()=>modalNovaCotacao(pn)},'Cotar'):null)))))),
          el('div',{class:'rodape-tab'},f.aviso)),
        f.da_categoria.length ? el('div',{class:'painel'},
          el('h2',{},'Fornecedores da categoria '+((f.categoria&&f.categoria.nome)||'')),
          el('div',{class:'corpo'}, ...f.da_categoria.map(x=>{
            const sub = x.email + (x.id ? '' : ' · e-mail sem fornecedor cadastrado');
            return el('div',{class:'opcao'}, el('div',{},
              el('div',{class:'nm'}, x.nome || x.email), el('div',{class:'mv'}, sub)));
          })) ) : null);
    }
    else if(aba==='Cotações'){
      const cs = await api('/api/material/'+encodeURIComponent(pn)+'/cotacoes');
      painel.replaceChildren(el('div',{class:'painel'},
        el('h2',{},'Cotações deste material',
          el('div',{class:'acoes'}, pode('cotacao.criar')?el('button',{class:'btn pequeno primario',
            onclick:()=>modalNovaCotacao(pn)},'Nova cotação'):null)),
        cs.length? el('div',{class:'rolagem'}, el('table',{class:'dados'},
          el('thead',{},el('tr',{},...['Processo','Requisição','Status','Qtde','Convidados','Respostas','Criada em'].map(h=>el('th',{},h)))),
          el('tbody',{},...cs.map(x=>el('tr',{},
            el('td',{},el('a',{style:'cursor:pointer',onclick:()=>location.hash='#/cotacao/'+x.id},x.numero)),
            el('td',{},x.requisicao||'—'), el('td',{},seloStatus(x.status)),
            el('td',{},int(x.quantidade)), el('td',{},int(x.convidados)),
            el('td',{},int(x.respostas)), el('td',{},dataBR(x.criado_em)))))))
          : el('div',{class:'vazio'},'Nenhuma cotação registrada para este material.')));
    }
    else if(aba==='Auditoria'){
      const a = await api('/api/material/'+encodeURIComponent(pn)+'/auditoria');
      painel.replaceChildren(el('div',{class:'painel'}, el('h2',{},'Auditoria do material'),
        a.length? el('div',{class:'rolagem'},el('table',{class:'dados'},
          el('thead',{},el('tr',{},...['Data','Usuário','Ação','Detalhe'].map(h=>el('th',{},h)))),
          el('tbody',{},...a.map(x=>el('tr',{},
            el('td',{},dataBR(x.criado_em)+' '+String(x.criado_em||'').slice(11,16)),
            el('td',{},x.usuario_email||'—'), el('td',{},x.acao),
            el('td',{},detalheAuditoria(x.detalhe)))))))
          : el('div',{class:'vazio'},'Nenhuma alteração registrada para este material.')));
    }
  }catch(ex){ painel.replaceChildren(el('div',{class:'erro-box'},ex.message)); }
}

const kpiSimples=(r,v,s)=>el('div',{class:'kpi'},el('div',{class:'r'},r),
  el('div',{class:'v'},v),s?el('div',{class:'s'},s):null);

function kpiRastro(rot, valor, p, meses){
  const n = p.pontos.length;
  return el('div',{class:'kpi',style:'cursor:pointer',title:'Clique para ver como foi calculado',
      onclick:()=>{
        const usados = p.pontos;
        drawer('Como '+rot+' foi calculada',
          el('div',{},
            el('p',{},p.explicacao || `Média ponderada pela quantidade das compras dos últimos ${meses} meses.`),
            el('p',{class:'muted'},'Fórmula: Σ(preço × quantidade) ÷ Σ(quantidade). '+
              'Compras sem preço unitário no SAP não entram no cálculo.'),
            el('table',{class:'dados'},
              el('thead',{},el('tr',{},...['Data','Fornecedor','Qtde','Preço','Documento'].map(h=>el('th',{},h)))),
              el('tbody',{},...usados.map(x=>el('tr',{},
                el('td',{},dataBR(x.data)), el('td',{class:'trunc'},x.fornecedor||'—'),
                el('td',{class:'num'},int(x.qtd)), el('td',{class:'num'},dinheiro(x.preco)),
                el('td',{class:'mono'},x.pedido||x.requisicao||'—')))))));
      }},
    el('div',{class:'r'}, rot, ' ', el('span',{class:'dica',title:'clique para ver os registros usados'},'ⓘ')),
    el('div',{class:'v'},valor),
    el('div',{class:'s'}, valor==='—'?'sem compras no período':'ver registros utilizados'));
}

function detalheAuditoria(json){
  if(!json) return '—';
  try{
    const d = JSON.parse(json);
    return el('div',{}, ...Object.entries(d).map(([k,v])=>el('div',{},
      el('span',{class:'muted'},k.replace(/_/g,' ')+': '), String(v??'—'))));
  }catch(e){ return json; }
}

function verContexto(pn){
  drawer('Contexto de compra · '+pn, el('div',{class:'sk'}));
  api('/api/material/'+encodeURIComponent(pn)+'/contexto').then(d=>{
    const m=d.material, mm=d.metricas||{};
    const corpo = document.querySelector('.drawer .corpo');
    corpo.replaceChildren(
      el('div',{style:'margin-bottom:10px'}, el('b',{},m.pn+' — '), m.descricao||''),
      el('div',{class:'kpis'},
        kpiSimples('Último preço',dinheiro(mm.ultimo_preco),dataBR(mm.ultimo_preco_data)),
        kpiSimples('MM60',dinheiro(m.mm60)),
        kpiSimples('Média 12M',dinheiro(mm.media_12m)),
        kpiSimples('Último fornecedor',mm.ultimo_fornecedor_nome||m.fornecedor_cadastro||'—'),
        kpiSimples('Consumo médio',mm.consumo_12m?num(mm.consumo_12m/12,1)+'/mês':'—'),
        kpiSimples('Estoque',int(m.estoque_atual)+' '+(m.umb||'')),
        kpiSimples('Cobertura',mm.cobertura_meses!=null?num(mm.cobertura_meses,1)+' meses':'—'),
        kpiSimples('Lead time',(mm.lead_time_obs||m.lead_time_dias)?num(mm.lead_time_obs||m.lead_time_dias,0)+' dias':'—')),
      el('button',{class:'btn primario',style:'width:100%;margin-top:10px',
        onclick:()=>{fecharSobreposicoes();location.hash='#/material/'+encodeURIComponent(pn);}},'Abrir Ficha 360º'));
  });
}
