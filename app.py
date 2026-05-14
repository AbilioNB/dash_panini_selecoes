import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Dashboard - Seleções", layout="wide", page_icon="⚽")

st.title("⚽ Dashboard de Acompanhamento - Seleções")
st.markdown("Acompanhamento em tempo real baseado na nossa base de dados oficial.")

# --- FUNÇÃO PARA LER DO GOOGLE SHEETS ---
def get_google_sheet_csv_url(url):
    if "docs.google.com" in url and "/edit" in url:
        doc_id = url.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
    return url


sheet_url = "https://docs.google.com/spreadsheets/d/1RKQgjvb2QImzO8cAhVtARSKNdJrdH22b1KNqqiqFAZw/edit?usp=sharing"

try:
    csv_url = get_google_sheet_csv_url(sheet_url)
    df = pd.read_csv(csv_url)
    
    # --- CORREÇÃO E LIMPEZA DE DADOS ---
    df = df.dropna(subset=['SELECOES'])
    df['SELECOES'] = df['SELECOES'].str.strip()
    df['GRUPO'] = df['GRUPO'].str.strip()

    # --- CÁLCULOS GERAIS ---
    qtd_selecoes = len(df)
    total_figurinhas_possiveis = qtd_selecoes * 20
    
    total_obtidas = int(df['TOTAL'].sum())
    total_faltante = int(df['FALTANTE'].sum())
    percentual_conclusao = (total_obtidas / total_figurinhas_possiveis) * 100

    # --- CRIAÇÃO DAS ABAS ---
    tab1, tab2 = st.tabs(["📊 Dashboard Geral", "🔍 Pesquisa de Faltantes"])

    # ==========================================
    # ABA 1: DASHBOARD GERAL (GRÁFICOS)
    # ==========================================
    with tab1:
        st.header("📊 Resumo Geral")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Seleções", f"{qtd_selecoes}")
        with col2:
            st.metric("Total Atual (Obtidas)", f"{total_obtidas}")
        with col3:
            st.metric("Total Faltante", f"{total_faltante}")
        with col4:
            st.metric("% de Finalização Geral", f"{percentual_conclusao:.1f}%")

        st.divider()

        # --- GRÁFICO 1 ---
        st.header("1️⃣ Seleções que mais precisam de figurinhas")
        df_faltantes = df[['SELECOES', 'FALTANTE']].sort_values(by='FALTANTE', ascending=False)
        fig_selecoes = px.bar(df_faltantes, 
                              x='SELECOES', 
                              y='FALTANTE',
                              labels={'SELECOES': 'Seleção', 'FALTANTE': 'Qtd. Faltante'},
                              color='FALTANTE',
                              color_continuous_scale='Reds')
        st.plotly_chart(fig_selecoes, use_container_width=True)

        # --- PREPARAÇÃO DE DADOS POR GRUPO ---
        df_grupo = df.groupby('GRUPO').agg(
            OBTIDAS_GRUPO=('TOTAL', 'sum'),
            FALTANTES_GRUPO=('FALTANTE', 'sum'),
            QTD_SELECOES=('SELECOES', 'count')
        ).reset_index()

        df_grupo['TOTAL_POSSIVEL_GRUPO'] = df_grupo['QTD_SELECOES'] * 20
        df_grupo['PERCENTUAL_GRUPO'] = (df_grupo['OBTIDAS_GRUPO'] / df_grupo['TOTAL_POSSIVEL_GRUPO']) * 100

        st.divider()
        
        col_grafico2, col_grafico3 = st.columns(2)

        with col_grafico2:
            # --- GRÁFICO 2 ---
            st.header("2️⃣ Balanceamento por Grupo")
            df_balanceamento = df_grupo[['GRUPO', 'OBTIDAS_GRUPO', 'FALTANTES_GRUPO']].melt(
                id_vars='GRUPO', var_name='Status', value_name='Quantidade'
            )
            df_balanceamento['Status'] = df_balanceamento['Status'].replace({
                'OBTIDAS_GRUPO': 'Obtidas', 'FALTANTES_GRUPO': 'Faltantes'
            })
            fig_balanceamento = px.bar(df_balanceamento, x='GRUPO', y='Quantidade', color='Status',
                                       barmode='stack', color_discrete_map={'Obtidas': '#2ecc71', 'Faltantes': '#e74c3c'})
            st.plotly_chart(fig_balanceamento, use_container_width=True)

        with col_grafico3:
            # --- GRÁFICO 3 ---
            st.header("3️⃣ Percentual de Finalização por Grupo")
            fig_percentual = px.bar(df_grupo, x='GRUPO', y='PERCENTUAL_GRUPO', text='PERCENTUAL_GRUPO',
                                    labels={'PERCENTUAL_GRUPO': '% Concluído', 'GRUPO': 'Grupo'},
                                    color='PERCENTUAL_GRUPO', color_continuous_scale='Blues')
            fig_percentual.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_percentual.update_layout(yaxis_range=[0, 110]) 
            st.plotly_chart(fig_percentual, use_container_width=True)


    # ==========================================
    # ABA 2: PESQUISA DE FALTANTES
    # ==========================================
    with tab2:
        st.header("🔍 Consulta de Números Faltantes")
        st.markdown("Verifique rapidamente quais figurinhas faltam para organizar suas trocas.")
        
        # Seleção do tipo de filtro
        tipo_busca = st.radio("Como você quer visualizar as faltantes?", 
                              ["Por Seleção", "Por Grupo"], 
                              horizontal=True)
        
        st.divider()

        if tipo_busca == "Por Seleção":
            selecao_escolhida = st.selectbox("Escolha a Seleção:", df['SELECOES'].unique())
            dados_selecao = df[df['SELECOES'] == selecao_escolhida].iloc[0]
            
            figurinhas_faltantes = []
            for i in range(1, 21):
                col_name = str(i)
                if col_name in df.columns and dados_selecao[col_name] == 0:
                    figurinhas_faltantes.append(col_name)
                    
            if len(figurinhas_faltantes) > 0:
                st.warning(f"**{selecao_escolhida}** - Faltam {len(figurinhas_faltantes)} figurinhas:\n\n### {', '.join(figurinhas_faltantes)}")
            else:
                st.success(f"🎉 Parabéns! A seleção de **{selecao_escolhida}** está 100% completa!")

        elif tipo_busca == "Por Grupo":
            # Pega os grupos de forma ordenada (A, B, C...)
            grupos_ordenados = sorted(df['GRUPO'].unique())
            grupo_escolhido = st.selectbox("Escolha o Grupo:", grupos_ordenados)
            
            # Filtra os dados apenas para as seleções daquele grupo
            df_grupo_filtrado = df[df['GRUPO'] == grupo_escolhido]
            
            st.subheader(f"Faltantes do Grupo {grupo_escolhido}")
            
            # Itera sobre todas as seleções do grupo para listar uma abaixo da outra
            for index, row in df_grupo_filtrado.iterrows():
                selecao = row['SELECOES']
                figurinhas_faltantes = []
                for i in range(1, 21):
                    col_name = str(i)
                    if col_name in df.columns and row[col_name] == 0:
                        figurinhas_faltantes.append(col_name)
                
                # Renderiza os blocos de aviso dependendo do status de cada seleção
                if len(figurinhas_faltantes) > 0:
                    st.info(f"**{selecao}** ({len(figurinhas_faltantes)} faltantes):  \n{', '.join(figurinhas_faltantes)}")
                else:
                    st.success(f"**{selecao}**: 🎉 100% completa!")

except Exception as e:
    st.error(f"Erro ao carregar os dados. Verifique se o link hardcoded no código está correto e se a planilha do Sheets é pública. Detalhe do erro: {e}")