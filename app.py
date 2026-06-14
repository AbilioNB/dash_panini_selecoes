import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import re
from pathlib import Path
from datetime import datetime

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


def carregar_dados(sheet_url):
    csv_url = get_google_sheet_csv_url(sheet_url)
    df_local = pd.read_csv(csv_url)

    df_local = df_local.dropna(subset=['SELECOES'])
    df_local['SELECOES'] = df_local['SELECOES'].astype(str).str.strip()
    df_local['GRUPO'] = df_local['GRUPO'].astype(str).str.strip()
    if 'SIGLA' in df_local.columns:
        df_local['SIGLA'] = df_local['SIGLA'].astype(str).str.strip().str.upper()

    return df_local


def recalcular_totais(df_local):
    colunas_figurinhas = [str(i) for i in range(1, 21) if str(i) in df_local.columns]

    if colunas_figurinhas:
        df_local['TOTAL'] = df_local[colunas_figurinhas].sum(axis=1)
        df_local['FALTANTE'] = len(colunas_figurinhas) - df_local['TOTAL']

    return df_local


def obter_figurinhas_faltantes(linha, df_referencia):
    figurinhas_faltantes = []
    for i in range(1, 21):
        col_name = str(i)
        if col_name in df_referencia.columns and linha[col_name] == 0:
            figurinhas_faltantes.append(col_name)
    return figurinhas_faltantes


def aplicar_aquisicoes_no_dataframe(df_local):
    banco_path = get_banco_path()
    if not banco_path.exists():
        return df_local

    with sqlite3.connect(banco_path) as conexao:
        try:
            historico = pd.read_sql_query(
                "SELECT DATA_HORA, SELECAO, NUMERO FROM aquisicoes ORDER BY DATA_HORA ASC",
                conexao,
            )
        except Exception:
            return df_local

    if historico.empty:
        return df_local

    for _, registro in historico.iterrows():
        selecao = str(registro["SELECAO"]).strip()
        numero = str(registro["NUMERO"]).strip()

        if numero not in df_local.columns:
            continue

        mascara = df_local["SELECOES"].astype(str).str.strip() == selecao
        if mascara.any():
            df_local.loc[mascara, numero] = 1

    return recalcular_totais(df_local)


def get_banco_path():
    return Path(__file__).with_name("dados.sqlite")


def carregar_dados_locais(sheet_url):
    banco_path = get_banco_path()
    banco_ja_existia = banco_path.exists()

    try:
        df_local = carregar_dados(sheet_url)
        df_local = recalcular_totais(df_local)

        with sqlite3.connect(banco_path) as conexao:
            df_local.to_sql("selecoes", conexao, if_exists="replace", index=False)
            if not banco_ja_existia:
                pd.DataFrame(columns=["DATA_HORA", "SELECAO", "NUMERO"]).to_sql(
                    "aquisicoes", conexao, if_exists="replace", index=False
                )
    except Exception:
        if not banco_ja_existia:
            raise

        with sqlite3.connect(banco_path) as conexao:
            df_local = pd.read_sql_query("SELECT * FROM selecoes", conexao)

    df_local = df_local.fillna(0)
    return aplicar_aquisicoes_no_dataframe(df_local)


def salvar_dados_locais(df_local):
    banco_path = get_banco_path()
    with sqlite3.connect(banco_path) as conexao:
        df_local.to_sql("selecoes", conexao, if_exists="replace", index=False)


def registrar_aquisicao_no_historico(selecao, numero):
    banco_path = get_banco_path()
    historico = pd.DataFrame([
        {
            "DATA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "SELECAO": selecao,
            "NUMERO": numero,
        }
    ])

    with sqlite3.connect(banco_path) as conexao:
        historico.to_sql("aquisicoes", conexao, if_exists="append", index=False)


def carregar_historico_aquisicoes():
    banco_path = get_banco_path()
    if not banco_path.exists():
        return pd.DataFrame(columns=["DATA_HORA", "SELECAO", "NUMERO"])

    with sqlite3.connect(banco_path) as conexao:
        try:
            return pd.read_sql_query("SELECT DATA_HORA, SELECAO, NUMERO FROM aquisicoes ORDER BY DATA_HORA DESC", conexao)
        except Exception:
            return pd.DataFrame(columns=["DATA_HORA", "SELECAO", "NUMERO"])


def limpar_cache_aquisicoes():
    banco_path = get_banco_path()
    if not banco_path.exists():
        return

    with sqlite3.connect(banco_path) as conexao:
        conexao.execute("DELETE FROM aquisicoes")
        conexao.commit()


sheet_url = "https://docs.google.com/spreadsheets/d/1RKQgjvb2QImzO8cAhVtARSKNdJrdH22b1KNqqiqFAZw/edit?usp=sharing"

