import streamlit as st
import pandas as pd
import altair as alt
import re
from pathlib import Path

st.set_page_config(
    page_title="Top Selling Products Visualizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Top Selling Products Data Visualizer")
st.caption("Upload your Key Findings CSVs and explore them interactively with filters, tables, and charts.")

# -----------------------------
# Helper Functions
# -----------------------------
def parse_price_range(price_str):
    """Extract numeric low and high from price range strings like '$10 - $50 per bottle'"""
    if pd.isna(price_str):
        return None, None
    matches = re.findall(r'\$?(\d+(?:\.\d+)?)', str(price_str))
    if len(matches) >= 2:
        return float(matches[0]), float(matches[1])
    elif len(matches) == 1:
        val = float(matches[0])
        return val, val
    return None, None

def clean_dataset_name(filename):
    name = Path(filename).stem
    for suffix in ["_key_findings_20260614", "_key_findings_2016_to_2026", "_structured_20260614"]:
        name = name.replace(suffix, "")
    name = name.replace("top_", "").replace("_", " ").title()
    return name.strip()

# -----------------------------
# Session State
# -----------------------------
if "datasets" not in st.session_state:
    st.session_state.datasets = {}

# -----------------------------
# Sidebar - Upload Focused (Cloud Friendly)
# -----------------------------
with st.sidebar:
    st.header("📁 Upload Your Data")
    
    st.markdown("**Upload one or more Key Findings CSVs**")
    uploaded_files = st.file_uploader(
        "Drop your CSV files here",
        type=["csv"],
        accept_multiple_files=True,
        help="You can upload multiple files at once. They will be available for the rest of this session."
    )
    
    if uploaded_files:
        for uf in uploaded_files:
            try:
                df = pd.read_csv(uf)
                display_name = clean_dataset_name(uf.name)
                st.session_state.datasets[display_name] = df
                st.success(f"✅ Loaded: **{display_name}** ({len(df)} rows)")
            except Exception as e:
                st.error(f"Failed to load {uf.name}: {e}")
    
    st.divider()
    
    # Dataset selector
    st.subheader("Select Dataset")
    dataset_names = sorted(list(st.session_state.datasets.keys()))
    
    if dataset_names:
        selected_name = st.selectbox(
            "Choose a dataset to explore",
            options=dataset_names,
            key="dataset_selector"
        )
    else:
        selected_name = None
        st.info("👆 Upload your Key Findings CSVs above to get started.")

