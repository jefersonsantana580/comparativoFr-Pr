
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
    page_title="Comparativo Demanda",
    layout="wide"
)

st.title("📊 Comparativo de Demanda")
st.caption("Comparativo entre versões de demanda com filtros e cenários")

# =====================================================
# CONSTANTES
# =====================================================
PT_BR_MESES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

MES_RE = re.compile(
    r'^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}$',
    re.IGNORECASE
)

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def detectar_colunas_mes(df):
    return [c for c in df.columns if MES_RE.match(str(c))]

def garantir_numerico(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def colorir(val):
    if isinstance(val, (int, float)):
        if val > 0:
            return "color:green;font-weight:bold"
        if val < 0:
            return "color:red;font-weight:bold"
    return ""

# =====================================================
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO
# =====================================================

def processar_comparativo(bytes_xlsx, visao):
    xls = pd.ExcelFile(bytes_xlsx)

    # Definição dinâmica das abas
    if visao == "F.Response - Request":
        aba_base = "REQUEST"
        aba_comp = "F.RESPONSE"
        titulo_calc = "F.Response − Request"
    else:
        aba_base = "PLAN"
        aba_comp = "REQUEST"
        titulo_calc = "Request − Plan"

    df_base = pd.read_excel(xls, sheet_name=aba_base)
    df_comp = pd.read_excel(xls, sheet_name=aba_comp)

    # Detectar meses
    meses = detectar_colunas_mes(df_base)

    df_base = garantir_numerico(df_base, meses)
    df_comp = garantir_numerico(df_comp, meses)

    # Colunas dimensionais = tudo que NÃO é mês
    dim_cols = [c for c in df_base.columns if c not in meses]

    # Merge correto (alinhamento real)
    df = df_base.merge(
        df_comp,
        on=dim_cols,
        how="outer",
        suffixes=("_base", "_comp")
    )

    # Garantir NaN = 0
    for m in meses:
        df[f"{m}_base"] = df[f"{m}_base"].fillna(0)
        df[f"{m}_comp"] = df[f"{m}_comp"].fillna(0)

    # Cálculo
    for m in meses:
        df[m] = df[f"{m}_comp"] - df[f"{m}_base"]

    # Limpeza
    drop_cols = []
    for m in meses:
        drop_cols += [f"{m}_base", f"{m}_comp"]

    df_final = df.drop(columns=drop_cols)
    df_final["TOTAL"] = df_final[meses].sum(axis=1)

    return df_final, meses, titulo_calc


    # ==============================
    # CÁLCULO (AQUI É O CORAÇÃO)
    # ==============================
    df_result = df_comp[meses] - df_base[meses]

    df_final = df_base.reset_index()
    for m in meses:
        df_final[m] = df_result[m].values

    df_final["TOTAL"] = df_final[meses].sum(axis=1)

    return df_final, meses, titulo_calc

# =====================================================
# UI
# =====================================================
uploaded = st.file_uploader(
    "📂 Envie o Excel (PLAN, REQUEST e F.RESPONSE)",
    type=["xlsx"]
)

visao = st.radio(
    "Selecione a visão",
    options=[
        "F.Response - Request",
        "Request - Plan"
    ],
    horizontal=True
)

if uploaded:
    try:
        df_out, meses, titulo_calc = processar_comparativo(
            uploaded,
            visao
        )

        st.subheader(f"📈 Visão: {titulo_calc}")

       
st.dataframe(
    df_out,
    use_container_width=True
)


        # Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_out.to_excel(writer, index=False, sheet_name="COMPARATIVO")

        buffer.seek(0)

        st.download_button(
            "⬇️ Baixar Excel",
            data=buffer,
            file_name=f"comparativo_{visao.replace(' ', '_').replace('.', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error("❌ Erro ao processar o arquivo")
        st.exception(e)

else:
    st.info("Faça upload do Excel para iniciar.")
