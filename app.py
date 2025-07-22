import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="库存列生成器", layout="wide")
st.title("📋 TikTok Quantity 列生成器")

st.markdown("""
将 TikTok 模板中 `Seller SKU` 与库存文件中的 `SKU编码` 对应，  
仅输出 `Quantity in U.S Pickup Warehouse` 列的更新值，供你复制粘贴回模板中。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])

if tiktok_file and inventory_file:
    try:
        # 读取 TikTok 文件
        df_tiktok = pd.read_excel(tiktok_file, header=None)

        # 自动识别列名所在行
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
            st.error("❌ 没找到 'Seller SKU' 或 'Quantity in U.S Pickup Warehouse' 列，请检查文件格式")
        else:
            # 读取库存 CSV
            df_inventory = pd.read_csv(inventory_file)
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
            sku_dict = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 从数据区开始读取 SKU 并生成数量列表
            start_row = header_row_index + 2
            quantity_list = []
            sku_list = []

            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                sku_list.append(raw_sku)
                if raw_sku in sku_dict:
                    quantity_list.append(int(sku_dict[raw_sku]))
                else:
                    quantity_list.append("")

            result_df = pd.DataFrame({
                "SKU": sku_list,
                "Updated Quantity in U.S Pickup Warehouse": quantity_list
            })

            st.success("✅ 匹配完成！下方是可以复制粘贴的库存列：")
            st.dataframe(result_df, use_container_width=True)

            # 提供导出 CSV 选项
            csv_data = result_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载为 CSV 文件", data=csv_data, file_name="quantity_column.csv", mime="text/csv")

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