# -----------------------------
# Main Content
# -----------------------------
if selected_name and selected_name in st.session_state.datasets:
    df = st.session_state.datasets[selected_name].copy()
    
    st.header(f"📋 {selected_name}")
    st.caption(f"{len(df)} items • {df['Category'].nunique() if 'Category' in df.columns else 'N/A'} categories")
    
    # Quick Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", len(df))
    with col2:
        st.metric("Categories", df["Category"].nunique() if "Category" in df.columns else "—")
    with col3:
        if "Current_Price_Range_USD" in df.columns:
            lows, highs = zip(*df["Current_Price_Range_USD"].apply(parse_price_range))
            valid = [l for l in lows if l is not None]
            if valid:
                st.metric("Price Range", f"${min(valid):.0f} – ${max([h for h in highs if h is not None]):.0f}")
            else:
                st.metric("Price Range", "—")
        else:
            st.metric("Price Info", "—")
    with col4:
        if "Brand_Examples" in df.columns:
            brands = set()
            for b in df["Brand_Examples"].dropna():
                for brand in str(b).split(" / "):
                    brands.add(brand.strip())
            st.metric("Brands (approx)", len(brands))
        else:
            st.metric("Brands", "—")
    
    st.divider()
    
    # Filters
    with st.expander("🔍 Filters & Search", expanded=True):
        filtered_df = df.copy()
        
        if "Category" in df.columns:
            cats = st.multiselect(
                "Filter by Category",
                options=sorted(df["Category"].dropna().unique()),
                default=sorted(df["Category"].dropna().unique())
            )
            filtered_df = filtered_df[filtered_df["Category"].isin(cats)]
        
        search = st.text_input("Search across Item Type, Brand, Features, or Best For")
        if search:
            mask = pd.Series(False, index=filtered_df.index)
            for col in ["Item_Type", "Brand_Examples", "Key_Features", "Best_For"]:
                if col in filtered_df.columns:
                    mask = mask | filtered_df[col].astype(str).str.contains(search, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    # Data Table
    st.subheader("📄 Data Table")
    st.dataframe(filtered_df, use_container_width=True, height=400, hide_index=True)
    
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Filtered Data as CSV",
        data=csv,
        file_name=f"{selected_name}_filtered.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.divider()
    
    # Visualizations
    st.subheader("📈 Visualizations")
    tab1, tab2, tab3 = st.tabs(["Category Distribution", "Price Analysis", "Brand Overview"])
    
    with tab1:
        if "Category" in filtered_df.columns and len(filtered_df) > 0:
            cat_counts = filtered_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            chart = alt.Chart(cat_counts).mark_bar().encode(
                x="Count:Q",
                y=alt.Y("Category:N", sort="-x"),
                color="Count:Q",
                tooltip=["Category", "Count"]
            ).properties(title="Items per Category", height=380)
            st.altair_chart(chart, use_container_width=True)
    
    with tab2:
        if "Current_Price_Range_USD" in filtered_df.columns and len(filtered_df) > 0:
            price_data = filtered_df.copy()
            price_data[["Price_Low", "Price_High"]] = price_data["Current_Price_Range_USD"].apply(
                lambda x: pd.Series(parse_price_range(x))
            ).dropna(subset=["Price_Low"])
            if len(price_data) > 0:
                avg = price_data.groupby("Category")["Price_Low"].mean().reset_index()
                avg.columns = ["Category", "Avg Low Price"]
                chart = alt.Chart(avg).mark_bar().encode(
                    x="Avg Low Price:Q",
                    y=alt.Y("Category:N", sort="-x"),
                    color="Avg Low Price:Q",
                    tooltip=["Category", "Avg Low Price"]
                ).properties(title="Average Lowest Price by Category", height=350)
                st.altair_chart(chart, use_container_width=True)
                st.caption("Prices are parsed from range strings (e.g. '$10 - $50').")
    
    with tab3:
        if "Brand_Examples" in filtered_df.columns and len(filtered_df) > 0:
            brand_list = []
            for b in filtered_df["Brand_Examples"].dropna():
                for brand in str(b).split(" / "):
                    brand_list.append(brand.strip())
            if brand_list:
                brand_df = pd.Series(brand_list).value_counts().head(12).reset_index()
                brand_df.columns = ["Brand", "Mentions"]
                chart = alt.Chart(brand_df).mark_bar().encode(
                    x="Mentions:Q",
                    y=alt.Y("Brand:N", sort="-x"),
                    color="Mentions:Q",
                    tooltip=["Brand", "Mentions"]
                ).properties(title="Top Mentioned Brands", height=380)
                st.altair_chart(chart, use_container_width=True)

else:
    # Welcome screen for Cloud
    st.info("👆 **Upload your Key Findings CSVs** in the sidebar to begin.")
    
    st.markdown("""
    ### How to use this tool on Streamlit Cloud
    1. In the sidebar, click **Browse files** and upload one or more of your Key Findings CSVs.
    2. Once uploaded, select a dataset from the dropdown.
    3. Use the filters, explore the interactive table, and view the visualizations.
    4. Download filtered data as CSV anytime.
    
    This app works great with all the top-selling product datasets you've created.
    """)
    
    with st.expander("Supported CSV Format"):
        st.markdown("""
        Works best with your standard **Key Findings** CSVs containing columns like:
        `Category`, `Item_Type`, `Brand_Examples`, `Current_Price_Range_USD`, `Key_Features`, `Best_For`
        """)
