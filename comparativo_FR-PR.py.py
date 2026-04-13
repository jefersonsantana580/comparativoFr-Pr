
# -*- coding: utf-8 -*-

import io
import re
import datetime as dt
import pandas as pd
import streamlit as st

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(
    page_title="Comparativo Request vs Plan / FR vs Request",
    layout="wide"
)

st.title("Comparativo Request vs Plan")
st.caption("Comparativo de demanda com filtros e cenários")

# =====================================================
# CONSTANTES
# =====================================================
PT_BR_MESES = ["jan","fev","mar","abr","mai","jun",
               "jul","ago","set","out","nov","dez"]

MES_RE = re.compile(
    r'^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}$',
    re.IGNORECASE
)

# =====================================================
# FUNÇÕES UTILITÁRIAS (ORIGINAIS)
# =====================================================
def detectar_colunas_mes(df):
    return [c for c in df.columns if MES_RE.match(str(c))]

def garantir_numerico(df, meses):
    for m in meses:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0)
    return df

# =====================================================
# FUNÇÃO PRINCIPAL (MESMA ESTRUTURA, NOVA VISÃO)
# =====================================================
def gerar_comparativo(xlsx_bytes, visao):
    xls = pd.ExcelFile(xlsx_bytes)

    df_plan = pd.read_excel(xls, sheet_name="PLAN")
    df_request = pd.read_excel(xls, sheet_name="REQUEST")
    df_fr = pd.read_excel(xls, sheet_name="F.RESPONSE")

    meses = detectar_colunas_mes(df_request)

    df_plan = garantir_numerico(df_plan, meses)
    df_request = garantir_numerico(df_request, meses)
    df_fr = garantir_numerico(df_fr, meses)

    # Dimensões (igual app original)
    dims = [
        "SITE",
        "PRODUCT NEED",
        "PRODUCT SERIES",
        "PRODUCT BRAND",
        "PRODUCT MARKET"
    ]

    # Base e comparador conforme visão
    if visao == "F.Response - Request":
        df_base = df_request
        df_comp = df_fr
        titulo = "F.Response − Request"
    else:
        df_base = df_plan
        df_comp = df_request
        titulo = "Request − Plan"

    # Agrupamento ORIGINAL
    g_base = df_base.groupby(dims)[meses].sum()
    g_comp = df_comp.groupby(dims)[meses].sum()

    # Alinhamento natural (como antes)
    df_calc = g_comp.sub(g_base, fill_value=0).reset_index()

    df_calc["TOTAL"] = df_calc[meses].sum(axis=1)

    return df_calc, meses, titulo

# =====================================================
# UI
# =====================================================
uploaded = st.file_uploader(
    "📂 Envie o Excel (PLAN, REQUEST e F.RESPONSE)",
    type=["xlsx"]
)

visao = st.radio(
    "Selecione a visão",
    ["Request - Plan", "F.Response - Request"],
    horizontal=True
)

if uploaded:
    try:
        df_out, meses, titulo = gerar_comparativo(
            uploaded,
            visao
        )

        st.subheader(f"📊 Visão: {titulo}")

        st.dataframe(
            df_out,
            use_container_width=True
        )

        # Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_out.to_excel(
                writer,
                index=False,
                sheet_name="COMPARATIVO"
            )
        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar Excel",
            buffer,
            file_name=f"comparativo_{titulo.replace(' ', '_').replace('.', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error("❌ Erro ao processar o arquivo")
        st.exception(e)
else:
    st.info("Faça upload do Excel para iniciar.")
