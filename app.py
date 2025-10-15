# app.py — Mati (browser) • Catálogo + Compras + Vendas • mobile‑friendly
# Execução local:   streamlit run app.py
# Aceder no iPhone: usar o URL de rede (ex.: http://192.168.X.X:8501) que o Streamlit mostra
# Login simples: defina APP_PASSWORD num .env ou no ambiente (opcional)
import os, json, datetime as dt
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from PIL import Image

st.set_page_config(page_title="Mati — Gestão", layout="wide")

# ---------- Auth (opcional) ----------
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
if APP_PASSWORD:
    with st.sidebar:
        st.subheader("🔒 Login")
        pw = st.text_input("Palavra‑passe", type="password")
        if pw != APP_PASSWORD:
            st.stop()
        st.success("Sessão iniciada.")

# ---------- Paths & persistence ----------
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
FILES = {
    "catalog": os.path.join(DATA_DIR, "catalog.json"),
    "materials": os.path.join(DATA_DIR, "materials.json"),
    "suppliers": os.path.join(DATA_DIR, "suppliers.json"),
    "purchases": os.path.join(DATA_DIR, "purchases.json"),
    "sales": os.path.join(DATA_DIR, "sales.json"),
}

def _read_json(p): 
    try:
        with open(p, "r", encoding="utf-8") as f: 
            return pd.DataFrame(json.load(f))
    except: 
        return pd.DataFrame()

def _write_json(p, df: pd.DataFrame):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(df.replace({np.nan: None}).to_dict(orient="records"), f, ensure_ascii=False, indent=2)

def load_state():
    st.session_state.catalog   = _read_json(FILES["catalog"])
    st.session_state.materials = _read_json(FILES["materials"])
    st.session_state.suppliers = _read_json(FILES["suppliers"])
    st.session_state.purchases = _read_json(FILES["purchases"])
    st.session_state.sales     = _read_json(FILES["sales"])

def save_state():
    _write_json(FILES["catalog"],   st.session_state.catalog)
    _write_json(FILES["materials"], st.session_state.materials)
    _write_json(FILES["suppliers"], st.session_state.suppliers)
    _write_json(FILES["purchases"], st.session_state.purchases)
    _write_json(FILES["sales"],     st.session_state.sales)

if "catalog" not in st.session_state:
    load_state()

# ---------- One‑time import from Excel (auto, se existir na mesma pasta) ----------
def try_auto_import_once():
    flag = os.path.join(DATA_DIR, ".import_done")
    if os.path.exists(flag): 
        return
    candidates = ["Mati_Catalogo_Simples.xlsx", "Mati_Arte_Aroma_Financas.xlsx"]
    excel = None
    for c in candidates:
        if os.path.exists(c):
            excel = c; break
    if not excel:
        return
    try:
        xls = pd.ExcelFile(excel)
        if "Catalogo Simples" in xls.sheet_names:
            df = pd.read_excel(excel, sheet_name="Catalogo Simples")
            # map para o nosso formato
            out = pd.DataFrame({
                "Produto_ID": df.get("Produto_ID", df.get("Peca_ID", pd.Series(dtype=str))),
                "Produto": df.get("Produto", df.get("Peca", pd.Series(dtype=str))),
                "Material": df.get("Material", pd.Series(dtype=str)),
                "Quantidade": df.get("Quantidade", pd.Series(dtype=float)),
                "Unidade": df.get("Unidade", pd.Series(dtype=str)),
                "Tipo_Preco": df.get("Tipo_Preco", pd.Series(dtype=str)),
                "Preco_Base_€": df.get("Preco_Base_€", pd.Series(dtype=float)),
                "Custo_Total_€": df.get("Custo_Total_€", pd.Series(dtype=float)),
                "Preco_Venda_€": df.get("Preco_Venda_€", pd.Series(dtype=float)),
                "Imagem_Path": df.get("Imagem_Path", pd.Series(dtype=str)),
            })
            st.session_state.catalog = out.fillna("")
        # Tentativa básica para Materiais
        if "Materiais" in xls.sheet_names:
            st.session_state.materials = pd.read_excel(excel, sheet_name="Materiais").fillna("")
        save_state()
        open(flag, "w").close()
        st.toast("Importei os dados do Excel uma única vez.", icon="✅")
    except Exception as e:
        st.toast(f"Import automático falhou: {e}", icon="⚠️")

try_auto_import_once()

# ---------- Helpers ----------
UNITS = ["g", "mL", "unidade"]
PRICE_TYPES = ["€/kg", "€/L", "€/unidade"]

