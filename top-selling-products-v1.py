import streamlit as st
import pandas as pd
import altair as alt
import re
from pathlib import Path
from io import StringIO

st.set_page_config(
    page_title="Top Selling Products Visualizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Top Selling Products Data Visualizer")
st.caption("Interactive explorer for your Key Findings CSVs — upload new ones or load existing datasets from your ecom-collections folder.")

# -----------------------------
# Helper Functions
# -----------------------------
def parse_price_range(price_str):
    """Extract numeric low and high from price range strings like '$10 - $50 per bottle'"""
    if pd.isna(price_str):
        return None, None
    matches = re.findall(r'\$?(\d+(?:\.\d+)?)', str(price_str))
    if len(matches) >= 2:
        low = float(matches[0])
        high = float(matches[1])
        return low, high
    elif len(matches) == 1:
        val = float(matches[0])
        return val, val
    return None, None

def clean_dataset_name(filename):
    """Create a nice display name from filename"""
    name = Path(filename).stem
    # Remove common suffixes
    for suffix in ["_key_findings_20260614", "_key_findings_2016_to_2026", "_structured_20260614"]:
        name = name.replace(suffix, "")
    name = name.replace("top_", "").replace("_", " ").title()
    return name.strip()

def load_from_artifacts():
    """Load all key findings CSVs from the standard artifacts location"""
    data_dir = Path("/home/workdir/artifacts/ecom-collections")
    if not data_dir.exists():
        st.error("Artifacts folder not found. Please upload files manually or adjust the path.")
        return {}
    
    files = list(data_dir.glob("*key_findings*.csv")) + list(data_dir.glob("*structured*.csv"))
    datasets = {}
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            display_name = clean_dataset_name(f.name)
            datasets[display_name] = df
        except Exception as e:
            st.warning(f"Could not load {f.name}: {e}")
    return datasets

# -----------------------------
# Session State Initialization
# -----------------------------
if "datasets" not in st.session_state:
    st.session_state.datasets = {}

if "active_dataset" not in st.session_state:
    st.session_state.active_dataset = None

# -----------------------------
# Sidebar - Data Management
# -----------------------------
with st.sidebar:
    st.header("📁 Data Management")
    
    # Load from artifacts button
    if st.button("🔄 Load All from Artifacts Folder", use_container_width=True):
        with st.spinner("Loading datasets..."):
            loaded = load_from_artifacts()
            if loaded:
                st.session_state.datasets.update(loaded)
                st.success(f"Loaded {len(loaded)} datasets!")
            else:
                st.info("No datasets found in artifacts folder.")
    
    st.divider()
    
    # File uploader for new/additional CSVs
    st.subheader("Upload New CSVs")
    uploaded_files = st.file_uploader(
        "Upload one or more Key Findings CSVs",
        type=["csv"],
        accept_multiple_files=True,
        help="Files will be added to the available datasets for this session."
    )
    
    if uploaded_files:
        for uf in uploaded_files:
            try:
                df = pd.read_csv(uf)
                display_name = clean_dataset_name(uf.name)
                st.session_state.datasets[display_name] = df
                st.success(f"✅ Loaded: {display_name} ({len(df)} rows)")
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
            index=0 if st.session_state.active_dataset is None else dataset_names.index(st.session_state.active_dataset) if st.session_state.active_dataset in dataset_names else 0,
            key="dataset_selector"
        )
        st.session_state.active_dataset = selected_name
    else:
        st.info("No datasets loaded yet. Use the buttons above to load or upload data.")
        selected_name = None

