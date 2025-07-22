import streamlit as st
import pandas as pd
from io import BytesIO

# 页面设置
st.set_page_config(page_title="SyncVesta - 美甲库存同步工具", layout="wide")
st.title("💅 SyncVesta – NailVesta TikTok 库存同步工具")

# 使用说明
st.markdown("""
**功能说明：**  
📌 将 NailVesta 内部 CSV 库存（按 Seller SKU）更新至 TikTok Excel 的  
➡️ `Total quantity in U.S Pickup Warehouse` 列  
最终生成 **Excel 文件 (.xlsx)**，用于快速导入 TikTok。
""")

# 上传文件
file1 = st.file_uploader("📤 上传 TikTok 导出文件（Excel）", type=["xlsx"])
file2 = st.file_uploader("📤 上传 NailVesta 内部库存文件（CSV）", type=["csv"])

if file1 and file2:
    try:
        # 读取 Excel（TikTok 数据）
        df_tiktok = pd.read_excel(file1, sheet_name=0)

        # 读取 CSV（库存数据）
        df_inventory = pd.read_csv(file2)

        # 重命名并筛选库存数据列
        df_inventory = df_inventory.rename(columns={"SKU编码": "Seller SKU", "当前库存": "库存"})
        df_inventory = df_inventory[["Seller SKU", "库存"]].dropna()

        # 仅更新真实数据行，跳过标题/说明
        mask = df_tiktok["Seller SKU"].notna() & ~df_tiktok["Seller SKU"].astype(str).str.contains("Cannot be edited", na=False)

        # 合并并更新 TikTok 表格中的库存列
        df_update = df_tiktok[mask].merge(df_inventory, on="Seller SKU", how="left")
        df_tiktok.loc[mask, "Total quantity in U.S Pickup Warehouse"] = df_update["库存"].values

        # 导出为 Excel 文件
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            return output.getvalue()

        updated_excel = to_excel(df_tiktok)

        # 下载按钮
        st.success("✅ 更新完成！点击下方按钮下载 Excel 文件：")
        st.download_button(
            label="📥 下载更新后的 Excel 文件",
            data=updated_excel,
            file_name="updated_tiktok_inventory.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
