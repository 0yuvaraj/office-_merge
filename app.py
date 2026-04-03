import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(layout="wide")
st.title("Dynamic Data Merger")

st.write("Upload two Excel files, select how they link together, and choose which columns to include in the final report.")

def clean_key(value):
    """Aggressively clean a merge key value to maximize matching."""
    s = str(value).strip().upper()
    # Only convert to string and strip whitespace — no other transformations
    return s

col1, col2 = st.columns(2)
with col1:
    upload_1 = st.file_uploader("Upload File 1 (Base)", type=['xlsx'])
with col2:
    upload_2 = st.file_uploader("Upload File 2 (Secondary)", type=['xlsx'])

if upload_1 and upload_2:
    try:
        df1 = pd.read_excel(upload_1)
        df2 = pd.read_excel(upload_2)

        # Strip whitespace from column names
        df1.columns = df1.columns.str.strip().astype(str)
        df2.columns = df2.columns.str.strip().astype(str)

        # Auto-swap: use the file with more columns as the base (File 1)
        # If columns are equal, use the file with more rows as the base
        if len(df2.columns) > len(df1.columns) or (len(df2.columns) == len(df1.columns) and len(df2) > len(df1)):
            df1, df2 = df2, df1
            st.info(f"ℹ️ Files were automatically swapped — the file with more data ({len(df1)} rows, {len(df1.columns)} cols) is now used as the base (File 1).")

        # Show previews of both files
        st.divider()
        st.subheader("📋 Data Preview")
        prev1, prev2 = st.columns(2)
        with prev1:
            st.write(f"**File 1 (Base)** — {len(df1)} rows, {len(df1.columns)} columns")
            st.dataframe(df1.head(5), use_container_width=True)
        with prev2:
            st.write(f"**File 2 (Secondary)** — {len(df2)} rows, {len(df2.columns)} columns")
            st.dataframe(df2.head(5), use_container_width=True)

        st.divider()
        st.subheader("1. Select Merge Keys")
        st.write("Choose the column in each file that contains matching IDs (e.g., 'Assessment Number').")
        
        c1, c2 = st.columns(2)
        with c1:
            key1 = st.selectbox("Merge Key for File 1", options=df1.columns.tolist())
        with c2:
            key2 = st.selectbox("Merge Key for File 2", options=df2.columns.tolist())

        # Show a live match preview BEFORE merging
        keys1_clean = df1[key1].apply(clean_key)
        keys2_clean = df2[key2].apply(clean_key)
        common_keys = set(keys1_clean) & set(keys2_clean)
        match_count = keys1_clean.isin(keys2_clean).sum()
        
        if match_count == 0:
            st.error(f"⚠️ 0 out of {len(df1)} rows in File 1 match any row in File 2 using these keys!")
            with st.expander("🔍 Show sample key values to compare"):
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.write(f"**File 1 '{key1}' (first 10, cleaned):**")
                    sample1 = pd.DataFrame({'Original': df1[key1].head(10), 'Cleaned': keys1_clean.head(10)})
                    st.dataframe(sample1)
                with dc2:
                    st.write(f"**File 2 '{key2}' (first 10, cleaned):**")
                    sample2 = pd.DataFrame({'Original': df2[key2].head(10), 'Cleaned': keys2_clean.head(10)})
                    st.dataframe(sample2)
        else:
            st.success(f"✅ {match_count} out of {len(df1)} rows in File 1 have a match in File 2!")

        st.divider()
        st.subheader("2. Select Desired Output Columns & Order")
        st.write("Select the columns you want to keep. The order you select them will be their order in the final file.")

        c3, c4 = st.columns(2)
        with c3:
            cols1 = st.multiselect("Select columns to keep from File 1", options=df1.columns.tolist(), default=df1.columns.tolist())
        with c4:
            default_cols2 = [c for c in df2.columns if c != key2]
            cols2 = st.multiselect("Select columns to keep from File 2", options=df2.columns.tolist(), default=default_cols2)

        st.divider()
        
        if st.button("Process and Merge Data", type="primary"):
            try:
                # Add a cleaned key column to both dataframes for merging
                df1_work = df1.copy()
                df2_work = df2.copy()
                df1_work['_merge_key'] = df1_work[key1].apply(clean_key)
                df2_work['_merge_key'] = df2_work[key2].apply(clean_key)

                # Select only columns the user wants + the merge key
                keep_cols_1 = list(dict.fromkeys(cols1 + ['_merge_key']))
                keep_cols_2 = list(dict.fromkeys(cols2 + ['_merge_key']))

                merged_df = pd.merge(
                    df1_work[keep_cols_1],
                    df2_work[keep_cols_2],
                    on='_merge_key',
                    how='left',
                    suffixes=('', '_file2')
                ).drop(columns=['_merge_key'])

                # Build the final column order based on user selections
                ordered_cols = []
                for col in cols1:
                    if col in merged_df.columns:
                        ordered_cols.append(col)
                    elif f"{col}_file2" in merged_df.columns:
                        ordered_cols.append(f"{col}_file2")

                for col in cols2:
                    if col in merged_df.columns and col not in ordered_cols:
                        ordered_cols.append(col)
                    elif f"{col}_file2" in merged_df.columns and f"{col}_file2" not in ordered_cols:
                        ordered_cols.append(f"{col}_file2")

                final_df = merged_df[ordered_cols]

                st.success("Data Merged Successfully!")
                st.dataframe(final_df.head(50), use_container_width=True)

                # Download Button
                towrite = io.BytesIO()
                final_df.to_excel(towrite, index=False, engine='openpyxl')
                towrite.seek(0)
                
                st.download_button(
                    label="📥 Download Merged Excel File",
                    data=towrite,
                    file_name="merged_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as merge_err:
                st.error(f"Error during merge: {merge_err}")
                st.exception(merge_err)

    except Exception as read_err:
        st.error(f"Error reading the excel files: {read_err}")
