import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="TikTok 批量库存更新工具", layout="wide")
st.title("📦 TikTok 批量库存更新工具")

st.markdown("""
该工具会从第 5 行开始，根据 `Seller SKU` 匹配库存文件的 `SKU编码`，更新 TikTok 模板表格中的  
➡️ `Quantity in U.S Pickup Warehouse` 列的值。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])

if tiktok_file and inventory_file:
    try:
        # 读取两个文件
        df_tiktok = pd.read_excel(tiktok_file, sheet_name=0, header=None)
        df_inventory = pd.read_csv(inventory_file)

        # 库存字典：清洗 SKU 字段用于匹配
        inventory_map = df_inventory.copy()
        inventory_map["SKU编码"] = inventory_map["SKU编码"].astype(str).str.strip()
        inventory_map["当前库存"] = pd.to_numeric(inventory_map["当前库存"], errors="coerce").fillna(0)
        sku_dict = dict(zip(inventory_map["SKU编码"], inventory_map["当前库存"]))

        # 找出字段所在列
        header_row = df_tiktok.iloc[1]
        sku_col = header_row[header_row == "Seller SKU"].index[0]
        qty_col = header_row[header_row == "Quantity in U.S Pickup Warehouse"].index[0]

        # 从第 4 行（索引为 4）开始是实际数据
        for i in range(4, len(df_tiktok)):
            sku = str(df_tiktok.iat[i, sku_col]).strip()
            if sku in sku_dict:
                df_tiktok.iat[i, qty_col] = sku_dict[sku]

        # 生成下载 Excel
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            return output.getvalue()

        result_excel = to_excel(df_tiktok)

        st.success("✅ 更新完成！点击下方按钮下载 Excel 文件：")
        st.download_button(
            label="📥 下载更新后的 TikTok 模板",
            data=result_excel,
            file_name="updated_tiktok_batch_edit.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
