import streamlit as st
import pandas as pd
import re
import tempfile
from openpyxl import load_workbook

st.set_page_config(page_title="TikTok库存列生成器", layout="wide")
st.title("📋 TikTok Quantity 列生成器（含一键复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，  
仅生成 `Quantity in U.S Pickup Warehouse` 的数字列，  
📋 可直接 **一键复制**，粘贴回模板中。
""")

# 上传文件
tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])


# —— 工具：Bundle 拆分 —— #
def split_bundle(sku_with_size: str):
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


# —— 工具：Bundle 库存计算 —— #
def bundle_stock_min(sku_with_size: str, stock_map: dict, *, for_unmatched: list):
    skus, is_bundle = split_bundle(sku_with_size)

    if not is_bundle:  
        if skus[0] in stock_map:
            return str(int(stock_map[skus[0]]))
        else:
            for_unmatched.append(skus[0])
            return ""

    found_all = all(k in stock_map for k in skus)
    if not found_all:
        missing = [k for k in skus if k not in stock_map]
        for_unmatched.extend(missing)
        return "0"

    return str(min(int(stock_map[k]) for k in skus))


# —— 主逻辑 —— #
if tiktok_file and inventory_file:
    try:
        # 将上传 Excel 写到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(tiktok_file.read())
            temp_path = tmp.name

        # 使用 openpyxl 的只读模式读取（不解析样式 → 永不报 XML 错误）
        wb = load_workbook(temp_path, data_only=True, read_only=True)
        ws = wb.active

        # 转成 pandas dataframe
        data = list(ws.values)
        df_tiktok = pd.DataFrame(data)

        # 自动查找表头
        sku_col = qty_col = None
        header_row_index = None

        for i in range(10):
            row = df_tiktok.iloc[i].astype(str).str.strip()
            if "Seller SKU" in row.values and "Quantity in U.S Pickup Warehouse" in row.values:
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in U.S Pickup Warehouse"].index[0]
                header_row_index = i
                break

        if sku_col is None:
            st.error("❌ 未找到表头：请确认是否为 TikTok 批量编辑模板。")
            st.stop()

        # 读取库存 CSV
        df_inventory = pd.read_csv(inventory_file)
        df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
        df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
        stock_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

        # 找到数据开始行
        start_row = header_row_index + 1
        while start_row < len(df_tiktok):
            val = str(df_tiktok.iat[start_row, qty_col]).strip()
            if val.replace(".", "", 1).isdigit() or val == "":
                break
            start_row += 1

        result_list = []
        unmatched_skus = []

        # 逐行匹配 SKU
        for i in range(start_row, len(df_tiktok)):
            raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
            original_qty = str(df_tiktok.iat[i, qty_col]).strip()

            computed = bundle_stock_min(raw_sku, stock_map, for_unmatched=unmatched_skus)

            if computed != "":
                result_list.append(computed)
            else:
                result_list.append(original_qty)

        output_text = "\n".join(result_list)

        st.success("✅ 匹配成功！点击下方按钮复制整个库存列：")
        st.code(output_text, language="text")

        st.markdown(
            f"""
            <button onclick="navigator.clipboard.writeText(`{output_text}`)"
            style="background-color:#4CAF50;color:white;padding:10px 16px;
                   border:none;border-radius:5px;cursor:pointer;margin-top:10px;">
            📋 一键复制库存列
            </button>
            """,
            unsafe_allow_html=True,
        )

        # 下载结果 CSV
        df_export = pd.DataFrame({
            "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).str.strip().values,
            "Updated Quantity": result_list
        })

        csv_file = df_export.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 下载为 CSV",
            data=csv_file,
            file_name="quantity_column.csv",
            mime="text/csv",
        )

        # 显示未匹配 SKU
        if unmatched_skus:
            uniq = list(dict.fromkeys(unmatched_skus))
            st.warning(
                "⚠️ 以下 SKU 未在库存表中找到（Bundle 按 0；单品保留原数量）：\n" +
                "\n".join(uniq[:20]) +
                ("\n..." if len(uniq) > 20 else "")
            )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
