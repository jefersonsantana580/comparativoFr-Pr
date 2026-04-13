# -*- coding: utf-8 -*-
"""Comparativo P.Request Vs Op.Plan / F.Response Vs Request

Este app foi refeito do zero mantendo a *mesma ideia* do app original:
- Upload de Excel
- Filtros na página principal (chips/multiselect)
- Várias visões (tabelas) com o MESMO cálculo (diferença entre cenários)
- Formatação verde/vermelho para positivos/negativos

Visões disponíveis via toggle:
- Request - Plan (REQUEST − PLAN)
- F.Response - Request (F.RESPONSE − REQUEST)

Requisitos: streamlit, pandas, openpyxl
"""

import io
import re
import datetime as dt
from typing import List, Tuple

import pandas as pd
import streamlit as st

# =====================================================
# CONFIGURAÇÃO
# =====================================================
st.set_page_config(page_title="Comparativo de Demanda", layout="wide")

PT_BR_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MES_RE = re.compile(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}$", re.IGNORECASE)

# Dimensões principais (iguais à tela de exemplo). Se alguma não existir no Excel, ela será ignorada.
DEFAULT_FILTER_COLS = ["PRODUCT BRAND", "PRODUCT MARKET", "SITE", "PRODUCT NEED"]
DEFAULT_GROUP_NEED_SERIES = ["SITE", "PRODUCT NEED", "PRODUCT SERIES", "PRODUCT BRAND", "PRODUCT MARKET"]


# =====================================================
# UTILITÁRIOS
# =====================================================

def _normalize_header(col):
    """Normaliza cabeçalhos de mês caso venham como data (Timestamp/date)."""
    if isinstance(col, (pd.Timestamp, dt.date)):
        return f"{PT_BR_MESES[col.month - 1]}/{col.year % 100:02d}"
    return str(col).strip()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_header(c) for c in df.columns]
    return df


def detectar_colunas_mes(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if MES_RE.match(str(c))]


def garantir_numerico(df: pd.DataFrame, meses: List[str]) -> pd.DataFrame:
    df = df.copy()
    for m in meses:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0)
    return df


def pick_existing_cols(df: pd.DataFrame, cols: List[str]) -> List[str]:
    return [c for c in cols if c in df.columns]


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Aplica filtros do tipo {col: set(valores_selecionados)}."""
    out = df
    for col, selected in filters.items():
        if col in out.columns and selected:
            out = out[out[col].isin(selected)]
    return out


def align_and_subtract(g_comp: pd.DataFrame, g_base: pd.DataFrame) -> pd.DataFrame:
    """Subtrai mantendo comportamento 'original' (somente interseção de chaves)."""
    a, b = g_comp.align(g_base, join="inner", axis=0)
    return a - b


def add_total(df: pd.DataFrame, meses: List[str]) -> pd.DataFrame:
    df = df.copy()
    df["TOTAL"] = df[meses].sum(axis=1)
    return df


def style_signed(df: pd.DataFrame, subset: List[str]):
    """Retorna Styler com números negativos em vermelho e positivos em verde.

    Compatível com pandas novos (Styler.map) e antigos (Styler.applymap).
    """
    def _color(val):
        try:
            v = float(val)
        except Exception:
            return ""
        if v < 0:
            return "color:#ff4d4f;font-weight:600;"  # vermelho
        if v > 0:
            return "color:#52c41a;font-weight:600;"  # verde
        return ""

    styler = df.style
    if hasattr(styler, "map"):
        return styler.map(_color, subset=subset)
    # fallback pandas antigo
    return styler.applymap(_color, subset=subset)


# =====================================================
# PROCESSAMENTO
# =====================================================

def load_sheets(xlsx_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    plan = normalize_columns(pd.read_excel(xls, sheet_name="PLAN"))
    req = normalize_columns(pd.read_excel(xls, sheet_name="REQUEST"))
    fr = normalize_columns(pd.read_excel(xls, sheet_name="F.RESPONSE"))
    return plan, req, fr


def compute_view(plan: pd.DataFrame, req: pd.DataFrame, fr: pd.DataFrame, visao: str) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Retorna (base, comp, titulo). Base é o termo subtraído."""
    if visao == "F.Response - Request":
        return req, fr, "F.Response − Request"
    return plan, req, "Request − Plan"


def comparativo(df_base: pd.DataFrame, df_comp: pd.DataFrame, dims: List[str], meses: List[str]) -> pd.DataFrame:
    dims = pick_existing_cols(df_base, dims)
    # agrupa e subtrai com interseção (comportamento do app antigo)
    g_base = df_base.groupby(dims, dropna=False)[meses].sum()
    g_comp = df_comp.groupby(dims, dropna=False)[meses].sum()
    diff = align_and_subtract(g_comp, g_base)
    out = diff.reset_index()
    out = add_total(out, meses)
    return out


def resumo_por_mes(df: pd.DataFrame, meses: List[str]) -> pd.DataFrame:
    """Resumo geral: soma da diferença por mês e total."""
    row = {m: df[m].sum() for m in meses}
    row["TOTAL"] = sum(row[m] for m in meses)
    return pd.DataFrame([row])


# =====================================================
# UI
# =====================================================

