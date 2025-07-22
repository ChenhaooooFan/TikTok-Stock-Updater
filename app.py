import streamlit as st
import pandas as pd
from io import BytesIO

# 页面设置
st.set_page_config(page_title="SyncVesta - 美甲库存同步工具", layout="wide")
st.title("💅 SyncVesta – NailVesta TikTok 库存同步工具")

# 使用说明
st.markdown("""
**功能说明：**  
📌 将 NailVesta 内部库存（CSV）按 `Seller SKU` 同步至 TikTok 表格  
➡️ 更新 `Total quantity in U.S Pickup Warehouse` = 当前库存 + Locked quantity  
✅ 匹配字段自动清洗（.strip()），导出文件保持原结构  
⚠️ 未匹配 SKU 保留原值，并在页面提示  
📤 导出为 Excel 文件 (.xlsx)
""")

# 上传文件
file1 = st.file_uploader("📤 上传 TikTok 导出文件（Excel）", type=["xlsx"])
file2 = st.file_uploader("📤 上传 NailVesta 内部库存文件（CSV）", type=["csv"])

if file1 and file2:
    try:
        # 读取原始文件
        df_tiktok_original = pd.read_excel(file1, sheet_name=0)
        df_inventory_original = pd.read_csv(file2)

        # 创建副本用于处理
        df_tiktok = df_tiktok_original.copy()
        df_inventory = df_inventory_original.copy()

        # 清洗 SKU 字段用于匹配（不会影响导出结构）
        df_tiktok["__clean_sku__"] = df_tiktok["Seller SKU"].astype(str).str.strip()
        df_inventory["__clean_sku__"] = df_inventory["SKU编码"].astype(str).str.strip()
        df_inventory["库存"] = df_inventory["当前库存"]

        # 构建 SKU → 当前库存 映射字典
        sku_to_inventory = df_inventory.set_index("__clean_sku__")["库存"].to_dict()

        # 匹配有效数据行
        mask = df_tiktok["Seller SKU"].notna() & ~df_tiktok["Seller SKU"].astype(str).str.contains("Cannot be edited", na=False)
        cleaned_skus = df_tiktok.loc[mask, "__clean_sku__"]

        # 获取库存匹配结果
        updated_inventory = cleaned_skus.map(sku_to_inventory)

        # 获取 Locked quantity 并加总
        locked = pd.to_numeric(df_tiktok.loc[mask, "Locked quantity"], errors='coerce').fillna(0)
        final_values = updated_inventory.add(locked, fill_value=0)

        # 未匹配的保持原始值
        original_values = df_tiktok_original.loc[mask, "Total quantity in U.S Pickup Warehouse"]
        final_values = final_values.where(updated_inventory.notna(), original_values)

        # 写入结果到输出表
        df_output = df_tiktok_original.copy()
        df_output.loc[mask, "Total quantity in U.S Pickup Warehouse"] = final_values

        # 提示未匹配的 SKU
        unmatched_skus = cleaned_skus[updated_inventory.isna()].unique().tolist()
        if unmatched_skus:
            st.warning(f"⚠️ 以下 {len(unmatched_skus)} 个 SKU 未在库存中匹配成功（原值已保留）：\n" + "\n".join(unmatched_skus))

        # 输出为 Excel 文件
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            return output.getvalue()

        updated_excel = to_excel(df_output)

        # 下载按钮
        st.success("✅ 库存同步完成！点击下方按钮下载 Excel 文件：")
        st.download_button(
            label="📥 下载更新后的 Excel 文件",
            data=updated_excel,
            file_name="updated_tiktok_inventory.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
