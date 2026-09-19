/* Portal de Cotações — núcleo: sessão, rotas, tabelas, gráficos, utilitários */
const S = { user:null, nav:{}, rota:'', params:{}, cache:{} };

/* ---------------- utilitários ---------------- */
const el = (t,a={},...f)=>{const n=document.createElement(t);
  for(const [k,v] of Object.entries(a)){
    if(v===null||v===undefined||v===false) continue;
    if(k==='class') n.className=v; else if(k==='html') n.innerHTML=v;
    else if(k.startsWith('on')) n.addEventListener(k.slice(2),v);
    else n.setAttribute(k,v);}
  f.flat().forEach(c=>c!==null&&c!==undefined&&c!==false&&n.append(c.nodeType?c:document.createTextNode(c)));
  return n;};
const $ = s=>document.querySelector(s);
/* nós nulos são ignorados (permite blocos condicionais na montagem das telas) */
const _rc = Element.prototype.replaceChildren;
Element.prototype.replaceChildren = function(...n){
  return _rc.apply(this, n.filter(x=>x!==null&&x!==undefined&&x!==false));
};
const esc = s=>String(s??'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
const num = (v,d=2)=> (v===null||v===undefined||v==='')?'—':
  Number(v).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const int = v=> (v===null||v===undefined)?'—':Number(v).toLocaleString('pt-BR');
const dinheiro = v=> (v===null||v===undefined)?'—':'R$ '+num(v,2);
const abrev = v=>{ if(v===null||v===undefined) return '—'; const a=Math.abs(v);
  if(a>=1e9) return 'R$ '+(v/1e9).toLocaleString('pt-BR',{maximumFractionDigits:1})+' bi';
  if(a>=1e6) return 'R$ '+(v/1e6).toLocaleString('pt-BR',{maximumFractionDigits:1})+' mi';
  if(a>=1e3) return 'R$ '+(v/1e3).toLocaleString('pt-BR',{maximumFractionDigits:0})+' mil';
  return 'R$ '+num(v,0); };
const abrevInt = v=>{ if(v===null||v===undefined) return '—'; const a=Math.abs(v);
  if(a>=1e6) return (v/1e6).toLocaleString('pt-BR',{maximumFractionDigits:1})+' mi';
  if(a>=1e3) return (v/1e3).toLocaleString('pt-BR',{maximumFractionDigits:0})+' mil';
  return int(v); };
const pct = v=> (v===null||v===undefined)?'—':(v*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const pctSinal = v=> (v===null||v===undefined)?'—':(v>0?'+':'')+pct(v);
const dataBR = d=>{ if(!d) return '—'; const p=String(d).slice(0,10).split('-');
  return p.length===3?`${p[2]}/${p[1]}/${p[0]}`:d; };
const mesBR = am=>{ if(!am) return '—'; const [a,m]=am.split('-');
  return ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'][+m-1]+'/'+a.slice(2); };

function toast(msg){ const t=el('div',{class:'toast'},msg); document.body.append(t);
  setTimeout(()=>t.remove(),3200); }

async function api(rota, opts={}){
  const o = {headers:{'Content-Type':'application/json'}, credentials:'same-origin', ...opts};
  if(o.body && typeof o.body!=='string') o.body = JSON.stringify(o.body);
  if(o.method && o.method!=='GET') o.headers['X-CSRF'] = S.user?.csrf || '';
  const r = await fetch(rota, o);
  if(r.status===401){ S.user=null; desenharLogin('Sua sessão expirou. Entre novamente.'); throw new Error('401'); }
  if(r.status===428){ desenharTrocaSenha('Defina uma nova senha para continuar.'); throw new Error('428'); }
  const j = await r.json().catch(()=>({erro:'Resposta inválida do servidor.'}));
  if(!r.ok) throw new Error(j.erro || `Erro ${r.status}`);
  return j;
}
const qs = o => Object.entries(o).filter(([,v])=>v!==''&&v!==null&&v!==undefined)
  .map(([k,v])=>`${k}=${encodeURIComponent(v)}`).join('&');
const pode = p => S.user && (S.user.permissoes.includes('*') || S.user.permissoes.includes(p));

/* ---------------- login ---------------- */
function desenharLogin(msg){
  document.body.innerHTML='';
  const erro = el('div',{class:'erro'}, msg||'');
  const email = el('input',{type:'email',autocomplete:'username',required:'required'});
  const senha = el('input',{type:'password',autocomplete:'current-password',required:'required'});
  const form = el('form',{onsubmit:async e=>{
      e.preventDefault(); erro.textContent='Entrando…';
      try{
        S.user = await api('/api/login',{method:'POST',body:{email:email.value,senha:senha.value}});
        if(S.user.trocar_senha) desenharTrocaSenha('Primeiro acesso: defina a sua senha.');
        else iniciar();
      }catch(ex){ erro.textContent = ex.message; }
    }},
    el('h1',{},'Portal de Gestão de Cotações'),
    el('p',{}, S.org ? `${S.org.org_nome} · ${S.org.org_subtitulo}` : 'Compras e Almoxarifado'),
    el('label',{},'E-mail corporativo'), email,
    el('label',{},'Senha'), senha,
    el('button',{type:'submit'},'Entrar'), erro,
    el('div',{class:'dicas'},'Acesso com a conta corporativa. Esqueceu a senha? Fale com o administrador do portal.'));
  document.body.append(el('div',{class:'login'}, form));
  email.focus();
}

/* ---------------- troca de senha ---------------- */
/* Contas criadas pelo administrador (e as resetadas) nascem com troca
   obrigatória: a API devolve 428 em tudo até a senha ser definida. */
function desenharTrocaSenha(msg){
  document.body.innerHTML='';
  const erro  = el('div',{class:'erro'}, msg||'');
  const atual = el('input',{type:'password',autocomplete:'current-password',required:'required'});
  const nova  = el('input',{type:'password',autocomplete:'new-password',required:'required',minlength:'10'});
  const conf  = el('input',{type:'password',autocomplete:'new-password',required:'required',minlength:'10'});
  const form = el('form',{onsubmit:async e=>{
      e.preventDefault();
      if(nova.value !== conf.value){ erro.textContent='A confirmação não confere com a nova senha.'; return; }
      erro.textContent='Salvando…';
      try{
        const r = await fetch('/api/senha',{method:'POST',credentials:'same-origin',
          headers:{'Content-Type':'application/json','X-CSRF':S.user?.csrf||''},
          body:JSON.stringify({senha_atual:atual.value, senha_nova:nova.value})});
        const j = await r.json().catch(()=>({erro:'Resposta inválida do servidor.'}));
        if(!r.ok){ erro.textContent = j.erro || ('Erro '+r.status); return; }
        S.user = null;
        desenharLogin('Senha alterada. Entre com a nova senha.');
      }catch(ex){ erro.textContent = ex.message; }
    }},
    el('h1',{},'Definir nova senha'),
    el('p',{},'Sua conta exige uma senha nova antes do primeiro uso.'),
    el('label',{},'Senha atual'), atual,
    el('label',{},'Nova senha'), nova,
    el('label',{},'Confirme a nova senha'), conf,
    el('button',{type:'submit'},'Salvar e entrar'), erro,
    el('div',{class:'dicas'},'Mínimo de 10 caracteres. Evite palavras óbvias e o seu próprio usuário.'));
  document.body.append(el('div',{class:'login'}, form));
  atual.focus();
}

/* ---------------- menu ---------------- */
const MENU = [
  {grupo:null, itens:[{rota:'dashboard', ic:'▦', rot:'Dashboard'}]},
  {grupo:'Cotações', perm:'cotacao.ver', itens:[
    {rota:'cotacoes/nova', ic:'＋', rot:'Nova cotação', perm:'cotacao.criar'},
    {rota:'cotacoes/andamento', ic:'◎', rot:'Em andamento', badge:'cotacoes_abertas'},
    {rota:'cotacoes/aguardando', ic:'⧗', rot:'Aguardando fornecedor', badge:'cotacoes_aguardando'},
    {rota:'cotacoes/finalizadas', ic:'✓', rot:'Finalizadas'}]},
  {grupo:'Materiais', perm:'material.ver', itens:[
    {rota:'materiais', ic:'▤', rot:'Consultar materiais'},
    {rota:'materiais/sem-fornecedor', ic:'⚠', rot:'Sem fornecedor', badge:'sem_fornecedor', alerta:true},
    {rota:'categorias', ic:'⊞', rot:'Categorias'}]},
  {grupo:'Estoque', perm:'estoque.ver', itens:[
    {rota:'estoque/geral', ic:'▥', rot:'Visão geral'},
    {rota:'estoque/cobertura', ic:'◔', rot:'Cobertura'},
    {rota:'estoque/consumo', ic:'∿', rot:'Consumo', perm:'consumo.ver'},
    {rota:'estoque/parado', ic:'⊘', rot:'Sem movimentação', badge:'sem_movimento'},
    {rota:'estoque/ruptura', ic:'⚠', rot:'Risco de ruptura', badge:'ruptura', alerta:true}]},
  {grupo:'Preços', perm:'preco.ver', itens:[
    {rota:'precos/geral', ic:'₴', rot:'Visão geral'},
    {rota:'precos/divergencias', ic:'≠', rot:'Divergências', badge:'divergencias', alerta:true},
    {rota:'precos/oportunidades', ic:'↓', rot:'Oportunidades', badge:'oportunidades'},
    {rota:'precos/escala', ic:'⚖', rot:'Escala inconsistente'}]},
  {grupo:'Histórico SAP', perm:'sap.ver', itens:[
    {rota:'sap/compras', ic:'▸', rot:'Compras'},
    {rota:'sap/requisicoes', ic:'▸', rot:'Requisições'},
    {rota:'sap/movimentacoes', ic:'▸', rot:'Movimentações'}]},
  {grupo:'Fornecedores', perm:'fornecedor.ver', itens:[
    {rota:'fornecedores', ic:'⌂', rot:'Cadastro'},
    {rota:'fornecedores/sem-email', ic:'✉', rot:'Pendências de vínculo'}]},
  {grupo:null, itens:[
    {rota:'pendencias', ic:'!', rot:'Pendências', badge:'pendencias_criticas', alerta:true, perm:'pendencia.ver'},
    {rota:'relatorios', ic:'▧', rot:'Relatórios', perm:'relatorio.ver'}]},
  {grupo:'Administração', perm:'auditoria.ver', itens:[
    {rota:'admin/usuarios', ic:'☰', rot:'Usuários', perm:'*'},
    {rota:'admin/auditoria', ic:'⟲', rot:'Auditoria', perm:'auditoria.ver'}]},
];

function desenharMenu(){
  const nav = el('nav');
  MENU.forEach(g=>{
    const itens = g.itens.filter(i=>!i.perm || pode(i.perm));
    if(!itens.length || (g.perm && !pode(g.perm))) return;
    if(g.grupo) nav.append(el('div',{class:'grupo'},g.grupo));
    itens.forEach(i=>{
      const n = S.nav[i.badge];
      nav.append(el('a',{class:'item'+(S.rota===i.rota?' ativo':''), 'data-rota':i.rota,
          title:i.rot, onclick:()=>location.hash='#/'+i.rota},
        el('span',{class:'ic'},i.ic), el('span',{class:'rot'},i.rot),
        n ? el('span',{class:'bd'+(i.alerta?' alerta':'')}, int(n)) : null));
    });
  });
  $('#menu').replaceChildren(nav);
}

/* ---------------- busca universal ---------------- */
function montarBusca(){
  const inp = el('input',{placeholder:'Pesquisar PN, descrição, fornecedor, RDA, pedido ou documento SAP…',
                          autocomplete:'off'});
  const res = el('div',{class:'res hide'});
  let t=null;
  inp.addEventListener('input',()=>{ clearTimeout(t); t=setTimeout(async()=>{
    if(inp.value.trim().length<2){ res.classList.add('hide'); return; }
    const d = await api('/api/busca?q='+encodeURIComponent(inp.value.trim()));
    res.replaceChildren();
    if(!d.grupos.length){ res.append(el('div',{class:'it muted'},'Nada encontrado.')); }
    d.grupos.forEach(g=>{
      res.append(el('div',{class:'gr'},g.titulo));
      g.itens.forEach(i=>res.append(el('div',{class:'it', onclick:()=>{
          res.classList.add('hide'); inp.value='';
          if(g.tipo==='material') location.hash='#/material/'+i.id;
          else if(g.tipo==='fornecedor') location.hash='#/fornecedor/'+i.id;
          else if(g.tipo==='cotacao') location.hash='#/cotacao/'+i.id;
          else if(g.tipo==='sap') location.hash='#/sap/compras?q='+encodeURIComponent(i.id);
          else location.hash='#/materiais?categoria='+encodeURIComponent(i.titulo);
        }}, el('div',{},i.titulo), el('span',{},i.sub))));
    });
    res.classList.remove('hide');
  },220); });
  document.addEventListener('click',e=>{ if(!e.target.closest('.busca')) res.classList.add('hide'); });
  return el('div',{class:'busca'}, el('span',{class:'lupa'},'⌕'), inp, res);
}

/* ---------------- shell ---------------- */
function montarShell(){
  document.body.innerHTML='';
  const shell = el('div',{class:'shell',id:'shell'},
    el('aside',{},
      el('div',{class:'marca'}, el('span',{},'◧'),
        el('div',{}, el('span',{class:'rot'}, (S.org && S.org.org_nome) || 'Cotações'),
                     el('small',{class:'rot'},'Compras · Almoxarifado'))),
      el('div',{id:'menu'}),
      el('div',{class:'rodape muted'}, el('span',{},'Fase 1 · dados SAP consolidados'))),
    el('main',{},
      el('header',{class:'top'},
        el('button',{class:'toggle',title:'Recolher menu',
          onclick:()=>$('#shell').classList.toggle('recolhido')},'☰'),
        montarBusca(),
        el('div',{class:'perfil'},
          el('div',{class:'av'}, (S.user.nome||'?').slice(0,1).toUpperCase()),
          el('div',{}, el('div',{},S.user.nome),
            el('div',{class:'muted',style:'font-size:11px'},
              S.user.perfil.charAt(0)+S.user.perfil.slice(1).toLowerCase())),
          el('button',{onclick:async()=>{await api('/api/logout',{method:'POST'});desenharLogin();}},'Sair'))),
      el('div',{class:'conteudo',id:'conteudo'})));
  document.body.append(shell);
}

/* ---------------- tabela reutilizável ---------------- */
/* cfg: {rota, colunas:[{k,rot,tipo,largura,ord,fmt}], filtros:[], ordemPadrao, onLinha, tela,
        acoes:[], semExport} */
function Tabela(cfg){
  const est = {pagina:1, por_pagina:50, ordem:cfg.ordemPadrao||'', dir:'asc',
               filtros:{...(cfg.filtrosIniciais||{})}, colunasOcultas:new Set()};
  const corpo = el('div',{class:'rolagem'});
  const rodape = el('div',{class:'rodape-tab'});
  const topo = el('div',{class:'tabela-topo'});

  const buscaInp = el('input',{class:'cresce',placeholder:cfg.placeholder||'Buscar…',
    value:est.filtros.q||'', oninput:e=>{est.filtros.q=e.target.value; debounce();}});
  let t=null; const debounce=()=>{clearTimeout(t);t=setTimeout(()=>{est.pagina=1;carregar();},300);};
  topo.append(buscaInp);
  (cfg.filtros||[]).forEach(f=>{
    if(f.tipo==='select'){
      const s = el('select',{onchange:e=>{est.filtros[f.k]=e.target.value;est.pagina=1;carregar();}},
        ...[{v:'',r:f.rot}].concat(f.opcoes).map(o=>el('option',{value:o.v ?? o},o.r ?? o)));
      if(est.filtros[f.k]) s.value=est.filtros[f.k];
      topo.append(s);
    } else if(f.tipo==='check'){
      const id='f'+Math.random().toString(36).slice(2);
      topo.append(el('label',{class:'muted',style:'display:flex;gap:5px;align-items:center'},
        el('input',{type:'checkbox',id,checked:est.filtros[f.k]==='1'||null,
          onchange:e=>{est.filtros[f.k]=e.target.checked?'1':'';est.pagina=1;carregar();}}), f.rot));
    } else {
      topo.append(el('input',{placeholder:f.rot,type:f.tipo||'text',style:'width:130px',
        value:est.filtros[f.k]||'',
        oninput:e=>{est.filtros[f.k]=e.target.value;debounce();}}));
    }
  });
  topo.append(el('button',{class:'btn pequeno',onclick:()=>{
      est.filtros={}; buscaInp.value=''; topo.querySelectorAll('input,select').forEach(i=>{
        if(i.type==='checkbox') i.checked=false; else i.value='';});
      est.pagina=1; carregar();}},'Limpar filtros'));
  topo.append(el('button',{class:'btn pequeno',title:'Escolher colunas visíveis',
    onclick:e=>menuColunas(e.target)},'Colunas'));
  if(!cfg.semExport)
    topo.append(el('button',{class:'btn pequeno',onclick:()=>{
      location.href=(cfg.rotaExport||cfg.rota.replace('/api/','/api/')+'/export')+'?'+qs(est.filtros);
    }},'Exportar Excel'));
  if(cfg.tela){
    topo.append(el('button',{class:'btn pequeno',title:'Salvar estes filtros como uma visão minha',
      onclick:async()=>{ const nome=prompt('Nome da visão (ex.: divergências >30% — Rolamentos)');
        if(!nome) return;
        await api('/api/filtros/'+cfg.tela,{method:'POST',body:{nome,filtros:est.filtros}});
        toast('Visão salva.'); carregarVisoes(); }},'Salvar visão'));
    var selVisoes = el('select',{onchange:e=>{ if(!e.target.value) return;
      est.filtros = JSON.parse(e.target.value); est.pagina=1;
      buscaInp.value = est.filtros.q||''; carregar(); }},
      el('option',{value:''},'Minhas visões'));
    topo.append(selVisoes);
  }
  (cfg.acoes||[]).forEach(a=>topo.append(el('button',{class:'btn pequeno',onclick:a.onclick},a.rot)));

  async function carregarVisoes(){
    if(!cfg.tela) return;
    const v = await api('/api/filtros/'+cfg.tela);
    selVisoes.replaceChildren(el('option',{value:''},'Minhas visões'),
      ...v.map(x=>el('option',{value:x.filtros},x.nome)));
  }

  function menuColunas(alvo){
    const cx = el('div',{class:'painel',style:'position:absolute;z-index:70;padding:8px;max-height:300px;overflow:auto'});
    cfg.colunas.forEach(c=>cx.append(el('label',{style:'display:block;font-size:12px;padding:2px'},
      el('input',{type:'checkbox',checked:!est.colunasOcultas.has(c.k)||null,
        onchange:e=>{e.target.checked?est.colunasOcultas.delete(c.k):est.colunasOcultas.add(c.k);pintar(ultimo);}}),
      ' '+c.rot)));
    const r = alvo.getBoundingClientRect();
    cx.style.left = r.left+'px'; cx.style.top = (r.bottom+4)+'px';
    document.body.append(cx);
    setTimeout(()=>document.addEventListener('click',function f(e){
      if(!cx.contains(e.target)){cx.remove();document.removeEventListener('click',f);}},{once:false}),50);
  }

  let ultimo = null;
  function pintar(d){
    ultimo = d;
    const cols = cfg.colunas.filter(c=>!est.colunasOcultas.has(c.k));
    if(!d.linhas.length){
      corpo.replaceChildren(el('div',{class:'vazio'},
        el('div',{style:'font-size:22px'},'∅'),
        el('div',{},'Nenhum registro com os filtros atuais.'),
        el('div',{class:'muted',style:'font-size:12px;margin-top:4px'},'Ajuste ou limpe os filtros.')));
    } else {
      const thead = el('thead',{}, el('tr',{}, ...cols.map(c=>{
        const ordenavel = c.ord!==false;
        return el('th',{class:(ordenavel?'':'na')+(c.tipo==='num'?' right':''),
          style:c.largura?`width:${c.largura}`:null,
          onclick:ordenavel?()=>{ if(est.ordem===c.k) est.dir=est.dir==='asc'?'desc':'asc';
            else {est.ordem=c.k;est.dir='asc';} carregar(); }:null},
          c.rot, ordenavel&&est.ordem===c.k?el('span',{class:'ord'},est.dir==='asc'?'▲':'▼'):null);
      })));
      const tbody = el('tbody',{}, ...d.linhas.map(l=>el('tr',{},
        ...cols.map(c=>{
          const v = c.fmt ? c.fmt(l) : l[c.k];
          const td = el('td',{class:c.tipo==='num'?'num':(c.tipo==='trunc'?'trunc':null),
                             title:c.tipo==='trunc'?(l[c.k]||''):null});
          if(v&&v.nodeType) td.append(v); else td.textContent = (v===null||v===undefined||v==='')?'—':v;
          return td;}))));
      corpo.replaceChildren(el('table',{class:'dados'},thead,tbody));
    }
    const paginas = Math.max(1,Math.ceil(d.total/d.por_pagina));
    rodape.replaceChildren(
      el('span',{},`${int(d.total)} registro(s)`),
      el('div',{class:'pag'},
        el('button',{class:'btn pequeno',disabled:d.pagina<=1||null,
          onclick:()=>{est.pagina--;carregar();}},'‹ Anterior'),
        el('span',{},`Página ${d.pagina} de ${int(paginas)}`),
        el('button',{class:'btn pequeno',disabled:d.pagina>=paginas||null,
          onclick:()=>{est.pagina++;carregar();}},'Próxima ›'),
        el('select',{onchange:e=>{est.por_pagina=+e.target.value;est.pagina=1;carregar();}},
          ...[25,50,100,200].map(n=>el('option',{value:n,selected:n===est.por_pagina||null},n+'/pág')))));
  }

  async function carregar(){
    corpo.replaceChildren(el('div',{style:'padding:12px'},
      ...Array.from({length:8},()=>el('div',{class:'sk',style:'width:'+(60+Math.random()*40)+'%'}))));
    try{
      const d = await api(cfg.rota+'?'+qs({...est.filtros, ordem:est.ordem, dir:est.dir,
        pagina:est.pagina, por_pagina:est.por_pagina}));
      pintar(d);
      if(cfg.aoCarregar) cfg.aoCarregar(d);
    }catch(ex){
      corpo.replaceChildren(el('div',{class:'erro-box'},'Não foi possível carregar: '+ex.message,
        el('div',{},el('button',{class:'btn pequeno',style:'margin-top:8px',onclick:carregar},'Tentar de novo'))));
    }
  }
  carregar(); carregarVisoes();
  return {node: el('div',{class:'painel'}, topo, corpo, rodape), recarregar:carregar, estado:est};
}

/* ---------------- gráficos SVG ---------------- */
const SVGNS='http://www.w3.org/2000/svg';
const sv=(t,a={})=>{const n=document.createElementNS(SVGNS,t);
  for(const [k,v] of Object.entries(a)) if(v!==null&&v!==undefined) n.setAttribute(k,v); return n;};

function grafLinha({series, labels, altura=210, formato=dinheiro, aoPassar}){
  const W=760,H=altura,P={t:14,r:14,b:26,l:74};
  const todos = series.flatMap(s=>s.tipo==='reta'?[s.valor]:(s.pontos||[]).map(p=>p.y))
    .filter(v=>v!==null&&v!==undefined&&!isNaN(v));
  if(!todos.length) return el('div',{class:'vazio'},'Sem dados no período selecionado.');
  let min=Math.min(...todos), max=Math.max(...todos);
  if(min===max){min=min*0.9;max=max*1.1||1;}
  const n = Math.max(...series.map(s=>(s.pontos||[]).length), 1);
  const x=i=>P.l+(n<=1?0:(W-P.l-P.r)*i/(n-1));
  const y=v=>H-P.b-(H-P.t-P.b)*((v-min)/(max-min||1));
  const g=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',height:altura,role:'img'});
  // faixa estreita: rótulos arredondados esconderiam a variação
  const amplitude = max-min;
  const fmt = formato===int || formato===abrevInt ? formato
    : amplitude < 1  ? (v=>'R$ '+num(v,4))
    : amplitude < 50 ? (v=>'R$ '+num(v,2)) : formato;
  for(let i=0;i<=4;i++){ const v=min+(max-min)*i/4, yy=y(v);
    g.append(sv('line',{x1:P.l,x2:W-P.r,y1:yy,y2:yy,class:'gx'}));
    const t=sv('text',{x:P.l-6,y:yy+3,'text-anchor':'end'}); t.textContent=fmt(v); g.append(t);}
  (labels||[]).forEach((lb,i)=>{ if(n>8 && i%Math.ceil(n/8)) return;
    const t=sv('text',{x:x(i),y:H-8,'text-anchor':'middle'}); t.textContent=lb; g.append(t);});
  series.forEach(s=>{
    if(s.tipo==='reta'){
      g.append(sv('line',{x1:P.l,x2:W-P.r,y1:y(s.valor),y2:y(s.valor),stroke:s.cor,
        'stroke-width':1.5,'stroke-dasharray':s.tracejado||'5 4'}));
      return;
    }
    const pts=(s.pontos||[]).filter(p=>p.y!==null&&p.y!==undefined);
    const d = pts.map((p,i)=>`${i?'L':'M'}${x(s.pontos.indexOf(p))},${y(p.y)}`).join(' ');
    g.append(sv('path',{d,fill:'none',stroke:s.cor,'stroke-width':2,'stroke-linejoin':'round'}));
    pts.forEach(p=>{ const i=s.pontos.indexOf(p);
      const c=sv('circle',{cx:x(i),cy:y(p.y),r:3.5,fill:s.cor,style:'cursor:pointer'});
      c.addEventListener('mouseenter',ev=>aoPassar&&aoPassar(p,ev));
      c.addEventListener('mouseleave',()=>aoPassar&&aoPassar(null));
      const tt=sv('title'); tt.textContent=p.dica||''; c.append(tt); g.append(c); });
  });
  return g;
}

function grafBarras({dados, altura=200, formato=int, cor='var(--brand)'}){
  if(!dados.length) return el('div',{class:'vazio'},'Sem dados.');
  const W=760,H=altura,P={t:12,r:10,b:26,l:56};
  const max=Math.max(...dados.map(d=>d.v||0))||1;
  const bw=(W-P.l-P.r)/dados.length;
  const g=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',height:altura});
  for(let i=0;i<=3;i++){ const v=max*i/3, yy=H-P.b-(H-P.t-P.b)*(i/3);
    g.append(sv('line',{x1:P.l,x2:W-P.r,y1:yy,y2:yy,class:'gx'}));
    const t=sv('text',{x:P.l-6,y:yy+3,'text-anchor':'end'}); t.textContent=formato(v); g.append(t);}
  dados.forEach((d,i)=>{
    const h=(H-P.t-P.b)*((d.v||0)/max);
    const r=sv('rect',{x:P.l+i*bw+bw*0.15,y:H-P.b-h,width:bw*0.7,height:Math.max(h,1),
      fill:d.cor||cor,rx:2});
    const tt=sv('title'); tt.textContent=`${d.r}: ${formato(d.v)}`; r.append(tt); g.append(r);
    if(dados.length<=14){ const t=sv('text',{x:P.l+i*bw+bw/2,y:H-8,'text-anchor':'middle'});
      t.textContent=d.r; g.append(t);} });
  return g;
}

function barrasH({dados, formato=dinheiro}){
  if(!dados.length) return el('div',{class:'vazio'},'Sem dados.');
  const max=Math.max(...dados.map(d=>d.v||0))||1;
  return el('div',{}, ...dados.map(d=>el('div',{style:'margin-bottom:7px'},
    el('div',{style:'display:flex;justify-content:space-between;font-size:12px;gap:10px'},
      el('span',{class:'trunc',style:'max-width:70%',title:d.r},d.r),
      el('span',{class:'muted'},formato(d.v))),
    el('div',{style:'height:6px;background:var(--line-2);border-radius:3px;margin-top:2px'},
      el('div',{style:`height:6px;width:${Math.max(2,(d.v/max)*100)}%;background:var(--brand);border-radius:3px`})))));
}

/* ---------------- selos e indicadores ---------------- */
function seloRisco(r){
  const m={RUPTURA:['crit','⚠','Risco de ruptura'],BAIXO:['warn','▲','Estoque baixo'],
    OK:['ok','✓','Normal'],ELEVADO:['warn','▲','Estoque elevado'],
    SEM_MOVIMENTO:['neutro','⊘','Sem movimentação']};
  const x=m[r]; if(!x) return el('span',{class:'muted'},'—');
  return el('span',{class:'selo '+x[0]}, x[1]+' '+x[2]);
}
function seloDivergencia(v, escala){
  if(escala) return el('span',{class:'selo info',title:'Preço mestre e preço pago em escalas diferentes'},'⚖ escala');
  if(v===null||v===undefined) return el('span',{class:'muted'},'—');
  const cls = Math.abs(v)>0.3?'warn':'neutro';
  return el('span',{class:'selo '+cls, title:'(último preço − MM60) ÷ MM60'},
    (Math.abs(v)>0.3?'⚠ ':'')+pctSinal(v));
}
function seloStatus(s){
  const m={RASCUNHO:'neutro',EM_APROVACAO:'info',ENVIADO:'info',AGUARDANDO:'warn',
    RESPONDIDO:'ok',EM_NEGOCIACAO:'warn',FINALIZADO:'ok',CANCELADO:'neutro',
    ABERTA:'warn',EM_ANALISE:'info',RESOLVIDA:'ok',IGNORADA:'neutro',
    CRITICA:'crit',ALTA:'crit',MEDIA:'warn',BAIXA:'neutro'};
  return el('span',{class:'selo '+(m[s]||'neutro')}, String(s||'—').replace(/_/g,' ').toLowerCase());
}

/* ---------------- drawer / modal ---------------- */
function drawer(titulo, conteudo){
  fecharSobreposicoes();
  const fundo = el('div',{class:'fundo',onclick:fecharSobreposicoes});
  const d = el('div',{class:'drawer'},
    el('h3',{}, titulo, el('button',{class:'fechar',onclick:fecharSobreposicoes},'✕')),
    el('div',{class:'corpo'}, conteudo));
  document.body.append(fundo,d); return d;
}
function modal(titulo, conteudo, botoes){
  fecharSobreposicoes();
  const fundo = el('div',{class:'fundo',onclick:fecharSobreposicoes});
  const m = el('div',{class:'modal'},
    el('h3',{},titulo),
    el('div',{class:'corpo'},conteudo),
    el('div',{class:'pe'}, ...botoes));
  document.body.append(fundo,m); return m;
}
function fecharSobreposicoes(){ document.querySelectorAll('.fundo,.drawer,.modal').forEach(n=>n.remove()); }
document.addEventListener('keydown',e=>{ if(e.key==='Escape') fecharSobreposicoes(); });

function confirmar(titulo, texto, aoConfirmar, rotulo='Confirmar'){
  modal(titulo, el('div',{},texto), [
    el('button',{class:'btn',onclick:fecharSobreposicoes},'Cancelar'),
    el('button',{class:'btn primario',onclick:()=>{fecharSobreposicoes();aoConfirmar();}},rotulo)]);
}

/* ---------------- roteamento ---------------- */
async function iniciar(){
  montarShell();
  S.nav = await api('/api/nav');
  desenharMenu();
  window.addEventListener('hashchange', rotear);
  rotear();
}
function crumbs(...partes){
  return el('div',{class:'crumbs'}, ...partes.flatMap((p,i)=>[
    i?el('span',{},' / '):null,
    p.rota?el('a',{onclick:()=>location.hash='#/'+p.rota, style:'cursor:pointer'},p.rot):el('span',{},p.rot||p)]));
}
function cabecalho(titulo, sub, ...acoes){
  return el('div',{style:'display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:12px'},
    el('div',{}, el('h1',{class:'tela'},titulo), sub?el('div',{class:'sub'},sub):null),
    el('div',{style:'margin-left:auto;display:flex;gap:7px'}, ...acoes));
}
async function rotear(){
  const h = location.hash.replace(/^#\/?/,'') || 'dashboard';
  const [caminho, query] = h.split('?');
  S.rota = caminho; S.params = Object.fromEntries(new URLSearchParams(query||''));
  desenharMenu();
  const c = $('#conteudo'); if(!c) return;
  c.replaceChildren(el('div',{}, ...Array.from({length:5},()=>el('div',{class:'sk'}))));
  try{ await renderizar(caminho, c); }
  catch(ex){ c.replaceChildren(el('div',{class:'erro-box'},'Erro ao abrir a tela: '+ex.message)); }
  c.scrollTop=0;
  api('/api/nav').then(n=>{S.nav=n;desenharMenu();});
}

/* início */
window.addEventListener('DOMContentLoaded', async()=>{
  /* identidade da instalação (nome da empresa) — pública, não exige sessão */
  try{ S.org = await (await fetch('/api/config')).json(); }catch(e){ S.org = null; }
  try{
    S.user = await api('/api/me');
    if(S.user.trocar_senha) desenharTrocaSenha('Defina uma nova senha para continuar.');
    else iniciar();
  }catch(e){ if(e.message!=='428') desenharLogin(); }
});