def compute_cost(q, tipo, preco_base):
    try:
        q = float(q or 0); p = float(preco_base or 0)
    except:
        return np.nan
    if tipo in ("€/kg","€/L"): return (q/1000.0) * p
    if tipo == "€/unidade": return q * p
    return np.nan

# ---------- Sidebar (mobile friendly) ----------
with st.sidebar:
    st.markdown("## Mati — Gestão")
    st.caption("Catálogo • Materiais • Compras • Vendas • Relatórios")
    st.write("---")
    st.write("📥 **Guarda tudo automaticamente** em `data/`.")
    if st.button("💾 Guardar agora"):
        save_state()
        st.success("Guardado!")

# ---------- Tabs ----------
tabs = st.tabs(["🛍️ Catálogo", "🏭 Materiais", "🤝 Fornecedores", "🧾 Compras", "🛒 Vendas", "📈 Relatórios"])

# ---- Catálogo ----
with tabs[0]:
    st.subheader("Catálogo")
    with st.form("cat_add", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            pid = st.text_input("Produto_ID")
            prod = st.text_input("Produto")
            mat = st.text_input("Material")
            qtd = st.number_input("Quantidade", min_value=0.0, step=1.0)
            uni = st.selectbox("Unidade", UNITS, index=0, key="uni_cat")
        with c2:
            tp  = st.selectbox("Tipo de Preço", PRICE_TYPES, index=0, key="tp_cat")
            pb  = st.number_input("Preço Base (€)", min_value=0.0, step=0.10)
            custo = compute_cost(qtd, tp, pb)
            pv  = st.number_input("Preço de Venda (€)", min_value=0.0, step=0.10)
            img = st.text_input("Imagem_Path (opcional)")
        st.caption(f"Custo total estimado: **{(0 if np.isnan(custo) else custo):.2f} €**")
        submitted = st.form_submit_button("Adicionar / Atualizar")
    if submitted:
        df = st.session_state.catalog.copy()
        row = {"Produto_ID": pid or prod, "Produto": prod or pid, "Material": mat, "Quantidade": qtd, "Unidade": uni, "Tipo_Preco": tp, "Preco_Base_€": pb, "Custo_Total_€": round(0 if np.isnan(custo) else float(custo), 4), "Preco_Venda_€": pv, "Imagem_Path": img}
        if not df.empty and (df["Produto_ID"] == row["Produto_ID"]).any():
            st.session_state.catalog.loc[df["Produto_ID"] == row["Produto_ID"], :] = row
        else:
            st.session_state.catalog = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        st.success("Guardado no catálogo.")
        save_state()

    st.dataframe(st.session_state.catalog, use_container_width=True)

# ---- Materiais ----
with tabs[1]:
    st.subheader("Materiais")
    with st.form("mat_add", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        with c1:
            mid = st.text_input("Material_ID")
            desc= st.text_input("Descrição")
        with c2:
            ubase = st.selectbox("Unidade base", ["kg","L","unidade","g","mL"], index=0)
            pbase = st.number_input("Preço base (€ por unidade base)", min_value=0.0, step=0.10)
        with c3:
            fornecedor = st.text_input("Fornecedor_ID (opcional)")
            preco_g  = st.number_input("Preço por g (opcional)", min_value=0.0, step=0.001, format="%.3f")
            preco_ml = st.number_input("Preço por mL (opcional)", min_value=0.0, step=0.001, format="%.3f")
            preco_un = st.number_input("Preço por unidade (opcional)", min_value=0.0, step=0.01)
        ok = st.form_submit_button("Adicionar / Atualizar")
    if ok:
        df = st.session_state.materials.copy()
        row = {"Material_ID": mid or desc, "Descricao": desc or mid, "Unidade_Base": ubase, "Preco_UnidBase_€": pbase, "Fornecedor_ID": fornecedor, "Preco_por_g_€": preco_g or None, "Preco_por_mL_€": preco_ml or None, "Preco_por_unidade_€": preco_un or None}
        if not df.empty and (df["Material_ID"] == row["Material_ID"]).any():
            st.session_state.materials.loc[df["Material_ID"] == row["Material_ID"], :] = row
        else:
            st.session_state.materials = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        st.success("Material guardado.")
        save_state()
    st.dataframe(st.session_state.materials, use_container_width=True)

# ---- Fornecedores ----
with tabs[2]:
    st.subheader("Fornecedores")
    with st.form("sup_add", clear_on_submit=True):
        fid = st.text_input("Fornecedor_ID")
        nome = st.text_input("Nome")
        contacto = st.text_input("Contacto")
        notas = st.text_area("Notas")
        ok = st.form_submit_button("Guardar fornecedor")
    if ok:
        df = st.session_state.suppliers.copy()
        row = {"Fornecedor_ID": fid or nome, "Nome": nome or fid, "Contacto": contacto, "Notas": notas}
        if not df.empty and (df["Fornecedor_ID"] == row["Fornecedor_ID"]).any():
            st.session_state.suppliers.loc[df["Fornecedor_ID"] == row["Fornecedor_ID"], :] = row
        else:
            st.session_state.suppliers = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        st.success("Fornecedor guardado.")
        save_state()
    st.dataframe(st.session_state.suppliers, use_container_width=True)

# ---- Compras (atualiza stock e custo médio simples) ----
with tabs[3]:
    st.subheader("Compras de Materiais")
    c1,c2,c3 = st.columns(3)
    with c1:
        data = st.date_input("Data", value=dt.date.today())
        mat_id = st.text_input("Material_ID")
        qtd = st.number_input("Quantidade", min_value=0.0, step=1.0)
    with c2:
        unidade = st.selectbox("Unidade", ["g","mL","unidade"], index=0)
        preco_unit = st.number_input("Preço unitário (€)", min_value=0.0, step=0.10)
        total = qtd * preco_unit
        st.metric("Total compra (€)", f"{total:.2f}")
    with c3:
        fornecedor = st.text_input("Fornecedor_ID")
        if st.button("Registar compra"):
            df = st.session_state.purchases
            row = {"Data": str(data), "Material_ID": mat_id, "Quantidade": qtd, "Unidade": unidade, "Preco_Unit_€": preco_unit, "Total_€": total, "Fornecedor_ID": fornecedor}
            st.session_state.purchases = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            st.success("Compra registada.")
            save_state()
    st.dataframe(st.session_state.purchases, use_container_width=True)

# ---- Vendas ----
with tabs[4]:
    st.subheader("Vendas")
    c1,c2 = st.columns(2)
    with c1:
        d = st.date_input("Data", value=dt.date.today(), key="vd")
        prod_id = st.text_input("Produto_ID")
        qv = st.number_input("Quantidade", min_value=0.0, step=1.0, key="vq")
    with c2:
        # lookup PV
        df = st.session_state.catalog
        pv_default = float(df[df["Produto_ID"]==prod_id]["Preco_Venda_€"].head(1).values[0]) if not df.empty and (df["Produto_ID"]==prod_id).any() else 0.0
        pv = st.number_input("Preço de Venda (€)", min_value=0.0, step=0.10, value=pv_default)
        total = qv * pv
        st.metric("Total venda (€)", f"{total:.2f}")
    if st.button("Registar venda"):
        df = st.session_state.sales
        # custo unitário simplificado: usar custo total do catálogo
        cu = float(st.session_state.catalog[st.session_state.catalog["Produto_ID"]==prod_id]["Custo_Total_€"].head(1).values[0]) if not st.session_state.catalog.empty and (st.session_state.catalog["Produto_ID"]==prod_id).any() else 0.0
        row = {"Data": str(d), "Produto_ID": prod_id, "Quantidade": qv, "Preco_Venda_€": pv, "Total_€": total, "Custo_Unit_€": cu, "Lucro_€": total - cu*qv}
        st.session_state.sales = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        st.success("Venda registada.")
        save_state()
    st.dataframe(st.session_state.sales, use_container_width=True)

# ---- Relatórios ----
with tabs[5]:
    st.subheader("Relatórios")
    total_gasto = float(st.session_state.purchases["Total_€"].sum()) if not st.session_state.purchases.empty else 0.0
    total_receita = float(st.session_state.sales["Total_€"].sum()) if not st.session_state.sales.empty else 0.0
    total_lucro = float(st.session_state.sales["Lucro_€"].sum()) if not st.session_state.sales.empty else 0.0
    c1,c2,c3 = st.columns(3)
    c1.metric("Total gasto", f"{total_gasto:.2f} €")
    c2.metric("Receita", f"{total_receita:.2f} €")
    c3.metric("Lucro (bruto)", f"{total_lucro:.2f} €")
    st.caption("Dica: partilha o URL de rede neste Wi‑Fi para veres no iPhone.")

st.write("---")
st.caption("Mati • Streamlit • Mobile‑friendly")
