import streamlit as st
import pandas as pd

st.set_page_config(page_title="TikTok库存列一键复制", layout="wide")
st.title("📋 TikTok Quantity列生成器（可一键复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，  
仅生成 `Quantity in U.S Pickup Warehouse` 的数字列，  
📋 可直接 **复制粘贴** 回 Excel 模板中。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])

if tiktok_file and inventory_file:
    try:
        df_tiktok = pd.read_excel(tiktok_file, header=None)

        # 自动定位包含表头的那一行
        sku_col = qty_col = None
        header_row_index = None
        for i in range(5):
            row = df_tiktok.iloc[i].astype(str).str.strip()
            if "Seller SKU" in row.values and "Quantity in U.S Pickup Warehouse" in row.values:
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in U.S Pickup Warehouse"].index[0]
                header_row_index = i
                break

        if sku_col is None or qty_col is None:
            st.error("❌ 没找到 'Seller SKU' 或 'Quantity in U.S Pickup Warehouse' 列，请确认表格格式")
        else:
            # 读取库存文件
            df_inventory = pd.read_csv(inventory_file)
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
            sku_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 开始匹配 SKU → 数量
            start_row = header_row_index + 2
            result_list = []
            unmatched_skus = []

            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                if raw_sku in sku_map:
                    result_list.append(str(int(sku_map[raw_sku])))
                else:
                    result_list.append("")
                    if raw_sku not in ["nan", "None", ""]:
                        unmatched_skus.append(raw_sku)

            # 输出可复制文本框
            st.success("✅ 匹配成功！下方为库存数量列，可一键复制粘贴回 Excel：")
            text_block = "\n".join(result_list)
            st.text_area("📋 数字列（与模板中 Quantity 列对应）", text_block, height=500)

            # 可选导出 CSV
            df_export = pd.DataFrame({
                "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).str.strip().values,
                "Updated Quantity": result_list
            })
            csv_file = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载为 CSV", data=csv_file, file_name="quantity_column.csv", mime="text/csv")

            # 提示未匹配
            if unmatched_skus:
                st.warning("⚠️ 以下 SKU 未匹配成功（保留空白）：\n" + "\n".join(unmatched_skus[:10]) + ("\n..." if len(unmatched_skus) > 10 else ""))

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
