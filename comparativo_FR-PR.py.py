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
    page_title="Comparativo Request Vs Plan",
    layout="wide"
)

st.title("Comparativo Request Vs Plan")
st.caption("Comparativo entre cenários com filtros, resumos e exportação")

PT_BR_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

MES_RE = re.compile(
    r'^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}$',
    re.IGNORECASE
)

# =====================================================
# FUNÇÕES UTILITÁRIAS
# =====================================================
def _normalize_header(col):
    if isinstance(col, (pd.Timestamp, dt.date)):
        return f"{PT_BR_MESES[col.month-1]}/{col.year % 100:02d}"

    s = str(col).replace("\u00a0", " ").strip().lower()
    s = re.sub(r"[-_ ]+", "/", s)

    m = re.match(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/(\d{2,4})$", s)
    if m:
        return f"{m.group(1)}/{m.group(2)[-2:]}"

    m = re.match(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)(\d{2})$", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    return s


def detectar_colunas_mes(df):
    cols_mes = []
    debug_map = {}

    for c in df.columns:
        alias = _normalize_header(c)
        debug_map[str(c)] = alias
        if MES_RE.match(alias or ""):
            cols_mes.append(c)

    def ordem(c):
        mm, yy = debug_map[str(c)].split("/")
        return int(yy), PT_BR_MESES.index(mm)

    return sorted(cols_mes, key=ordem), debug_map


def garantir_numerico(df, meses):
    for m in meses:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors="coerce")
    return df


def colorir_valores(val):
    if isinstance(val, (int, float)):
        if val < 0:
            return "color:red;font-weight:bold;"
        if val > 0:
            return "color:green;font-weight:bold;"
    return ""


def formatar_tabela(df):
    df = df.fillna(0)
    cols_num = df.select_dtypes(include="number").columns

    styler = (
        df.style
        .format(lambda x: f"{x:,.0f}".replace(",", "."), subset=cols_num)
        .map(colorir_valores, subset=cols_num)
        .set_properties(subset=cols_num, **{"text-align": "center"})
        .set_properties(subset=df.columns.difference(cols_num), **{"text-align": "left"})
    )
    return styler


