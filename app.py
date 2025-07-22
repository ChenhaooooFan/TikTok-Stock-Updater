import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="SyncVesta - 美甲库存同步工具", layout="wide")
st.title("💅 SyncVesta – NailVesta TikTok 库存同步工具")

st.markdown(\"""
**功能说明：**  
📌 将 NailVesta 内部 CSV 库存（按 Seller SKU）更新至 TikTok Excel 的  
➡️ `Total quantity in U.S Pickup Warehouse` 列  
支持文件上传 + 一键下载结果。
\""")

# 上传文件
file1 = st.file_uploader("📤 上传 TikTok 导出文件（Excel）", type=["xlsx"])
file2 = st.file_uploader("📤 上传 NailVesta 内部库存文件（CSV）", type=["csv"])

if file1 and file2:
    try:
        # 读取两个文件
        df_tiktok = pd.read_excel(file1, sheet_name=0)
        df_inventory = pd.read_csv(file2)

        # 清洗库存表
        df_inventory = df_inventory.rename(columns={"SKU编码": "Seller SKU", "当前库存": "库存"})
        df_inventory = df_inventory[["Seller SKU", "库存"]].dropna()

        # 排除说明行，只更新有效 SKU 行
        mask = df_tiktok["Seller SKU"].notna() & ~df_tiktok["Seller SKU"].astype(str).str.contains("Cannot be edited", na=False)

        # 匹配并更新库存列
        df_update = df_tiktok[mask].merge(df_inventory, on="Seller SKU", how="left")
        df_tiktok.loc[mask, "Total quantity in U.S Pickup Warehouse"] = df_update["库存"].values

        # 提供下载
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            return output.getvalue()

        updated_excel = to_excel(df_tiktok)
        st.success("✅ 库存同步完成！点击下方按钮下载：")
        st.download_button("📥 下载更新后的 Excel 文件", data=updated_excel, file_name="updated_tiktok_inventory.xlsx")

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