# -----------------------------
# Main Content
# -----------------------------
if selected_name and selected_name in st.session_state.datasets:
    df = st.session_state.datasets[selected_name].copy()
    
    # Header
    st.header(f"📋 {selected_name}")
    st.caption(f"Source: {len(df)} items  •  {df['Category'].nunique() if 'Category' in df.columns else 'N/A'} categories")
    
    # -----------------------------
    # Quick Metrics Row
    # -----------------------------
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Items", len(df))
    
    with col2:
        if "Category" in df.columns:
            st.metric("Categories", df["Category"].nunique())
        else:
            st.metric("Categories", "—")
    
    with col3:
        if "Current_Price_Range_USD" in df.columns:
            lows, highs = zip(*df["Current_Price_Range_USD"].apply(parse_price_range))
            valid_lows = [l for l in lows if l is not None]
            if valid_lows:
                st.metric("Price Range (Low)", f"${min(valid_lows):.0f} – ${max([h for h in highs if h is not None]):.0f}")
            else:
                st.metric("Price Range", "—")
        else:
            st.metric("Price Info", "—")
    
    with col4:
        if "Brand_Examples" in df.columns:
            # Count unique brands (rough)
            all_brands = set()
            for b in df["Brand_Examples"].dropna():
                for brand in str(b).split(" / "):
                    all_brands.add(brand.strip())
            st.metric("Unique Brands (approx)", len(all_brands))
        else:
            st.metric("Brands", "—")
    
    st.divider()
    
    # -----------------------------
    # Filters Section
    # -----------------------------
    with st.expander("🔍 Filters & Search", expanded=True):
        filter_cols = st.columns([2, 2, 3])
        
        filtered_df = df.copy()
        
        # Category filter
        if "Category" in df.columns:
            all_cats = sorted(df["Category"].dropna().unique().tolist())
            selected_cats = filter_cols[0].multiselect(
                "Filter by Category",
                options=all_cats,
                default=all_cats
            )
            filtered_df = filtered_df[filtered_df["Category"].isin(selected_cats)]
        
        # Search in Item_Type or Brand
        search_term = filter_cols[1].text_input(
            "Search Item Type / Brand / Features",
            placeholder="e.g. iPhone, Nike, waterproof..."
        )
        if search_term:
            search_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            for col in ["Item_Type", "Brand_Examples", "Key_Features", "Best_For"]:
                if col in filtered_df.columns:
                    search_mask = search_mask | filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[search_mask]
        
        # Price range filter (if available)
        if "Current_Price_Range_USD" in df.columns:
            lows, highs = zip(*df["Current_Price_Range_USD"].apply(parse_price_range))
            valid_lows = [l for l in lows if l is not None]
            if valid_lows:
                min_price = int(min(valid_lows))
                max_price = int(max([h for h in highs if h is not None] or [min_price + 100]))
                price_range = filter_cols[2].slider(
                    "Max Price (High end of range)",
                    min_value=min_price,
                    max_value=max_price,
                    value=max_price,
                    step=5
                )
                # Filter rows where high price <= selected
                row_highs = [h if h is not None else 999999 for h in highs]
                price_mask = pd.Series(row_highs, index=df.index) <= price_range
                filtered_df = filtered_df[price_mask.reindex(filtered_df.index, fill_value=False)]
    
    # -----------------------------
    # Data Table
    # -----------------------------
    st.subheader("📄 Interactive Data Table")
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=420,
        hide_index=True
    )
    
    # Download button
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Data as CSV",
        data=csv,
        file_name=f"{selected_name}_filtered.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.divider()
    
    # -----------------------------
    # Visualizations
    # -----------------------------
    st.subheader("📈 Visualizations")
    
    viz_tab1, viz_tab2, viz_tab3 = st.tabs(["Category Distribution", "Price Analysis", "Brand Overview"])
    
    with viz_tab1:
        if "Category" in filtered_df.columns and len(filtered_df) > 0:
            cat_counts = filtered_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            
            chart = alt.Chart(cat_counts).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("Count:Q", title="Number of Items"),
                y=alt.Y("Category:N", sort="-x", title="Category"),
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["Category", "Count"]
            ).properties(
                title=f"Items per Category — {selected_name}",
                height=400
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No Category data available for visualization.")
    
    with viz_tab2:
        if "Current_Price_Range_USD" in filtered_df.columns and len(filtered_df) > 0:
            price_data = filtered_df[["Item_Type", "Current_Price_Range_USD", "Category"]].copy()
            price_data[["Price_Low", "Price_High"]] = price_data["Current_Price_Range_USD"].apply(
                lambda x: pd.Series(parse_price_range(x))
            )
            price_data = price_data.dropna(subset=["Price_Low"])
            
            if len(price_data) > 0:
                # Average low price by category
                avg_price = price_data.groupby("Category")["Price_Low"].mean().reset_index()
                avg_price.columns = ["Category", "Avg Low Price ($)"]
                
                price_chart = alt.Chart(avg_price).mark_bar().encode(
                    x=alt.X("Avg Low Price ($):Q"),
                    y=alt.Y("Category:N", sort="-x"),
                    color=alt.Color("Avg Low Price ($):Q", scale=alt.Scale(scheme="greens")),
                    tooltip=["Category", "Avg Low Price ($)"]
                ).properties(
                    title="Average Lowest Price by Category",
                    height=350
                )
                st.altair_chart(price_chart, use_container_width=True)
                
                st.caption("Note: Prices parsed from range strings. Actual selling prices may vary.")
            else:
                st.info("Could not parse numeric prices from the data.")
        else:
            st.info("No price range column found in this dataset.")
    
    with viz_tab3:
        if "Brand_Examples" in filtered_df.columns and len(filtered_df) > 0:
            # Simple brand frequency (split by / )
            brand_list = []
            for brands in filtered_df["Brand_Examples"].dropna():
                for b in str(brands).split(" / "):
                    brand_list.append(b.strip())
            
            if brand_list:
                brand_counts = pd.Series(brand_list).value_counts().head(15).reset_index()
                brand_counts.columns = ["Brand", "Mentions"]
                
                brand_chart = alt.Chart(brand_counts).mark_bar().encode(
                    x=alt.X("Mentions:Q"),
                    y=alt.Y("Brand:N", sort="-x"),
                    color=alt.Color("Mentions:Q", scale=alt.Scale(scheme="oranges")),
                    tooltip=["Brand", "Mentions"]
                ).properties(
                    title="Top Mentioned Brands (from Brand_Examples column)",
                    height=400
                )
                st.altair_chart(brand_chart, use_container_width=True)
            else:
                st.info("No brand data available.")
        else:
            st.info("No Brand_Examples column in this dataset.")
    
    # Footer note
    st.caption("💡 Tip: Use the filters above to narrow down results before downloading. New uploads are available only in this session — save important ones locally.")

else:
    # Welcome / instructions screen
    st.info("👈 Use the sidebar to load datasets from your artifacts folder or upload new Key Findings CSVs.")
    
    st.markdown("""
    ### How to use this tool
    1. Click **"Load All from Artifacts Folder"** to automatically import all your existing top-selling datasets.
    2. Or upload new CSVs created from future "Do this for X" requests.
    3. Select a dataset from the dropdown.
    4. Explore with filters, search, interactive table, and visualizations (category distribution, price analysis, brand overview).
    5. Download filtered subsets as CSV for use in quotes, reports, or further analysis.
    
    This app works great alongside your other business tools (quote calculators, comparison dashboards, etc.).
    """)
    
    with st.expander("Supported Dataset Format"):
        st.markdown("""
        The visualizer works best with your standard **Key Findings** CSVs that have columns like:
        - `Category`
        - `Item_Type`
        - `Brand_Examples`
        - `Type`
        - `Current_Price_Range_USD`
        - `Key_Features`
        - `Best_For`
        - `Notes_June_2026` (or similar)
        
        Most of the datasets you've generated follow this structure, so they should load cleanly.
        """)

# -----------------------------
# Requirements note for deployment
# -----------------------------
st.sidebar.caption("For Streamlit Community Cloud deployment, use this requirements.txt:\n\nstreamlit\npandas\naltair")
