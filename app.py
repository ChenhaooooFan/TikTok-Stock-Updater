import streamlit as st
import pandas as pd
import re

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
    输入: 'ABC123DEF456-S' / 'ABC123DEF456GHI789-S' / 'ABC123DEF456GHI789JKL012-S' / 'ABC123-S'
    返回: (组成SKU列表['ABC123-S','DEF456-S',...], 是否为bundle)
    规则：'-' 前为 code，长度需为 6,12,18,24（每段 3字母+3数字）；后缀为尺码（S/M/L 等单字母也可）。
    若不满足规则，视为单品：返回 [原样], False
    """
    s = (sku_with_size or "").strip()
    if "-" not in s:
        return [s], False
    code, size = s.split("-", 1)
    code = code.strip(); size = size.strip()
    if len(code) % 6 == 0 and 6 <= len(code) <= 24:
        parts = [code[i:i+6] for i in range(0, len(code), 6)]
        if all(re.fullmatch(r"[A-Z]{3}\d{3}", p or "") for p in parts):
            return [f"{p}-{size}" for p in parts], (len(parts) >= 2)
    return [s], False

def bundle_stock_min(sku_with_size: str, stock_map: dict, *, for_unmatched: list) -> str:
    """
    - 单品：若库存表有该 SKU -> 返回库存数字；否则返回空字符串（表示保留原表值）
    - Bundle(2-4件)：若所有组成 SKU 均存在 -> 返回这些库存的最小值；
                     若存在任一组成缺失 -> 返回 '0'（保守不超卖）并记录未匹配信息
    返回字符串，便于直接拼接复制列。
    """
    skus, is_bundle = split_bundle(sku_with_size)
    if not is_bundle:
        if skus and skus[0] in stock_map:
            return str(int(stock_map[skus[0]]))
        else:
            # 单品缺失：不覆盖原值（返回空串，后面会用原数量）
            if skus and skus[0] not in ["", "nan", "None"]:
                for_unmatched.append(skus[0])
            return ""
    # bundle 计算最小库存
    found_all = all(k in stock_map for k in skus)
    if not found_all:
        # 记录缺失的组成 SKU，且返回 0
        missing_parts = [k for k in skus if k not in stock_map]
        for_unmatched.extend(missing_parts)
        return "0"
    vals = [int(stock_map[k]) for k in skus]
    return str(min(vals))

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
            stock_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

            # 跳过提示文字，定位真实数据开始行
            start_row = header_row_index + 1
            while start_row < len(df_tiktok):
                cell_value = str(df_tiktok.iat[start_row, qty_col]).strip()
                if cell_value.replace('.', '', 1).isdigit() or cell_value == "":
                    break
                start_row += 1

            result_list = []
            unmatched_skus = []

            for i in range(start_row, len(df_tiktok)):
                raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
                original_qty = str(df_tiktok.iat[i, qty_col]).strip()

                # —— 新逻辑：根据库存生成（bundle 用最小库存；单品按库存；未匹配保留原值）——
                computed = bundle_stock_min(raw_sku, stock_map, for_unmatched=unmatched_skus)
                if computed != "":
                    result_list.append(computed)
                else:
                    # 单品未匹配：保留原始数量值（与原逻辑一致）
                    result_list.append(original_qty)

            quantity_text = "\n".join(result_list)

            # 显示复制按钮和文本内容
            st.success("✅ 匹配成功！点击下方按钮复制整个库存列：")

            st.code(quantity_text, language="text")

            st.markdown(f"""
                <button onclick="navigator.clipboard.writeText(`{quantity_text}`)"
                style="background-color:#4CAF50;color:white;padding:10px 16px;border:none;border-radius:5px;cursor:pointer;margin-top:10px;">
                📋 一键复制库存列
                </button>
                """, unsafe_allow_html=True)

            # 可选导出 CSV
            df_export = pd.DataFrame({
                "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).str.strip().values,
                "Updated Quantity": result_list
            })
            csv_file = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载为 CSV", data=csv_file, file_name="quantity_column.csv", mime="text/csv")

            if unmatched_skus:
                # 去重并只显示部分
                uniq = []
                seen = set()
                for s in unmatched_skus:
                    if s not in seen:
                        uniq.append(s); seen.add(s)
                st.warning("⚠️ 以下 SKU 未在库存表中找到（Bundle 将按 0 处理；单品已保留原数量）：\n"
                           + "\n".join(uniq[:20]) + ("\n..." if len(uniq) > 20 else ""))

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
