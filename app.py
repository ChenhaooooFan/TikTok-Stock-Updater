import streamlit as st
import pandas as pd

st.set_page_config(page_title="TikTok库存列复制", layout="wide")
st.title("\U0001F4CB TikTok 库存列复制工具（纯数字）")

st.markdown("将 TikTok 模板与库存文件对比，仅生成纯数字的库存列，可直接粘贴至 Excel ✅")

tiktok_file = st.file_uploader("\U0001F4C4 上传 TikTok 批量编辑模板（.xlsx）", type=["xlsx"])
inventory_file = st.file_uploader("\U0001F4C4 上传库存 CSV 文件", type=["csv"])

if tiktok_file and inventory_file:
    try:
        df_tiktok = pd.read_excel(tiktok_file, header=None)
        sku_col = qty_col = header_row_index = None

        # 找列名
        for i in range(5):
            row = df_tiktok.iloc[i].astype(str).str.strip()
            if "Seller SKU" in row.values and "Quantity in U.S Pickup Warehouse" in row.values:
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in U.S Pickup Warehouse"].index[0]
                header_row_index = i
                break

        if sku_col is None or qty_col is None:
            st.error("❌ 没找到所需列，请检查上传的 Excel 文件")
        else:
            df_inventory = pd.read_csv(inventory_file)
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
            sku_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            start_row = header_row_index + 2
            result_list = []
            unmatched = []

            for i in range(start_row, len(df_tiktok)):
                sku = str(df_tiktok.iat[i, sku_col]).strip()
                original_qty = df_tiktok.iat[i, qty_col]

                if sku in sku_map:
                    result_list.append(str(int(sku_map[sku])))
                else:
                    result_list.append(str(original_qty) if pd.notna(original_qty) else "")
                    if sku not in ["nan", "None", ""]:
                        unmatched.append(sku)

            final_output = "\n".join(result_list)

            # ✅ 展示纯数字列用于复制 + 复制按钮
            st.download_button(
                label="📋 复制库存列为 TXT 文件（可打开复制粘贴）",
                data=final_output,
                file_name="tiktok_warehouse_column.txt",
                mime="text/plain"
            )

            st.text_area("\U0001F4CB 预览库存数字（粘贴至 Excel）", final_output, height=500)

            # 未匹配提示
            if unmatched:
                st.warning("⚠️ 以下 SKU 未匹配成功（原值保留）：\n" + "\n".join(unmatched[:10]) + ("\n..." if len(unmatched) > 10 else ""))

    except Exception as e:
        st.error(f"❌ 错误：{e}")
