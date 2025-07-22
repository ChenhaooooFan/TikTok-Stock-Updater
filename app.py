import streamlit as st
import pandas as pd

st.set_page_config(page_title="📋 仅数字库存列复制器", layout="wide")
st.title("📋 TikTok 库存列生成器（纯数字复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，  
只生成纯数字的 `Quantity in U.S Pickup Warehouse` 列 ✅  
👉 一键复制，无任何额外说明文字。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])

if tiktok_file and inventory_file:
    try:
        df_tiktok = pd.read_excel(tiktok_file, header=None)

        # 自动定位表头行和列索引
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
            st.error("❌ 未找到所需的列，请确认文件格式")
        else:
            df_inventory = pd.read_csv(inventory_file)
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
            sku_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 匹配并保留原值（若未匹配）
            start_row = header_row_index + 2
            result_list = []
            unmatched_skus = []

            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                original_qty = df_tiktok.iat[i, qty_col]

                if raw_sku in sku_map:
                    result_list.append(str(int(sku_map[raw_sku])))
                else:
                    result_list.append(str(original_qty) if pd.notna(original_qty) else "")
                    if raw_sku not in ["nan", "None", ""]:
                        unmatched_skus.append(raw_sku)

            quantity_text = "\n".join(result_list)

            # 显示纯数字 + 复制按钮
            st.text_area("📋 复制这段数字（直接粘贴到 Excel 中）", quantity_text, height=500)

            st.markdown(f"""
                <button onclick="navigator.clipboard.writeText(`{quantity_text}`)"
                style="background-color:#008CBA;color:white;padding:10px 16px;border:none;border-radius:5px;cursor:pointer;margin-top:10px;">
                📋 一键复制纯数字库存列
                </button>
                """, unsafe_allow_html=True)

            # 提示未匹配
            if unmatched_skus:
                st.warning("⚠️ 以下 SKU 未匹配成功（已保留原值）：\n" + "\n".join(unmatched_skus[:10]) + ("\n..." if len(unmatched_skus) > 10 else ""))

    except Exception as e:
        st.error(f"❌ 错误：{e}")
