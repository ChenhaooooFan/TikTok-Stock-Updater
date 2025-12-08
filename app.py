import streamlit as st
import pandas as pd
import re
import tempfile

st.set_page_config(page_title="TikTok库存列一键复制", layout="wide")
st.title("📋 TikTok Quantity 列生成器（含一键复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，  
仅生成 `Quantity in U.S Pickup Warehouse` 的数字列，  
📋 可直接 **一键复制**，粘贴回模板中。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])


# —— 工具：Bundle 拆分与最小库存计算 —— #
def split_bundle(sku_with_size: str):
    """
    输入示例:
      'ABC123DEF456-S' / 'ABC123DEF456GHI789-S' / 'ABC123-S'
    返回: (组成SKU列表, 是否为 bundle)
    """
    s = (sku_with_size or "").strip()
    if "-" not in s:
        return [s], False

    code, size = s.split("-", 1)
    code = code.strip()
    size = size.strip()

    if len(code) % 6 == 0 and 6 <= len(code) <= 24:
        parts = [code[i:i+6] for i in range(0, len(code), 6)]
        if all(re.fullmatch(r"[A-Z]{3}\d{3}", p) for p in parts):
            return [f"{p}-{size}" for p in parts], (len(parts) >= 2)

    return [s], False


def bundle_stock_min(sku_with_size: str, stock_map: dict, *, for_unmatched: list) -> str:
    """
    单品：若库存表有该 SKU -> 返回库存；没有 -> 返回 ""（保留原值）
    Bundle：若所有组成 SKU 存在 -> 返回最小库存；否则返回 0
    """
    skus, is_bundle = split_bundle(sku_with_size)

    if not is_bundle:  # 单品
        if skus and skus[0] in stock_map:
            return str(int(stock_map[skus[0]]))
        else:
            if skus and skus[0] not in ["", "nan", "None"]:
                for_unmatched.append(skus[0])
            return ""

    # Bundle
    found_all = all(k in stock_map for k in skus)
    if not found_all:
        missing_parts = [k for k in skus if k not in stock_map]
        for_unmatched.extend(missing_parts)
        return "0"

    vals = [int(stock_map[k]) for k in skus]
    return str(min(vals))


# —— 主逻辑 —— #
if tiktok_file and inventory_file:
    try:
        # 将上传的 Excel 写入临时文件，避免 openpyxl 在 BytesIO 上解析失败
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(tiktok_file.read())
            temp_path = tmp.name

        df_tiktok = pd.read_excel(temp_path, header=None)

        # 自动定位表头所在行与列
        sku_col = qty_col = None
        header_row_index = None

        for i in range(5):
            row = df_tiktok.iloc[i].astype(str).str.strip()
            if (
                "Seller SKU" in row.values and
                "Quantity in U.S Pickup Warehouse" in row.values
            ):
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in U.S Pickup Warehouse"].index[0]
                header_row_index = i
                break

        if sku_col is None or qty_col is None:
            st.error("❌ 未找到 'Seller SKU' 或 'Quantity in U.S Pickup Warehouse' 列，请确认表格格式是否正确。")
        else:
            # 读取库存
            df_inventory = pd.read_csv(inventory_file)
            df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
            df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)

            stock_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 找到数据开始行
            start_row = header_row_index + 1
            while start_row < len(df_tiktok):
                cell_value = str(df_tiktok.iat[start_row, qty_col]).strip()
                if cell_value.replace('.', '', 1).isdigit() or cell_value == "":
                    break
                start_row += 1

            result_list = []
            unmatched_skus = []

            # —— 逐行匹配 SKU —— #
            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                original_qty = str(df_tiktok.iat[i, qty_col]).strip()

                computed = bundle_stock_min(raw_sku, stock_map, for_unmatched=unmatched_skus)

                if computed != "":
                    result_list.append(computed)
                else:
                    result_list.append(original_qty)

            quantity_text = "\n".join(result_list)

            st.success("✅ 匹配成功！点击下方按钮复制整个库存列：")
            st.code(quantity_text, language="text")

            # 一键复制按钮
            st.markdown(f"""
                <button onclick="navigator.clipboard.writeText(`{quantity_text}`)"
                style="background-color:#4CAF50;color:white;padding:10px 16px;border:none;border-radius:5px;cursor:pointer;margin-top:10px;">
                📋 一键复制库存列
                </button>
                """, unsafe_allow_html=True)

            # 导出 CSV
            df_export = pd.DataFrame({
                "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).str.strip().values,
                "Updated Quantity": result_list
            })

            csv_file = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载为 CSV", data=csv_file, file_name="quantity_column.csv", mime="text/csv")

            # 未匹配提示
            if unmatched_skus:
                uniq = []
                seen = set()
                for s in unmatched_skus:
                    if s not in seen:
                        uniq.append(s)
                        seen.add(s)

                st.warning("⚠️ 以下 SKU 未在库存表中找到（Bundle 按 0 处理；单品保留原数量）：\n" +
                           "\n".join(uniq[:20]) +
                           ("\n..." if len(uniq) > 20 else ""))

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