# =====================================================
# FUNÇÃO PRINCIPAL
# =====================================================
def gerar_passo1(xlsx_bytes, show_debug=False, visao="Request - Plan", incluir_outer=False):

    xls_original = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")

    # Leitura das abas
    plan = pd.read_excel(xls_original, "PLAN", engine="openpyxl")
    req = pd.read_excel(xls_original, "REQUEST", engine="openpyxl")

    fr = None
    if "F.RESPONSE" in xls_original.sheet_names:
        fr = pd.read_excel(xls_original, "F.RESPONSE", engine="openpyxl")

    if visao == "F.Response - Request" and fr is None:
        raise ValueError("Aba 'F.RESPONSE' não encontrada no Excel enviado.")

    # Detecta meses considerando as abas disponíveis
    meses_plan, map_plan = detectar_colunas_mes(plan)
    meses_req, map_req = detectar_colunas_mes(req)
    meses = list(dict.fromkeys(meses_plan + meses_req))

    map_fr = {}
    if fr is not None:
        meses_fr, map_fr = detectar_colunas_mes(fr)
        meses = list(dict.fromkeys(meses + meses_fr))

    if not meses:
        raise ValueError("Nenhuma coluna de mês encontrada.")

    # Força numérico
    plan = garantir_numerico(plan, meses)
    req = garantir_numerico(req, meses)
    if fr is not None:
        fr = garantir_numerico(fr, meses)

    # Debug de cabeçalhos
    if show_debug:
        st.subheader("Diagnóstico PLAN")
        st.json(map_plan)
        st.subheader("Diagnóstico REQUEST")
        st.json(map_req)
        if fr is not None:
            st.subheader("Diagnóstico F.RESPONSE")
            st.json(map_fr)

    # =================================================
    # FILTROS
    # =================================================
    st.subheader("Filtros")

    def filtro_mult(df, col):
        if df is None or col not in df.columns:
            return None
        vals = sorted(df[col].dropna().unique())
        return st.multiselect(col, vals, default=vals)

    # Base para lista de filtros: união de abas para não "sumir" opções
    frames = [plan, req]
    if fr is not None:
        frames.append(fr)
    union_df = pd.concat(frames, ignore_index=True, sort=False)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        f_brand = filtro_mult(union_df, "PRODUCT BRAND")
    with c2:
        f_market = filtro_mult(union_df, "PRODUCT MARKET")
    with c3:
        f_site = filtro_mult(union_df, "SITE")
    with c4:
        f_need = filtro_mult(union_df, "PRODUCT NEED")

    def aplicar_filtros(df):
        if df is None:
            return None
        if f_brand is not None and "PRODUCT BRAND" in df.columns:
            df = df[df["PRODUCT BRAND"].isin(f_brand)]
        if f_market is not None and "PRODUCT MARKET" in df.columns:
            df = df[df["PRODUCT MARKET"].isin(f_market)]
        if f_site is not None and "SITE" in df.columns:
            df = df[df["SITE"].isin(f_site)]
        if f_need is not None and "PRODUCT NEED" in df.columns:
            df = df[df["PRODUCT NEED"].isin(f_need)]
        return df

    plan = aplicar_filtros(plan)
    req = aplicar_filtros(req)
    fr = aplicar_filtros(fr)

    # =================================================
    # Seleção base/comp conforme visão
    # =================================================
    if visao == "F.Response - Request":
        base_name, comp_name = "REQUEST", "F.RESPONSE"
        base_df, comp_df = req, fr
    else:
        base_name, comp_name = "PLAN", "REQUEST"
        base_df, comp_df = plan, req

    how_merge = "outer" if incluir_outer else "inner"

    # =================================================
    # TABELA 1 — PRODUCT NEED (COMP - BASE)
    # =================================================
    grp_need = ["SITE", "PRODUCT NEED"]

    base_n = base_df[grp_need + meses].groupby(grp_need, dropna=False)[meses].sum().reset_index()
    comp_n = comp_df[grp_need + meses].groupby(grp_need, dropna=False)[meses].sum().reset_index()

    comp_need_merge = pd.merge(
        base_n, comp_n,
        on=grp_need,
        how=how_merge,
        suffixes=(f"_{base_name}", f"_{comp_name}")
    ).fillna(0)

    for m in meses:
        comp_need_merge[m] = comp_need_merge[f"{m}_{comp_name}"] - comp_need_merge[f"{m}_{base_name}"]

    step1_need = comp_need_merge[grp_need + meses].copy()
    step1_need["TOTAL"] = step1_need[meses].sum(axis=1)

    total_n = {c: "TOTAL GERAL" for c in grp_need}
    for m in meses:
        total_n[m] = step1_need[m].sum()
    total_n["TOTAL"] = step1_need["TOTAL"].sum()

    step1_need = pd.concat([step1_need, pd.DataFrame([total_n])], ignore_index=True)

    # =================================================
    # TABELA EXTRA — PRODUCT NEED (SOMENTE COMP)
    # (no original era somente REQUEST; agora generalizado)
    # =================================================
    comp_only_need = (
        comp_df[grp_need + meses]
        .groupby(grp_need, dropna=False)[meses]
        .sum()
        .reset_index()
    )
    comp_only_need["TOTAL"] = comp_only_need[meses].sum(axis=1)

    total_comp = {c: "TOTAL GERAL" for c in grp_need}
    for m in meses:
        total_comp[m] = comp_only_need[m].sum()
    total_comp["TOTAL"] = comp_only_need["TOTAL"].sum()

    comp_only_need = pd.concat([comp_only_need, pd.DataFrame([total_comp])], ignore_index=True)

    # =================================================
    # TABELA 2 — ORDEM SOLICITADA (COMP - BASE)
    # =================================================
    grp_serie = [
        "SITE",
        "PRODUCT NEED",
        "PRODUCT SERIES",
        "PRODUCT BRAND",
        "PRODUCT MARKET",
    ]

    base_s = base_df[grp_serie + meses].groupby(grp_serie, dropna=False)[meses].sum().reset_index()
    comp_s = comp_df[grp_serie + meses].groupby(grp_serie, dropna=False)[meses].sum().reset_index()

    comp_s_merge = pd.merge(
        base_s, comp_s,
        on=grp_serie,
        how=how_merge,
        suffixes=(f"_{base_name}", f"_{comp_name}")
    ).fillna(0)

    for m in meses:
        comp_s_merge[m] = comp_s_merge[f"{m}_{comp_name}"] - comp_s_merge[f"{m}_{base_name}"]

    step1_serie = comp_s_merge[grp_serie + meses].copy()
    step1_serie["TOTAL"] = step1_serie[meses].sum(axis=1)

    total_s = {c: "TOTAL GERAL" for c in grp_serie}
    for m in meses:
        total_s[m] = step1_serie[m].sum()
    total_s["TOTAL"] = step1_serie["TOTAL"].sum()

    step1_serie = pd.concat([step1_serie, pd.DataFrame([total_s])], ignore_index=True)

    # =================================================
    # ADIÇÃO — PRODUCT · FC · DELTA MENSAL (COMP - BASE)
    # Mantém colunas meta (até o 1º mês) como no original
    # =================================================
    # Filtra FC no base e no comp (se a coluna existir)
    if "DEMAND TYPE" in base_df.columns:
        base_fc = base_df[base_df["DEMAND TYPE"] == "FC"]
    else:
        base_fc = base_df.iloc[0:0]

    if "DEMAND TYPE" in comp_df.columns:
        comp_fc = comp_df[comp_df["DEMAND TYPE"] == "FC"]
    else:
        comp_fc = comp_df.iloc[0:0]

    # Descobrir a posição do 1º mês em PLAN (mantém referência original) — fallback para base_df
    month_positions = [plan.columns.get_loc(c) for c in meses if c in plan.columns]
    if month_positions:
        first_month_pos = min(month_positions)
        meta_cols = list(plan.columns[:first_month_pos])
    else:
        # fallback: usa base_df
        month_positions_b = [base_df.columns.get_loc(c) for c in meses if c in base_df.columns]
        first_month_pos = min(month_positions_b) if month_positions_b else len(base_df.columns)
        meta_cols = list(base_df.columns[:first_month_pos])

    # Agregar por TODAS as colunas de metadados
    base_p = base_fc[meta_cols + meses].groupby(meta_cols, dropna=False)[meses].sum().reset_index()
    comp_p = comp_fc[meta_cols + meses].groupby(meta_cols, dropna=False)[meses].sum().reset_index()

    comp_p_merge = pd.merge(
        base_p, comp_p,
        on=meta_cols,
        how=how_merge,
        suffixes=(f"_{base_name}", f"_{comp_name}")
    ).fillna(0)

    step1_product_fc = comp_p_merge[meta_cols].copy()
    for m in meses:
        step1_product_fc[m] = comp_p_merge[f"{m}_{comp_name}"] - comp_p_merge[f"{m}_{base_name}"]
    step1_product_fc["TOTAL"] = step1_product_fc[meses].sum(axis=1)

    total_prod = {c: "TOTAL GERAL" for c in meta_cols}
    for m in meses:
        total_prod[m] = step1_product_fc[m].sum()
    total_prod["TOTAL"] = step1_product_fc["TOTAL"].sum()
    step1_product_fc = pd.concat([step1_product_fc, pd.DataFrame([total_prod])], ignore_index=True)

    # =================================================
    # EXPORTAR EXCEL (FORMATADO)
    # =================================================
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    buf_out = io.BytesIO()
    with pd.ExcelWriter(buf_out, engine="openpyxl") as writer:
        # Copia as abas originais
        for sheet in xls_original.sheet_names:
            pd.read_excel(xls_original, sheet).to_excel(writer, sheet_name=sheet, index=False)

        abas = {
            "Step1_Comparativo_Serie": step1_serie,
            "Step1_Comparativo_Need": step1_need,
            f"Resumo_{comp_name}_Product_Need": comp_only_need,
            f"{comp_name} x {base_name} FC - Produto Mensal": step1_product_fc,
        }

        for nome, df in abas.items():
            df.to_excel(writer, sheet_name=nome[:31], index=False)
            ws = writer.book[nome[:31]]

            cols_num = df.select_dtypes(include="number").columns
            idx_cols = [df.columns.get_loc(c) + 1 for c in cols_num]

            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                for idx in idx_cols:
                    cell = row[idx - 1]
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '#,##0'
                        if cell.value < 0:
                            cell.font = Font(color="FF0000", bold=True)
                        elif cell.value > 0:
                            cell.font = Font(color="008000", bold=True)

                if str(row[0].value).upper() == "TOTAL GERAL":
                    for cell in row:
                        cell.font = Font(bold=True)

            for col in ws.columns:
                max_len = 0
                for cell in col:
                    if cell.value is None:
                        continue
                    max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[get_column_letter(col[0].column)].width = max_len + 2

    return buf_out.getvalue(), step1_serie, step1_need, comp_only_need


