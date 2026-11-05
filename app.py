import pandas as pd
import numpy as np
import streamlit as st
import re
from datetime import datetime

# =====================================================================
# CONFIGURAÇÃO DE PÁGINA E ESTILOS COMPATÍVEIS COM GP7
# =====================================================================
st.set_page_config(
    page_title="Resumo de Sell Out - GP7",
    page_icon="📊",
    layout="wide"
)

# Estilização CSS inspirada no HTML original
st.markdown("""
<style>
    .main { background-color: #eef0f3; }
    .stTable { font-size: 12px; }
    .gp7-title {
        background-color: #0e1f35;
        color: white;
        text-align: center;
        padding: 12px;
        font-size: 22px;
        font-weight: bold;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    .metric-card {
        background-color: white;
        padding: 10px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .badge-ok {
        background-color: #d9f2e0;
        color: #136b2c;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-err {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# CONFIGURAÇÕES E REGRAS DE NEGÓCIO
# =====================================================================
CONFIG = {
    'revenda': 'GP7 - JEQUIÉ',
    'codigo': '1027247',
    'unidades': [
        {'cod': '1027247', 'nome': 'GP7 - JEQUIÉ', 'gvs': [{'nome': 'GV 1', 'de': 101, 'ate': 109}, {'nome': 'GV 2', 'de': 201, 'ate': 208}]},
        {'cod': '1043293', 'nome': 'GP7 - ITAPETINGA', 'gvs': [{'nome': 'GV 1', 'de': 101, 'ate': 110}]}
    ],
    'github_base_url': 'https://raw.githubusercontent.com/hugoaprjequie-ops/Fechamento-Comercial/main/',
    'arquivoCora': 'Pedidos_1027247.csv',
    'arquivoBoni': '03.02.37_1027247.csv',
    'arquivoBase': 'Base.csv',
    'campoHecto': 'VOLUME HECTOLITRO',
    'campoValor': 'VALOR TOTAL',
    'campoValorFalta': 'VALOR LIQUIDO ITEM'
}

CATS = ['CERVEJA', 'REFRIGENANC', 'MKTPLACE', 'AGUA']

# =====================================================================
# FUNÇÕES DE HIGIENIZAÇÃO E TRATAMENTO
# =====================================================================
def norm(val):
    if pd.isna(val) or val is None:
        return ''
    s = str(val).strip().upper()
    return re.sub(r'[\u0300-\u036f]', '', s)

def chave(val):
    if pd.isna(val) or val is None:
        return ''
    s = str(val).strip()
    return str(int(s)) if s.isdigit() else norm(s)

def parse_num(val):
    if pd.isna(val) or val is None or val == '':
        return 0.0
    s = str(val).strip().replace('R$', '').replace(' ', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

def parse_iso(val):
    s = str(val).strip() if pd.notna(val) else ''
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})', s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    return m.group(0) if m else ''

# =====================================================================
# LEITURA DE DADOS DO GITHUB / UPLOAD
# =====================================================================
@st.cache_data(ttl=600)
def carregar_csv_url(url):
    try:
        df = pd.read_csv(url, sep=None, engine='python', encoding='utf-8')
        df.columns = [norm(c) for c in df.columns]
        return df
    except:
        try:
            df = pd.read_csv(url, sep=None, engine='python', encoding='latin1')
            df.columns = [norm(c) for c in df.columns]
            return df
        except:
            return None

def processar_base(df_base):
    if df_base is None or df_base.empty:
        return None
    
    prod_map = {}
    cesta_map = {}
    emb_map = {}
    he_set = set()

    for _, row in df_base.iterrows():
        g = lambda i: str(row.iloc[i]).strip() if len(row) > i and pd.notna(row.iloc[i]) else ''
        
        if g(0):
            k = chave(g(0))
            if k not in prod_map:
                prod_map[k] = {'marca': g(2), 'emb': g(3)}
        if g(9) and g(10):
            k = chave(g(9))
            if k not in cesta_map:
                cesta_map[k] = norm(g(10))
        if g(6) and g(7):
            k = chave(g(6))
            if k not in emb_map:
                emb_map[k] = norm(g(7))
        if g(12):
            he_set.add(chave(g(12)))

    return {'prod': prod_map, 'cesta': cesta_map, 'embTipo': emb_map, 'he': he_set}

def derivar_colunas(df, base_dict):
    if df is None or base_dict is None:
        return df
    
    tipo_marca, cesta_emb, cesta_he = [], [], []
    col_prod = 'COD. PRODUTO' if 'COD. PRODUTO' in df.columns else 'PRODUTO'
    
    for _, r in df.iterrows():
        cod = r.get(col_prod, '')
        k = chave(cod)
        p = base_dict['prod'].get(k)
        
        cesta = ''
        if p and chave(p['marca']) in base_dict['cesta']:
            cesta = base_dict['cesta'][chave(p['marca'])]
        elif k in base_dict['cesta']:
            cesta = base_dict['cesta'][k]
            
        tipo_marca.append(cesta)
        
        cesta_e = ''
        if cesta == 'CERVEJA':
            emb_tipo = base_dict['embTipo'].get(chave(p['emb'])) if p else None
            cesta_e = emb_tipo if emb_tipo else 'OW'
        cesta_emb.append(cesta_e)
        
        cesta_he.append('HE' if k in base_dict['he'] else '')

    df['TIPO MARCA'] = tipo_marca
    df['CESTA EMBALAGEM'] = cesta_emb
    df['CESTA HE'] = cesta_he
    return df

# =====================================================================
# INTERFACE SIDEBAR (FILTROS E CONTROLES)
# =====================================================================
st.sidebar.title("⚙️ Filtros e Fontes")

url_cora = CONFIG['github_base_url'] + CONFIG['arquivoCora']
url_base = CONFIG['github_base_url'] + CONFIG['arquivoBase']
url_boni = CONFIG['github_base_url'] + CONFIG['arquivoBoni']

# Tentar carregar do GitHub
df_cora = carregar_csv_url(url_cora)
df_base_raw = carregar_csv_url(url_base)
df_boni = carregar_csv_url(url_boni)

# Fallback para uploads manuais se não ler do GitHub
with st.sidebar.expander("📁 Upload Manual (opcional)"):
    u_cora = st.file_uploader("Cora Pedidos (.csv)", type=['csv', 'txt'])
    u_base = st.file_uploader("BASE (.csv)", type=['csv', 'txt'])
    u_boni = st.file_uploader("03.02.37 (.csv)", type=['csv', 'txt'])
    
    if u_cora: df_cora = pd.read_csv(u_cora, sep=None, engine='python')
    if u_base: df_base_raw = pd.read_csv(u_base, sep=None, engine='python')
    if u_boni: df_boni = pd.read_csv(u_boni, sep=None, engine='python')

# Status da Leitura dos Ficheiros
st.sidebar.markdown("### 📌 Status da Leitura")
s_cora = "✔ Lido" if df_cora is not None else "❌ Não carregado"
s_base = "✔ Lido" if df_base_raw is not None else "❌ Não carregado"
s_boni = "✔ Lido" if df_boni is not None else "❌ Não carregado"

st.sidebar.markdown(f"- **Cora Pedidos:** {s_cora}")
st.sidebar.markdown(f"- **BASE:** {s_base}")
st.sidebar.markdown(f"- **03.02.37:** {s_boni}")

if df_cora is not None and df_base_raw is not None:
    base_dict = processar_base(df_base_raw)
    df_cora = derivar_colunas(df_cora, base_dict)
    if df_boni is not None:
        df_boni = derivar_colunas(df_boni, base_dict)

    # Datas disponíveis
    df_cora['DATA_ENTREGA_ISO'] = df_cora['DATA ENTREGA'].apply(parse_iso)
    datas = sorted([d for d in df_cora['DATA_ENTREGA_ISO'].unique() if d])
    data_sel = st.sidebar.date_input("Data de Entrega", datetime.strptime(datas[-1], "%Y-%m-%d") if datas else datetime.now())
    data_sel_str = data_sel.strftime("%Y-%m-%d")

    # Unidades
    opcoes_unidade = {'todas': 'Todas'}
    for u in CONFIG['unidades']:
        opcoes_unidade[u['cod']] = f"{u['nome']} ({u['cod']})"
    unidade_sel = st.sidebar.selectbox("Unidade", options=list(opcoes_unidade.keys()), format_func=lambda x: opcoes_unidade[x])

    # Visão (GVs / Setores)
    gvs_disp = []
    if unidade_sel != 'todas':
        u_obj = next((x for x in CONFIG['unidades'] if x['cod'] == unidade_sel), None)
        if u_obj: gvs_disp = u_obj['gvs']
    else:
        gvs_disp = CONFIG['unidades'][0]['gvs']

    opcoes_visao = {'todos': 'Todos'}
    for idx, g in enumerate(gvs_disp):
        opcoes_visao[f"gv{idx+1}"] = f"{g['nome']} ({g['de']}–{g['ate']})"
        for s in range(g['de'], g['ate'] + 1):
            opcoes_visao[f"s{s}"] = f"Setor {s}"

    visao_sel = st.sidebar.selectbox("Visão (GV / Setor)", options=list(opcoes_visao.keys()), format_func=lambda x: opcoes_visao[x])
    base_cat_sel = st.sidebar.selectbox("Categorias por GV/setor", options=['dia', 'tt'], format_func=lambda x: "VOL DIA" if x == 'dia' else "VOL TT (dia + buffer)")

    # =====================================================================
    # PROCESSAMENTO DOS DADOS (REGRAS DO RESUMO SELL OUT)
    # =====================================================================
    def filtrar_itens():
        out = []
        for _, r in df_cora.iterrows():
            if r['DATA_ENTREGA_ISO'] != data_sel_str:
                continue
            
            # Filtro Unidade
            un_cod = chave(r.get('COD. UNIDADE VENDA', ''))
            if unidade_sel != 'todas' and un_cod != chave(unidade_sel):
                continue
                
            # Ignorar cancelados
            if 'CANCEL' in norm(r.get('SITUACAO PEDIDO', '')):
                continue

            buf = norm(r.get('TIPO BUFFER', '')) not in ['', 'NAO', 'N', '0', '-', 'NENHUM']
            eh_falta = norm(r.get('SITUACAO ATEND. ITEM', '')) == 'FALTA'
            eh_bonif = 'BONIF' in (norm(r.get('DESC. TIPO MOVIMENTO', '')) + ' ' + norm(r.get('TIPO PEDIDO', '')))
            
            tipo = None
            if eh_falta:
                tipo = None if buf else 'falta'
            elif eh_bonif:
                tipo = 'bonif'
            elif buf:
                tipo = 'buffer'
            else:
                tipo = 'venda'

            if not tipo:
                continue

            cat = r.get('TIPO MARCA', '')
            cat = cat if cat in CATS else 'OUTROS'
            
            # Setor
            m = re.search(r'\d+', str(r.get('COD. SETOR', '')))
            setor = int(m.group(0)) if m else 0

            # Visão filtro
            if visao_sel != 'todos':
                if visao_sel.startswith('gv'):
                    gv_idx = int(visao_sel[2:]) - 1
                    g_info = gvs_disp[gv_idx] if gv_idx < len(gvs_disp) else None
                    if not (g_info and g_info['de'] <= setor <= g_info['ate']):
                        continue
                elif visao_sel.startswith('s'):
                    if setor != int(visao_sel[1:]):
                        continue

            vol_h = parse_num(r.get(CONFIG['campoHecto'], 0))
            val_v = parse_num(r.get(CONFIG['campoValorFalta'] if tipo == 'falta' else CONFIG['campoValor'], 0))

            out.append({
                'r': r, 'tipo': tipo, 'cat': cat, 'setor': setor, 'un': un_cod,
                'h': vol_h, 'v': val_v
            })
        return out

    itens = filtrar_itens()

    # =====================================================================
    # RENDERIZAÇÃO DOS PAINÉIS E TABELAS
    # =====================================================================
    st.markdown(f"<div class='gp7-title'>RESUMO DE SELL OUT — {data_sel.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)

    if not itens:
        st.warning("Nenhum registo encontrado para os filtros selecionados.")
    else:
        # Consolidação por Categoria
        res = {c: {'volDia': 0.0, 'buffer': 0.0, 'volHE': 0.0, 'volBees': 0.0, 'volBoni': 0.0, 'boniDia': 0.0, 'fat': 0.0} for c in CATS + ['OUTROS']}
        fat_total = 0.0
        buffer_total = 0.0
        
        for it in itens:
            c = res[it['cat']]
            r = it['r']
            if it['tipo'] == 'venda':
                c['volDia'] += it['h']
                c['fat'] += it['v']
                fat_total += it['v']
                if 'BEES' in (norm(r.get('CANAL ORIGEM', '')) + ' ' + norm(r.get('TIPO CANAL ORIGEM', ''))):
                    c['volBees'] += it['h']
                if norm(r.get('CESTA HE', '')) != '':
                    c['volHE'] += it['h']
            elif it['tipo'] == 'buffer':
                c['buffer'] += it['h']
                buffer_total += it['v']
            elif it['tipo'] == 'bonif':
                c['volBoni'] += it['h']
                c['boniDia'] += it['v']

        # Montagem do Dataframe de Resumo Sell Out
        rows_sell = []
        for cat in CATS:
            x = res[cat]
            vol_tt = x['volDia'] + x['buffer']
            peso_bees = (x['volBees'] / x['volDia'] * 100) if x['volDia'] else 0
            rows_sell.append({
                'CATEGORIA': cat,
                'VOL TT': f"{vol_tt:,.1f}",
                'VOL DIA': f"{x['volDia']:,.1f}",
                'BUFFER': f"{x['buffer']:,.1f}",
                'VENDA HE': f"{x['volHE']:,.1f}",
                'S/ BEES': f"{x['volDia'] - x['volBees']:,.1f}",
                'VOL BEES': f"{x['volBees']:,.1f}",
                'PESO BEES': f"{peso_bees:.1f}%",
                'VOL BONI DIA': f"{x['volBoni']:,.1f}",
                'FATURAMENTO': f"R$ {x['fat']:,.2f}"
            })
        
        st.subheader("📊 Sell Out por Categoria")
        st.dataframe(pd.DataFrame(rows_sell), use_container_width=True)

        # Métricas Rápidas Faturamento
        col1, col2, col3 = st.columns(3)
        col1.metric("Faturamento Dia Total", f"R$ {fat_total:,.2f}")
        col2.metric("Buffer Total (R$)", f"R$ {buffer_total:,.2f}")
        col3.metric("Faturamento + Buffer", f"R$ {fat_total + buffer_total:,.2f}")

else:
    st.info("A aguardar carregamento dos dados do GitHub ou upload de ficheiros no menu lateral...")
