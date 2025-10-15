# app.py — Mati • Catálogo com galeria e ficha ao clicar
# Execução local: streamlit run app.py
import os, json, datetime as dt
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Mati — Catálogo", layout="wide")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
FILES = {
    "catalog":   os.path.join(DATA_DIR, "catalog.json"),
    "materiais": os.path.join(DATA_DIR, "materiais.json"),
    "receitas":  os.path.join(DATA_DIR, "receitas.json"),
}

# ---------- helpers de persistência ----------
def _read_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    except:
        return pd.DataFrame()

def _write_json(p, df: pd.DataFrame):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(df.replace({np.nan: None}).to_dict(orient="records"),
                  f, ensure_ascii=False, indent=2)

def load_state():
    st.session_state.catalog   = _read_json(FILES["catalog"])
    st.session_state.materiais = _read_json(FILES["materiais"])
    st.session_state.receitas  = _read_json(FILES["receitas"])

if "catalog" not in st.session_state:
    load_state()

# ---------- import automático 1x do Excel (se existir no repo) ----------
def import_from_excel_once():
    flag = os.path.join(DATA_DIR, ".import_done_gallery")
    if os.path.exists(flag): return
    excel = None
    for cand in ["Mati_Arte_Aroma_Financas.xlsx", "Mati_Catalogo_Simples.xlsx"]:
        if os.path.exists(cand):
            excel = cand; break
    if not excel: return
    try:
        xls = pd.ExcelFile(excel)

        # Materiais
        if "Materiais" in xls.sheet_names:
            st.session_state.materiais = pd.read_excel(excel, sheet_name="Materiais").fillna("")

        # Receitas/BOM
        sheet_rec = "Receitas" if "Receitas" in xls.sheet_names else None
        if sheet_rec:
            st.session_state.receitas = pd.read_excel(excel, sheet_name=sheet_rec).fillna("")

        # Catálogo / Peças
        sheet_cat = None
        for s in ["Catalogo", "Catalogo Simples", "Pecas"]:
            if s in xls.sheet_names: sheet_cat = s; break
        if sheet_cat:
            df = pd.read_excel(excel, sheet_name=sheet_cat).fillna("")
            # normaliza campos esperados
            st.session_state.catalog = pd.DataFrame({
                "Produto_ID": df.get("Produto_ID", df.get("Peca_ID", pd.Series(dtype=str))),
                "Produto":    df.get("Produto", df.get("Peca", pd.Series(dtype=str))),
                "Preco_Venda_€": df.get("Preco_Venda_€", pd.Series(dtype=float)),
                "Imagem_Path": df.get("Imagem_Path", pd.Series(dtype=str)),
                "Categoria":  df.get("Categoria", pd.Series(dtype=str)),
                "Dimensoes":  df.get("Dimensoes", pd.Series(dtype=str)),
            }).fillna("")
        # guarda
        _write_json(FILES["catalog"], st.session_state.catalog)
        _write_json(FILES["materiais"], st.session_state.materiais)
        _write_json(FILES["receitas"], st.session_state.receitas)
        open(flag, "w").close()
        st.toast("Importei dados do Excel.", icon="✅")
    except Exception as e:
        st.toast(f"Import falhou: {e}", icon="⚠️")

import_from_excel_once()

# ---------- preço unitário por material ----------
def unit_price_row(mrow, unidade):
    """devolve preço por g / mL / unidade com fallback a partir de Preco_UnidBase_€."""
    if mrow is None: return 0.0
    u = (unidade or "").lower()
    ubase = str(mrow.get("Unidade_Base") or "").lower()
    pbase = float(mrow.get("Preco_UnidBase_€") or 0)
    pg = mrow.get("Preco_por_g_€"); pml = mrow.get("Preco_por_mL_€"); pun = mrow.get("Preco_por_unidade_€")

    if pg in ("", None):
        if ubase == "kg": pg = pbase/1000.0
        elif ubase == "g": pg = pbase
    if pml in ("", None):
        if ubase in ("l","litro","liter"): pml = pbase/1000.0
        elif ubase == "ml": pml = pbase
    if pun in ("", None):
        if ubase in ("unidade","un"): pun = pbase

    if u == "g": return float(pg or 0)
    if u == "ml": return float(pml or 0)
    if u in ("un","unidade"): return float(pun or 0)
    return 0.0

def get_material_row(codigo):
    cid = str(codigo or "").strip().lower()
    if st.session_state.materiais.empty: return None
    for _, r in st.session_state.materiais.iterrows():
        for k in ["Codigo","Material_ID","Material","Descricao"]:
            if str(r.get(k, "")).strip().lower() == cid:
                return r
    return None

