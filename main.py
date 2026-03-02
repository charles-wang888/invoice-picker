# -*- coding: utf-8 -*-
"""
发票凑数神器 - Streamlit Web 应用
用法：python main.py  （将自动启动 Streamlit）
或：streamlit run main.py
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
import time
from typing import List, Optional

import streamlit as st

# 金额 Z：整数或小数点后最多 2 位
Z_AMOUNT_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")


def parse_z_amount(value: str) -> Optional[float]:
    """校验并解析金额 Z，允许整数或最多两位小数；不合法返回 None。"""
    if not value or not value.strip():
        return None
    s = value.strip()
    if not Z_AMOUNT_PATTERN.fullmatch(s):
        return None
    try:
        x = float(s)
        return x if x > 0 else None
    except ValueError:
        return None

from invoice_selector import Invoice, select_invoices, SolverConfig


def parse_invoices_from_upload(uploaded_file) -> List[Invoice]:
    """从上传的文件解析发票列表，每行：发票号码 + 空格 + 金额"""
    invoices = []
    text = uploaded_file.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        code, amount_str = parts[0], parts[1]
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        if amount <= 0:
            continue
        invoices.append(Invoice(id=code, amount=round(amount, 2)))
    return invoices


def run_app():
    def make_solution_csv_bytes(rows: list[dict], target_z: float, total_amount: float, err_pct: float) -> bytes:
        """
        导出 CSV（UTF-8 with BOM，便于 Excel 直接打开）。
        rows: [{"发票编号": str, "面额（元）": float}, ...]
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["发票编号", "面额（元）", "目标金额Z", "汇总金额", "误差率%"])
        for r in rows:
            amt = float(r["面额（元）"])
            writer.writerow(
                [
                    r["发票编号"],
                    f"{amt:.2f}",
                    f"{target_z:.2f}",
                    f"{total_amount:.2f}",
                    f"{err_pct:.6f}",
                ]
            )
        return output.getvalue().encode("utf-8-sig")

    st.set_page_config(page_title="发票凑数神器", page_icon="🧾", layout="wide")
    st.title("🧾 发票凑数神器")
    st.caption("从上传的发票文件中选出指定张数，使总金额 ≥ 目标金额且尽可能接近目标")

    uploaded = st.file_uploader(
        "上传发票数据文件（每行：发票号码 + 空格 + 金额，如 raw_data.txt）",
        type=["txt"],
        accept_multiple_files=False,
    )

    col1, col2 = st.columns(2)
    with col1:
        y = st.number_input(
            "要选出的发票张数 Y",
            min_value=1,
            value=1000,
            step=1,
            help="必须选满 Y 张",
        )
    with col2:
        z_str = st.text_input(
            "要凑的总金额 Z（元）",
            value="1000000",
            placeholder="整数或小数点后最多 2 位，如 345565 或 345565.25",
            help="支持整数或最多两位小数，如 1000000、345565.5",
        )
        z = parse_z_amount(z_str)
        if z_str and z is None:
            st.caption(":red[格式错误：请填写整数或最多两位小数，且大于 0]")

    # 点击「执行」时始终用当前输入（Y、Z、上传文件）重新计算；仅翻页时用缓存
    has_cached = "run_results" in st.session_state
    exec_clicked = st.button("执行", type="primary", key="exec_btn")
    if has_cached:
        if st.button("重新计算", key="clear_btn"):
            for k in list(st.session_state.keys()):
                if k == "run_results" or k == "run_z" or k == "run_elapsed" or k.startswith("page_sol_"):
                    del st.session_state[k]
            st.rerun()
    if not exec_clicked and not has_cached:
        st.stop()

    # 点击「执行」则先清空旧结果，再用当前表单的 Y、Z 重新跑一遍
    if exec_clicked:
        for k in list(st.session_state.keys()):
            if k in ("run_results", "run_z", "run_elapsed") or k.startswith("page_sol_"):
                del st.session_state[k]
        if z is None or z <= 0:
            st.error("请填写有效的目标金额 Z：整数或小数点后最多 2 位，且大于 0")
            st.stop()
        if not uploaded:
            st.error("请先上传发票数据文件（.txt）")
            st.stop()
        with st.spinner("正在解析文件..."):
            try:
                invoices = parse_invoices_from_upload(uploaded)
            except Exception as e:
                st.error(f"解析文件失败：{e}")
                st.stop()
        n = len(invoices)
        if n == 0:
            st.error("未能解析出任何有效发票行，请检查文件格式（每行：发票号码 金额）")
            st.stop()
        if n < y:
            st.error(f"文件中共 {n} 张发票，不足要选出的 Y={y} 张")
            st.stop()
        st.success(f"已加载 {n} 张发票，将选出 {y} 张凑齐目标金额 Z = {z:,.2f} 元")
        # 目标与初始和差距大时多跑几轮，保证能收敛到接近 Z（如凑 43 万 vs 初始约千万）
        estimated_initial = sum(inv.amount for inv in sorted(invoices, key=lambda x: x.amount, reverse=True)[:y])
        gap = max(0, estimated_initial - z)
        max_rounds = max(2000, min(15000, 2000 + int(gap / 500)))
        seeds = [None, 42, 123]
        results = []
        t0 = time.perf_counter()
        progress = st.progress(0, text="正在计算 Top 3 解法（满轮数 + 不同 seed）...")
        for i, seed in enumerate(seeds):
            progress.progress((i + 1) / 3, text=f"计算解法 {i + 1}/3 ...")
            cfg = SolverConfig(
                max_swap_rounds=max_rounds,
                min_improvement=0.01,
                sort_descending=True,
                sort_tie_break_seed=seed,
            )
            res = select_invoices(invoices, select_count=y, target_amount=z, config=cfg)
            if res.is_feasible():
                results.append(res)
        progress.progress(1.0, text="计算完成")
        elapsed = time.perf_counter() - t0
        if not results:
            st.warning("未能得到可行组合（总金额无法达到目标 Z），请减小目标金额或增加可选发票。")
            st.stop()
        seen_keys = set()
        unique_results = []
        for res in results:
            key = tuple(sorted(res.selected_ids))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_results.append(res)
        results = unique_results
        st.session_state["run_results"] = [
            {
                "rows": [{"发票编号": inv.id, "面额（元）": round(inv.amount, 2)} for inv in res.selected],
                "total_amount": res.total_amount,
                "gap": res.gap,
                "target": res.target,
            }
            for res in results
        ]
        st.session_state["run_z"] = z
        st.session_state["run_elapsed"] = elapsed

    if "run_results" not in st.session_state:
        st.stop()
    saved = st.session_state["run_results"]
    run_z = st.session_state["run_z"]
    elapsed = st.session_state["run_elapsed"]
    valid_page_keys = {f"page_sol_{i}" for i in range(1, len(saved) + 1)}
    for k in list(st.session_state.keys()):
        if k.startswith("page_sol_") and k not in valid_page_keys:
            del st.session_state[k]

    st.subheader(f"解法（共 {len(saved)} 种不同组合）")
    page_size = 20
    for idx, data in enumerate(saved, 1):
        rows = data["rows"]
        total_amount = data["total_amount"]
        total_items = len(rows)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        err_pct = (total_amount - run_z) / run_z * 100.0 if run_z > 0 else 0.0

        page_key = f"page_sol_{idx}"
        if page_key not in st.session_state:
            st.session_state[page_key] = 1
        page = st.session_state[page_key]
        page = max(1, min(page, total_pages))
        st.session_state[page_key] = page

        with st.expander(
            f"**解法 {idx}**：汇总 {total_amount:,.2f} 元，误差率 **{err_pct:.4f}%**",
            expanded=(idx == 1),
        ):
            st.markdown(f"- **汇总金额**：{total_amount:,.2f} 元")
            st.markdown(f"- **误差率**：(汇总 − Z) / Z × 100% = **{err_pct:.4f}%**")
            st.markdown(f"- **选中张数**：{total_items} 张")
            st.markdown("---")
            st.markdown("**凑数发票清单（每张编号与面额）**")

            csv_bytes = make_solution_csv_bytes(rows, run_z, total_amount, err_pct)
            st.download_button(
                "导出 CSV（完整清单）",
                data=csv_bytes,
                file_name=f"发票凑数_解法{idx}_Y{total_items}_Z{run_z:.2f}.csv",
                mime="text/csv",
                key=f"dl_csv_{idx}",
            )

            # 分页条：上一页 | 页码列表 1,2,3... | 下一页
            def _page_nums(total_pages: int, current: int, window: int = 5):
                """生成页码列表，当前页附近 + 首尾，中间用 None 表示省略"""
                if total_pages <= window + 2:
                    return list(range(1, total_pages + 1))
                out = [1]
                if current - window // 2 > 2:
                    out.append(None)
                for p in range(max(2, current - window // 2), min(total_pages, current + window // 2 + 1) + 1):
                    if p not in out:
                        out.append(p)
                if current + window // 2 < total_pages - 1:
                    out.append(None)
                if total_pages > 1 and total_pages not in out:
                    out.append(total_pages)
                return out

            col_prev, col_pages, col_next = st.columns([1, 3, 1])
            with col_prev:
                if st.button("上一页", key=f"prev_{idx}", disabled=(page <= 1)):
                    st.session_state[page_key] = max(1, page - 1)
                    st.rerun()
            with col_pages:
                st.caption(f"第 **{page}** / **{total_pages}** 页（共 {total_items} 张，每页 {page_size} 张）")
                page_list = _page_nums(total_pages, page)
                cols = st.columns(len(page_list))
                for i, p in enumerate(page_list):
                    with cols[i]:
                        if p is None:
                            st.write("…")
                        else:
                            if st.button(str(p), key=f"page_{idx}_{p}", disabled=(p == page)):
                                st.session_state[page_key] = p
                                st.rerun()
            with col_next:
                if st.button("下一页", key=f"next_{idx}", disabled=(page >= total_pages)):
                    st.session_state[page_key] = min(total_pages, page + 1)
                    st.rerun()

            start = (page - 1) * page_size
            end = start + page_size
            st.dataframe(
                rows[start:end],
                use_container_width=True,
                hide_index=True,
                column_config={"面额（元）": st.column_config.NumberColumn(format="%.2f")},
            )

    st.metric("整体运行时长", f"{elapsed:.2f} 秒")


if __name__ == "__main__":
    # 用 main.py 启动：由子进程设 STREAMLIT_LAUNCHED，避免父进程误跑 run_app
    if os.environ.get("STREAMLIT_LAUNCHED"):
        run_app()
    else:
        env = os.environ.copy()
        env["STREAMLIT_LAUNCHED"] = "1"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                __file__,
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            env=env,
            check=True,
        )
