import streamlit as st
import pandas as pd
import re
import tempfile
from xlsx2csv import Xlsx2csv

st.set_page_config(page_title="TikTok库存列生成器", page_icon="💅", layout="wide")
st.title("📋 TikTok Quantity 列生成器（含一键复制）")

st.markdown("""
将 TikTok 模板中的 `Seller SKU` 与库存表中的 `SKU编码` 对应，  
仅生成 `Quantity in U.S Pickup Warehouse` 的数字列，  
📋 可直接 **一键复制**，粘贴回模板中。

本版更新：  
如果单品 SKU 没有在库存表中找到，程序会 **保留 TikTok 原库存**，并在下方清楚列出这些 SKU，方便溯源。
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

    # Bundle 逻辑：比如 ABC001DEF002-M
    if len(code) % 6 == 0 and 6 <= len(code) <= 24:
        parts = [code[i:i + 6] for i in range(0, len(code), 6)]
        if all(re.fullmatch(r"[A-Z]{3}\d{3}", p) for p in parts):
            return [f"{p}-{size}" for p in parts], (len(parts) >= 2)

    return [s], False


# —— 工具：计算库存 —— #
def compute_stock_result(sku_with_size: str, stock_map: dict):
    """
    返回结果：
    computed_qty:
        - 单品匹配成功：库存数字
        - 单品未匹配：""
        - Bundle 缺组件："0"
    action:
        - matched_single
        - unmatched_single_keep_original
        - matched_bundle
        - bundle_missing_set_zero
    """

    skus, is_bundle = split_bundle(sku_with_size)

    # 单品 SKU
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

    # Bundle SKU
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


# —— 主逻辑 —— #
if tiktok_file and inventory_file:
    try:
        # 保存 TikTok Excel 上传文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(tiktok_file.read())
            excel_path = tmp.name

        # 将 Excel 第一页转成 CSV，避免样式 XML 报错
        csv_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        Xlsx2csv(excel_path, outputencoding="utf-8").convert(csv_temp.name)

        # 读取 TikTok 模板
        df_tiktok = pd.read_csv(csv_temp.name, header=None)

        # 自动识别表头
        sku_col = None
        qty_col = None
        product_name_col = None
        header_row_index = None

        for i in range(min(20, len(df_tiktok))):
            row = df_tiktok.iloc[i].astype(str).str.strip()

            if "Seller SKU" in row.values and "Quantity in U.S Pickup Warehouse" in row.values:
                sku_col = row[row == "Seller SKU"].index[0]
                qty_col = row[row == "Quantity in U.S Pickup Warehouse"].index[0]
                header_row_index = i

                # 尝试识别 Product Name
                for idx, val in row.items():
                    val_clean = str(val).strip().lower()
                    if val_clean in [
                        "product name",
                        "product name*",
                        "product title",
                        "product"
                    ]:
                        product_name_col = idx
                        break

                break

        if sku_col is None or qty_col is None:
            st.error("❌ 未找到表头：请确认是否为 TikTok 批量编辑模板。")
            st.stop()

        # 读取库存 CSV
        df_inventory = pd.read_csv(inventory_file)

        if "SKU编码" not in df_inventory.columns or "当前库存" not in df_inventory.columns:
            st.error("❌ 库存文件必须包含 `SKU编码` 和 `当前库存` 两列。")
            st.stop()

        df_inventory["SKU编码"] = df_inventory["SKU编码"].astype(str).str.strip()
        df_inventory["当前库存"] = pd.to_numeric(
            df_inventory["当前库存"],
            errors="coerce"
        ).fillna(0)

        stock_map = dict(zip(df_inventory["SKU编码"], df_inventory["当前库存"]))

        # 找 TikTok 数据开始行
        start_row = header_row_index + 1

        while start_row < len(df_tiktok):
            val = str(df_tiktok.iat[start_row, qty_col]).strip()

            if val.replace(".", "", 1).isdigit() or val == "":
                break

            start_row += 1

        result_list = []

        # 新增：溯源记录
        preserved_original_records = []
        bundle_missing_records = []
        all_unmatched_skus = []

        # 开始逐行匹配
        for i in range(start_row, len(df_tiktok)):
            raw_sku = str(df_tiktok.iat[i, sku_col]).strip()
            original_qty = str(df_tiktok.iat[i, qty_col]).strip()

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

            # 匹配成功 / Bundle 缺组件设为 0
            if computed_qty != "":
                final_qty = computed_qty
            # 单品未匹配，保留原 TikTok qty
            else:
                final_qty = original_qty

            result_list.append(final_qty)

            # 记录：单品未匹配但保留原库存
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

            # 记录：Bundle 缺组件 SKU，设置为 0
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

        # 下载最终库存列
        df_export = pd.DataFrame({
            "SKU": df_tiktok.loc[start_row:, sku_col].astype(str).str.strip().values,
            "Updated Quantity": result_list
        })

        csv_file = df_export.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "📥 下载最终库存列 CSV",
            data=csv_file,
            file_name="quantity_column.csv",
            mime="text/csv",
        )

        st.divider()

        # 显示单品未匹配但保留原库存
        if preserved_original_records:
            st.warning("⚠️ 以下单品 SKU 未匹配，已保留 TikTok 原库存。请重点检查这些 SKU。")

            df_preserved = pd.DataFrame(preserved_original_records)
            st.dataframe(df_preserved, use_container_width=True)

            preserved_csv = df_preserved.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "📥 下载：未匹配且保留原库存的单品 SKU 清单",
                data=preserved_csv,
                file_name="unmatched_single_skus_kept_original_qty.csv",
                mime="text/csv",
            )
        else:
            st.success("✅ 没有发现“单品 SKU 未匹配但保留原库存”的情况。")

        # 显示 Bundle 缺组件 SKU
        if bundle_missing_records:
            st.warning("⚠️ 以下 Bundle SKU 有组件未匹配，程序已按原逻辑将 Bundle 库存设置为 0。")

            df_bundle_missing = pd.DataFrame(bundle_missing_records)
            st.dataframe(df_bundle_missing, use_container_width=True)

            bundle_csv = df_bundle_missing.to_csv(index=False).encode("utf-8-sig")

            st.download_button(
                "📥 下载：Bundle 缺失组件 SKU 清单",
                data=bundle_csv,
                file_name="bundle_missing_component_skus_set_zero.csv",
                mime="text/csv",
            )

        # 所有未匹配 SKU 汇总
        if all_unmatched_skus:
            uniq = list(dict.fromkeys(all_unmatched_skus))

            st.info(
                "📌 所有未在库存表中找到的 SKU 汇总：\n\n" +
                "\n".join(uniq)
            )

    except Exception as e:
        st.error(f"❌ 发生错误：{e}")