st.title("Comparativo de Demanda")
st.caption("Comparativo com filtros, múltiplas visões e cenários (verde/verm.)")

uploaded = st.file_uploader("📂 Envie o Excel (PLAN, REQUEST e F.RESPONSE)", type=["xlsx"])

col_a, col_b, col_c = st.columns([2, 2, 3])
with col_a:
    visao = st.radio(
        "Selecione a visão",
        ["Request - Plan", "F.Response - Request"],
        horizontal=True,
    )
with col_b:
    show_debug = st.checkbox("Exibir diagnóstico", value=False)
with col_c:
    st.markdown("""<div style='opacity:.8;padding-top:6px'>
<b>Interpretação:</b> valores positivos = excesso do comparador; negativos = déficit vs base.
</div>""", unsafe_allow_html=True)

if not uploaded:
    st.info("Faça upload do Excel para iniciar.")
    st.stop()

# Carrega dados
xlsx_bytes = uploaded.read()
plan_df, req_df, fr_df = load_sheets(xlsx_bytes)

# Detecta meses a partir de REQUEST (normalmente tem a mesma lista)
meses = detectar_colunas_mes(req_df)

if not meses:
    st.error("Não encontrei colunas de mês no formato 'jan/26'. Verifique o layout do Excel.")
    if show_debug:
        st.write("Colunas encontradas na REQUEST:", list(req_df.columns))
    st.stop()

# Converte números
plan_df = garantir_numerico(plan_df, meses)
req_df = garantir_numerico(req_df, meses)
fr_df = garantir_numerico(fr_df, meses)

# Define base/comp conforme toggle
base_df, comp_df, titulo_calc = compute_view(plan_df, req_df, fr_df, visao)

# ---------- FILTROS (página principal) ----------
st.subheader("Filtros")

filter_cols = pick_existing_cols(base_df, DEFAULT_FILTER_COLS)

# fontes de valores: usar a união base+comp para não "sumir" opções ao trocar a visão
union_df = pd.concat([base_df[filter_cols], comp_df[filter_cols]], ignore_index=True).drop_duplicates() if filter_cols else pd.DataFrame()

filters = {}
cols = st.columns(4)
for i, col_name in enumerate(filter_cols):
    values = sorted([v for v in union_df[col_name].dropna().unique().tolist()])
    with cols[i % 4]:
        selected = st.multiselect(
            col_name,
            options=values,
            default=values,
        )
    filters[col_name] = set(selected)

# aplica filtros nos dois dataframes
base_f = apply_filters(base_df, filters)
comp_f = apply_filters(comp_df, filters)

if show_debug:
    st.markdown("### Diagnóstico")
    st.write({
        "Visão": titulo_calc,
        "Linhas BASE (antes)": len(base_df),
        "Linhas COMP (antes)": len(comp_df),
        "Linhas BASE (filtrado)": len(base_f),
        "Linhas COMP (filtrado)": len(comp_f),
        "Meses detectados": meses,
    })

# ---------- VISÕES / TABELAS ----------
st.subheader(f"Visão: {titulo_calc}")

# 1) Comparativo principal (NEED + SERIES)
df_need_series = comparativo(base_f, comp_f, DEFAULT_GROUP_NEED_SERIES, meses)

st.markdown("#### Comparativo por PRODUCT NEED + PRODUCT SERIES")
styled = style_signed(df_need_series, subset=meses + ["TOTAL"])
st.dataframe(styled, use_container_width=True, height=520)

# 2) Comparativo por PRODUCT SERIES
st.markdown("#### Comparativo por PRODUCT SERIES")
dims_series = ["SITE", "PRODUCT SERIES", "PRODUCT BRAND", "PRODUCT MARKET"]
df_series = comparativo(base_f, comp_f, dims_series, meses)
st.dataframe(style_signed(df_series, subset=meses + ["TOTAL"]), use_container_width=True, height=420)

# 3) Comparativo por PRODUCT NEED
st.markdown("#### Comparativo por PRODUCT NEED")
dims_need = ["SITE", "PRODUCT NEED", "PRODUCT BRAND", "PRODUCT MARKET"]
df_need = comparativo(base_f, comp_f, dims_need, meses)
st.dataframe(style_signed(df_need, subset=meses + ["TOTAL"]), use_container_width=True, height=420)

# 4) Resumo por mês
st.markdown("#### Resumo geral (diferença total por mês)")
df_resumo_mes = resumo_por_mes(df_need_series, meses)
st.dataframe(style_signed(df_resumo_mes, subset=meses + ["TOTAL"]), use_container_width=True)

# ---------- DOWNLOAD ----------
st.divider()

out_buf = io.BytesIO()
with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
    df_need_series.to_excel(writer, index=False, sheet_name="NEED_SERIES")
    df_series.to_excel(writer, index=False, sheet_name="SERIES")
    df_need.to_excel(writer, index=False, sheet_name="NEED")
    df_resumo_mes.to_excel(writer, index=False, sheet_name="RESUMO_MES")

out_buf.seek(0)

st.download_button(
    "⬇️ Baixar Excel com todas as visões",
    data=out_buf,
    file_name=f"comparativo_{titulo_calc.replace(' ', '_').replace('.', '')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
