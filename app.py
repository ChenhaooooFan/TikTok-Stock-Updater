import streamlit as st
import pandas as pd
import re
import tempfile
from xlsx2csv import Xlsx2csv

st.set_page_config(page_title="TikTok库存列生成器", page_icon="💅", layout="wide")
st.title("📋 TikTok Quantity 列生成器（含一键复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，
仅生成 `Quantity in Pick Up Warehouse`（模板 U 列）的数字列，
📋 可直接 **一键复制**，粘贴回模板中。

本版更新：
如果单品 SKU 没有在库存表中找到，程序会 **保留 TikTok 原库存**，并在下方清楚列出这些 SKU，方便溯源。
""")

tiktok_file = st.file_uploader("📤 上传 TikTok 批量编辑模板（Excel）", type=["xlsx"])
inventory_file = st.file_uploader("📤 上传库存文件（CSV）", type=["csv"])


# 清洗不可见字符（零宽空格等）
def clean_sku(s: str) -> str:
    return (
        str(s)
        .strip()
        .replace('​', '')
        .replace('‌', '')
        .replace('‍', '')
        .replace('﻿', '')
    )


# 单元格转字符串，空单元格（NaN）返回 ""
def cell_str(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


# Bundle 拆分
def split_bundle(sku_with_size: str):
    s = clean_sku(sku_with_size)

    if "-" not in s:
        return [s], False

    code, size = s.split("-", 1)
    code = code.strip()
    size = size.strip()

    if len(code) % 6 == 0 and 6 <= len(code) <= 24:
        parts = [code[i:i + 6] for i in range(0, len(code), 6)]
        if all(re.fullmatch(r"[A-Z]{3}\d{3}", p) for p in parts):
            return [f"{p}-{size}" for p in parts], (len(parts) >= 2)

    return [s], False


# 计算库存
def compute_stock_result(sku_with_size: str, stock_map: dict):
    skus, is_bundle = split_bundle(sku_with_size)

    if not is_bundle:
        sku = skus[0]
        if sku in stock_map:
            return {
                "computed_qty": str(int(stock_map[sku])),
                "is_bundle": False,
                "missing_skus": [],
                "matched_skus": [sku],
                "action": "matched_single"
            }
        return {
            "computed_qty": "",
            "is_bundle": False,
            "missing_skus": [sku],
            "matched_skus": [],
            "action": "unmatched_single_keep_original"
        }

    missing = [k for k in skus if k not in stock_map]
    if missing:
        return {
            "computed_qty": "0",
            "is_bundle": True,
            "missing_skus": missing,
            "matched_skus": [k for k in skus if k in stock_map],
            "action": "bundle_missing_set_zero"
        }

    return {
        "computed_qty": str(min(int(stock_map[k]) for k in skus)),
        "is_bundle": True,
        "missing_skus": [],
        "matched_skus": skus,
        "action": "matched_bundle"
    }


# 主逻辑
if tiktok_file and inventory_file:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(tiktok_file.read())
            excel_path = tmp.name

        csv_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        Xlsx2csv(excel_path, outputencoding="utf-8").convert(csv_temp.name)

        df_tiktok = pd.read_csv(csv_temp.name, header=None)

        sku_col = None
        qty_col = None
        product_name_col = None
        header_row_index = None

        for i in range(min(20, len(df_tiktok))):
            row = df_tiktok.iloc[i].astype(str).str.strip()
            if "Seller SKU" in row.values and "Quantity in Pick Up Warehouse" in row.values:
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in Pick Up Warehouse"].index[0]
                header_row_index = i
                for idx, val in row.items():
                    if str(val).strip().lower() in ["product name", "product name*", "product title", "product"]:
                        product_name_col = idx
                        break
                break

        if sku_col is None or qty_col is None:
            st.error("❌ 未找到表头 `Seller SKU` / `Quantity in Pick Up Warehouse`：请确认是否为 TikTok 批量编辑模板。")
            st.stop()

        df_inventory = pd.read_csv(inventory_file)

        if "SKU编码" not in df_inventory.columns or "当前库存" not in df_inventory.columns:
            st.error("❌ 库存文件必须包含 `SKU编码` 和 `当前库存` 两列。")
            st.stop()

        df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).apply(clean_sku)
        df_inventory["当前库存"] = pd.to_numeric(df_inventory["当前库存"], errors="coerce").fillna(0)
        stock_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

        start_row = header_row_index + 1
        while start_row < len(df_tiktok):
            val = cell_str(df_tiktok.iat[start_row, qty_col])
            if val.replace(".", "", 1).isdigit() or val == "":
                break
            start_row += 1

        result_list = []
        preserved_original_records = []
        bundle_missing_records = []
        all_unmatched_skus = []

        for i in range(start_row, len(df_tiktok)):
            raw_sku = clean_sku(df_tiktok.iat[i, sku_col])
            original_qty = cell_str(df_tiktok.iat[i, qty_col])

            if raw_sku == "" or raw_sku.lower() == "nan":
                result_list.append(original_qty)
                continue

            product_name = ""
            if product_name_col is not None:
                product_name = str(df_tiktok.iat[i, product_name_col]).strip()
                if product_name.lower() == "nan":
                    product_name = ""

            result = compute_stock_result(raw_sku, stock_map)
            computed_qty = result["computed_qty"]
            final_qty = computed_qty if computed_qty != "" else original_qty
            result_list.append(final_qty)

            if result["action"] == "unmatched_single_keep_original":
                all_unmatched_skus.extend(result["missing_skus"])
                preserved_original_records.append({
                    "Excel Row": i + 1,
                    "Product Name": product_name,
                    "Seller SKU": raw_sku,
                    "Original Quantity Kept": original_qty,
                    "Final Quantity": final_qty,
                    "Reason": "SKU not found in inventory file, original TikTok quantity kept"
                })

            if result["action"] == "bundle_missing_set_zero":
                all_unmatched_skus.extend(result["missing_skus"])
                bundle_missing_records.append({
                    "Excel Row": i + 1,
                    "Product Name": product_name,
                    "Bundle Seller SKU": raw_sku,
                    "Missing Component SKUs": ", ".join(result["missing_skus"]),
                    "Original Quantity": original_qty,
                    "Final Quantity": final_qty,
                    "Reason": "Bundle component SKU missing in inventory file, quantity set to 0"
                })

        output_text = "\n".join(result_list)

        st.success("✅ 匹配完成！点击下方按钮复制整个库存列：")
        st.code(output_text, language="text")
        st.markdown(
            f"""
            <button onclick="navigator.clipboard.writeText(`{output_text}`)"
            style="
                background-color:#4CAF50;
                color:white;
                padding:10px 16px;
                border:none;
                border-radius:5px;
                cursor:pointer;
                margin-top:10px;
            ">
            📋 一键复制库存列
            </button>
            """,
            unsafe_allow_html=True,
        )

        df_export = pd.DataFrame({
            "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).apply(clean_sku).values,
            "Updated Quantity": result_list
        })
        st.download_button(
            "📥 下载最终库存列 CSV",
            data=df_export.to_csv(index=False).encode("utf-8-sig"),
            file_name="quantity_column.csv",
            mime="text/csv",
        )

        st.divider()

        if preserved_original_records:
            st.warning("⚠️ 以下单品 SKU 未匹配，已保留 TikTok 原库存。请重点检查这些 SKU。")
            df_preserved = pd.DataFrame(preserved_original_records)
            st.dataframe(df_preserved, use_container_width=True)
            st.download_button(
                "📥 下载：未匹配且保留原库存的单品 SKU 清单",
                data=df_preserved.to_csv(index=False).encode("utf-8-sig"),
                file_name="unmatched_single_skus_kept_original_qty.csv",
                mime="text/csv",
            )
        else:
            st.success('✅ 没有发现"单品 SKU 未匹配但保留原库存"的情况。')

        if bundle_missing_records:
            st.warning("⚠️ 以下 Bundle SKU 有组件未匹配，程序已按原逻辑将 Bundle 库存设置为 0。")
            df_bundle_missing = pd.DataFrame(bundle_missing_records)
            st.dataframe(df_bundle_missing, use_container_width=True)
            st.download_button(
                "📥 下载：Bundle 缺失组件 SKU 清单",
                data=df_bundle_missing.to_csv(index=False).encode("utf-8-sig"),
                file_name="bundle_missing_component_skus_set_zero.csv",
                mime="text/csv",
            )

        if all_unmatched_skus:
            uniq = list(dict.fromkeys(all_unmatched_skus))
            st.info("📌 所有未在库存表中找到的 SKU 汇总：")
            st.code("\n".join(uniq), language="text")

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