try:
    st.session_state.df_base = carregar_dados_locais(sheet_url)
    st.session_state.df_atual = recalcular_totais(st.session_state.df_base.copy())
    st.session_state.historico_aquisicoes = carregar_historico_aquisicoes()

    if 'mensagem_acao' in st.session_state:
        st.success(st.session_state.mensagem_acao)
        del st.session_state.mensagem_acao

    df = st.session_state.df_atual

    # --- CÁLCULOS GERAIS ---
    qtd_selecoes = len(df)
    total_figurinhas_possiveis = qtd_selecoes * 20
    
    total_obtidas = int(df['TOTAL'].sum())
    total_faltante = int(df['FALTANTE'].sum())
    percentual_conclusao = (total_obtidas / total_figurinhas_possiveis) * 100

    # --- CRIAÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard Geral", "🔍 Pesquisa de Faltantes", "🔎 Pesquisa por Sigla", "➕ Registrar Aquisição", "📋 Faltantes por Grupo"])

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
                figurinhas_faltantes = obter_figurinhas_faltantes(row, df)
                
                # Renderiza os blocos de aviso dependendo do status de cada seleção
                if len(figurinhas_faltantes) > 0:
                    st.info(f"**{selecao}** ({len(figurinhas_faltantes)} faltantes):  \n{', '.join(figurinhas_faltantes)}")
                else:
                    st.success(f"**{selecao}**: 🎉 100% completa!")

    # ==========================================
    # ABA 5: FALTANTES POR GRUPO
    # ==========================================
    with tab5:
        st.header("📋 Faltantes por Grupo")
        st.markdown("Visão consolidada de todas as seleções, organizada por grupo e ordenada alfabeticamente.")

        grupos_ordenados = sorted(df['GRUPO'].dropna().unique())

        for grupo in grupos_ordenados:
            df_grupo = df[df['GRUPO'] == grupo].copy().sort_values(by='SELECOES')
            with st.expander(f"Grupo {grupo} - {len(df_grupo)} seleções", expanded=True):
                linhas_resumo = []

                for _, row in df_grupo.iterrows():
                    figurinhas_faltantes = obter_figurinhas_faltantes(row, df)
                    if not figurinhas_faltantes:
                        continue
                    linhas_resumo.append({
                        "SELECAO": row['SELECOES'],
                        "QTD_FALTANTES": len(figurinhas_faltantes),
                        "FALTANTES": ", ".join(figurinhas_faltantes),
                    })

                if not linhas_resumo:
                    st.caption("Nenhuma seleção com faltantes neste grupo.")
                    continue

                df_resumo = pd.DataFrame(linhas_resumo).sort_values(by=['QTD_FALTANTES', 'SELECAO'], ascending=[False, True])
                st.dataframe(df_resumo, use_container_width=True, hide_index=True)

    # ==========================================
    # ABA 3: PESQUISA POR SIGLA
    # ==========================================
    with tab3:
        st.header("🔎 Consulta por Sigla")
        st.markdown("Digite a sigla e o número da figurinha, por exemplo: CZE2.")

        with st.form("form_pesquisa_sigla"):
            sigla_digitada = st.text_input("Digite a sigla:", placeholder="Ex.: CZE2").strip().upper()
            pesquisar_sigla = st.form_submit_button("Pesquisar sigla")

        if pesquisar_sigla:
            if 'SIGLA' not in df.columns:
                st.error("A coluna SIGLA não está disponível na base carregada.")
            elif not sigla_digitada:
                st.warning("Digite uma sigla para pesquisar.")
            else:
                correspondencia = re.match(r"^([A-ZÀ-ÿ]+)(\d+)?$", sigla_digitada)

                if not correspondencia:
                    st.error("Use o formato SIGLA+NÚMERO, por exemplo CZE2.")
                else:
                    sigla_base = correspondencia.group(1)
                    numero_figurinhas = correspondencia.group(2)

                    siglas_base = df['SIGLA'].astype(str).str.strip().str.upper()
                    resultado_sigla = df[siglas_base == sigla_base]

                    if resultado_sigla.empty:
                        st.error("Não obitida")
                    else:
                        linha = resultado_sigla.iloc[0]

                        if not numero_figurinhas:
                            st.caption(f"Encontrada na seleção: {linha['SELECOES']} | SIGLA: {linha['SIGLA']}")
                            st.success("Já obitida")
                        else:
                            coluna_figura = numero_figurinhas

                            if coluna_figura not in df.columns:
                                st.error("Não obitida")
                            elif int(linha[coluna_figura]) == 1:
                                st.caption(f"Encontrada na seleção: {linha['SELECOES']} | SIGLA: {linha['SIGLA']}")
                                st.success("Já obitida")
                            else:
                                st.caption(f"Encontrada na seleção: {linha['SELECOES']} | SIGLA: {linha['SIGLA']}")
                                st.error("Não obitida")

    # ==========================================
    # ABA 4: REGISTRAR AQUISIÇÃO
    # ==========================================
    with tab4:
        st.header("➕ Registrar Aquisição de Figurinhas")
        st.markdown("Escolha o país, selecione o número que estava faltando e atualize a tabela em tempo real.")
        st.info("As alterações são salvas localmente em um banco SQLite dentro do projeto.")

        confirmar_limpeza = st.checkbox("Confirmo que quero limpar o cache local de aquisições")

        if st.button("Limpar cache local de aquisições", disabled=not confirmar_limpeza):
            limpar_cache_aquisicoes()
            st.session_state.pop("historico_aquisicoes", None)
            st.session_state.pop("mensagem_acao", None)
            st.rerun()

        selecao_aquisicao = st.selectbox("Escolha o País / Seleção:", sorted(df['SELECOES'].unique()), key="selecao_aquisicao")
        df_selecao_aquisicao = df[df['SELECOES'] == selecao_aquisicao].iloc[0]

        numeros_faltantes = [
            str(i)
            for i in range(1, 21)
            if str(i) in df.columns and df_selecao_aquisicao[str(i)] == 0
        ]

        numero_aquisicao = st.selectbox(
            "Escolha o número adquirido:",
            numeros_faltantes if numeros_faltantes else ["Nenhum número faltante"],
            disabled=not numeros_faltantes,
            key=f"numero_aquisicao_{selecao_aquisicao}",
        )

        registrar = st.button("Registrar aquisição")

        if registrar:
            if not numeros_faltantes:
                st.warning(f"A seleção **{selecao_aquisicao}** já está completa.")
            else:
                idx_selecao = df.index[df['SELECOES'] == selecao_aquisicao][0]
                linha_planilha = idx_selecao + 2

                if df.loc[idx_selecao, numero_aquisicao] == 1:
                    st.info(f"O número **{numero_aquisicao}** já estava registrado como adquirido para **{selecao_aquisicao}**.")
                else:
                    df_atualizado = st.session_state.df_atual.copy()
                    df_atualizado.loc[idx_selecao, numero_aquisicao] = 1
                    df_atualizado = recalcular_totais(df_atualizado)
                    registrar_aquisicao_no_historico(selecao_aquisicao, numero_aquisicao)
                    salvar_dados_locais(df_atualizado)
                    st.session_state.df_base = df_atualizado.copy()
                    st.session_state.df_atual = df_atualizado
                    novo_registro = pd.DataFrame([
                        {
                            "DATA_HORA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "SELECAO": selecao_aquisicao,
                            "NUMERO": numero_aquisicao,
                        }
                    ])
                    historico_atual = st.session_state.get("historico_aquisicoes")
                    if historico_atual is None or historico_atual.empty:
                        st.session_state.historico_aquisicoes = novo_registro
                    else:
                        st.session_state.historico_aquisicoes = pd.concat(
                            [novo_registro, historico_atual],
                            ignore_index=True,
                        )
                    st.session_state.mensagem_acao = f"Aquisição registrada com sucesso: **{selecao_aquisicao}** - número **{numero_aquisicao}**."
                    st.rerun()

        st.divider()
        st.subheader("Tabela atualizada")
        colunas_tabela = ['SELECOES', 'GRUPO', 'TOTAL', 'FALTANTE'] + [str(i) for i in range(1, 21) if str(i) in df.columns]
        df_tabela = df[colunas_tabela].copy()

        def colorir_valor(valor):
            if valor == 0:
                return 'background-color: #ffcccc; color: #8b0000; font-weight: bold;'
            if valor == 1:
                return 'background-color: #ccffcc; color: #006400; font-weight: bold;'
            return ''

        colunas_figurinhas = [str(i) for i in range(1, 21) if str(i) in df_tabela.columns]
        try:
            styler = df_tabela.style
            if hasattr(styler, "map"):
                df_estilizado = styler.map(colorir_valor, subset=colunas_figurinhas)
            else:
                df_estilizado = styler.applymap(colorir_valor, subset=colunas_figurinhas)
        except Exception:
            df_estilizado = df_tabela
        st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Exportar histórico")
        historico_aquisicoes = st.session_state.get("historico_aquisicoes")
        if historico_aquisicoes is None:
            historico_aquisicoes = carregar_historico_aquisicoes()
            st.session_state.historico_aquisicoes = historico_aquisicoes

        if historico_aquisicoes.empty:
            st.caption("Nenhuma aquisição registrada ainda.")
        else:
            csv_historico = historico_aquisicoes.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Baixar CSV com País e Número",
                data=csv_historico,
                file_name="historico_aquisicoes.csv",
                mime="text/csv",
            )
            st.dataframe(historico_aquisicoes, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao carregar os dados. Verifique se o link hardcoded no código está correto e se a planilha do Sheets é pública. Detalhe do erro: {e}")