# =====================================================
# UI
# =====================================================
uploaded = st.file_uploader("Envie o Excel (PLAN, REQUEST e opcionalmente F.RESPONSE)", type=["xlsx"])

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    visao = st.radio("Visão", ["Request - Plan", "F.Response - Request"], horizontal=True)
with col2:
    incluir_outer = st.checkbox(
        "Incluir todos (outer)",
        value=False,
        help="Desmarcado: apenas interseção (como no app original). Marcado: inclui combinações que existam só em um lado (ausentes tratados como 0)."
    )
with col3:
    debug = st.checkbox("Exibir diagnóstico", value=False)

if uploaded:
    try:
        excel_out, df_serie, df_need, df_comp_need = gerar_passo1(
            uploaded.read(),
            show_debug=debug,
            visao=visao,
            incluir_outer=incluir_outer,
        )

        st.subheader("Comparativo por PRODUCT NEED + PRODUCT SERIES")
        st.dataframe(formatar_tabela(df_serie), use_container_width=True)

        st.subheader("Resumo por PRODUCT NEED (COMP - BASE)")
        st.dataframe(formatar_tabela(df_need), use_container_width=True)

        st.subheader("Resumo por PRODUCT NEED (Somente COMP)")
        st.dataframe(formatar_tabela(df_comp_need), use_container_width=True)

        nome_saida = f"saida_step1_{visao.replace(' ', '_').replace('.', '')}_{'outer' if incluir_outer else 'inner'}.xlsx"
        st.download_button(
            "⬇️ Baixar Excel",
            data=excel_out,
            file_name=nome_saida
        )

    except Exception as e:
        st.error("Erro ao processar o arquivo")
        st.exception(e)
else:
    st.info("Faça upload do Excel para iniciar.")
