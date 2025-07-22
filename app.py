import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="TikTok 批量库存更新工具", layout="wide")
st.title("📦 TikTok 批量库存更新工具")

st.markdown("""
该工具从 TikTok 模板中自动识别 `Seller SKU` 和 `Quantity in U.S Pickup Warehouse` 列，  
再从库存 CSV 中匹配 SKU，更新 TikTok 模板中对应的库存数量。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])

if tiktok_file and inventory_file:
    try:
        # 读取文件
        df_tiktok = pd.read_excel(tiktok_file, sheet_name=0, header=None)
        df_inventory = pd.read_csv(inventory_file)

        # 自动识别包含表头字段的行
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
            st.error("❌ 没有在前 5 行内找到 'Seller SKU' 或 'Quantity in U.S Pickup Warehouse' 字段，请确认格式。")
        else:
            # 构建库存映射表
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
            sku_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 数据区从 header_row_index + 2 开始（跳过表头 + 说明行）
            start_row = header_row_index + 2
            unmatched_skus = []

            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                if raw_sku in sku_map:
                    df_tiktok.iat[i, qty_col] = sku_map[raw_sku]
                elif raw_sku not in ["nan", "None", ""]:
                    unmatched_skus.append(raw_sku)

            # 输出提示
            if unmatched_skus:
                st.warning(f"⚠️ 以下 SKU 未匹配到库存，保持原值：\n" + "\n".join(unmatched_skus[:10]) + ("\n..." if len(unmatched_skus) > 10 else ""))

            # 导出为 Excel
            def to_excel(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
                return output.getvalue()

            updated_file = to_excel(df_tiktok)

            st.success("✅ 更新完成，点击下载：")
            st.download_button(
                label="📥 下载更新后的 Excel 文件",
                data=updated_file,
                file_name="updated_tiktok_batch_edit.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