# ---------- custo por peça (materiais + sem overhead nesta versão) ----------
def bom_for(pid):
    if st.session_state.receitas.empty: return pd.DataFrame(columns=["Codigo_Material","Unidade","Quantidade"])
    df = st.session_state.receitas.copy()
    # aceita Peca_ID ou Produto_ID
    df = df[(df["Peca_ID"].astype(str) == str(pid)) | (df.get("Produto_ID","").astype(str) == str(pid))]
    keep = ["Codigo_Material","Material","Unidade","Quantidade","Perdas_%","Quantidade_Ajustada"]
    for k in keep:
        if k not in df.columns: df[k] = ""
    df["Codigo"] = df["Codigo_Material"].replace("", np.nan).fillna(df["Material"])
    df["Qtd_Final"] = pd.to_numeric(df["Quantidade_Ajustada"], errors="coerce").fillna(pd.to_numeric(df["Quantidade"], errors="coerce")).fillna(0)
    return df[["Codigo","Unidade","Qtd_Final"]].reset_index(drop=True)

def cost_for(pid):
    bom = bom_for(pid)
    total = 0.0
    linhas = []
    for _, row in bom.iterrows():
        mrow = get_material_row(row["Codigo"])
        pu = unit_price_row(mrow, str(row["Unidade"]).lower())
        subtotal = float(row["Qtd_Final"] or 0) * pu
        total += subtotal
        linhas.append({
            "Material": row["Codigo"],
            "Unidade":  row["Unidade"],
            "Quantidade": float(row["Qtd_Final"] or 0),
            "Preço/unid": round(pu, 4),
            "Subtotal €": round(subtotal, 4)
        })
    return round(total, 4), pd.DataFrame(linhas)

# ---------- UI ----------
st.markdown("## 🛍️ Catálogo (clique na foto para ver custos, PV e materiais)")
st.caption("Os dados são carregados do Excel (uma vez) e guardados em `data/`.")

# Filtro rápido
colf1, colf2, colf3 = st.columns([2,2,1])
with colf1:
    q = st.text_input("Pesquisar", "")
with colf2:
    cat = st.text_input("Categoria (opcional)", "")

catdf = st.session_state.catalog.copy()
if q:
    mask = catdf["Produto"].str.contains(q, case=False, na=False) | catdf["Produto_ID"].astype(str).str.contains(q, case=False, na=False)
    catdf = catdf[mask]
if cat:
    catdf = catdf[catdf["Categoria"].astype(str).str.contains(cat, case=False, na=False)]

if catdf.empty:
    st.info("Sem itens para mostrar. Confirma se o Excel foi importado.")
    st.stop()

# Galeria responsiva
cols_per_row = 4 if st.session_state.get("_is_desktop", True) else 2
cols = st.columns(cols_per_row)

if "selected_pid" not in st.session_state:
    st.session_state.selected_pid = None

for i, (_, r) in enumerate(catdf.iterrows()):
    c = cols[i % cols_per_row]
    with c:
        # imagem (pode ser caminho local no repo ou URL)
        img_path = r.get("Imagem_Path", "")
        if str(img_path).startswith("http"):
            st.image(img_path, use_column_width=True)
        elif img_path and os.path.exists(img_path):
            st.image(img_path, use_column_width=True)
        else:
            st.image("https://static.streamlit.io/examples/dice.jpg", use_column_width=True)  # placeholder
        st.markdown(f"**{r.get('Produto','')}**")
        if st.button("Ver detalhes", key=f"btn_{r.get('Produto_ID','')}_{i}"):
            st.session_state.selected_pid = r.get("Produto_ID", "")

st.write("---")

# Painel de detalhes
pid = st.session_state.selected_pid
if pid:
    sel = catdf[catdf["Produto_ID"].astype(str) == str(pid)].head(1)
    if not sel.empty:
        nome = sel["Produto"].values[0]
        pv = float(sel.get("Preco_Venda_€", pd.Series([0])).values[0] or 0)
        custo, bom = cost_for(pid)
        margem = pv - custo
        st.markdown(f"### 📌 {nome}  \nID: `{pid}`")
        m1,m2,m3 = st.columns(3)
        m1.metric("Preço de custo", f"{custo:.2f} €")
        m2.metric("Preço de venda", f"{pv:.2f} €")
        m3.metric("Margem (estimada)", f"{margem:.2f} €")
        st.markdown("**Materiais necessários (BOM):**")
        st.dataframe(bom, use_container_width=True, hide_index=True)
    else:
        st.info("Seleção inválida.")

st.write("---")
with st.sidebar:
    if st.button("💾 Guardar agora"):
        _write_json(FILES["catalog"], st.session_state.catalog)
        _write_json(FILES["materiais"], st.session_state.materiais)
        _write_json(FILES["receitas"], st.session_state.receitas)
        st.success("Guardado!")
