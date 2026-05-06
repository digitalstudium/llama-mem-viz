#!/usr/bin/env python3
"""
llama-mem-diff.py — professional visual diff between two llama-mem-viz runs
Shows difference in ALL important flags: -ngl, -ncmoe, -ub, -fa, -ctk, -ctv, etc.
Memory breakdown shows VRAM, RAM, and Total separately.
"""

import json
import sys
import shutil
import re

USE_COLOR = sys.stdout.isatty()

RESET  = "\033[0m" if USE_COLOR else ""
BOLD   = "\033[1m" if USE_COLOR else ""
DIM    = "\033[2m" if USE_COLOR else ""
RED    = "\033[31m" if USE_COLOR else ""
GREEN  = "\033[32m" if USE_COLOR else ""
CYAN   = "\033[36m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
GRAY   = "\033[90m" if USE_COLOR else ""

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_cli_args(cli_args: str) -> dict:
    if cli_args == "N/A":
        return {}
    args = {}
    patterns = {
        "ngl": r"-ngl\s+(\d+)",
        "ncmoe": r"-ncmoe\s+(\d+)",
        "ub": r"-ub\s+(\d+)",
        "fa": r"-fa\s+(on|off)",
        "ctk": r"-ctk\s+(\w+)",
        "ctv": r"-ctv\s+(\w+)",
        "t": r"-t\s+(\d+)",
        "np": r"-np\s+(\d+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, cli_args)
        if match:
            args[key] = match.group(1)
    return args

def model_meta_lines(data: dict) -> list[str]:
    info = data.get("model", {}) or {}
    cli_args = data.get("cli_args", "N/A")
    parsed = parse_cli_args(cli_args)

    name = info.get("name", "N/A")
    arch = info.get("arch", "N/A")
    quant = info.get("file_type", "N/A")
    ctx = info.get("ctx", "N/A")
    offloaded = info.get("layers_offloaded", "N/A")
    total_layers = info.get("layers_total", "N/A")
    status = "ready" if data.get("status", {}).get("server_ready") else "failed"

    lines = [
        f"Model:      {name}",
        f"Arch:       {arch} ({quant})",
        f"Context:    {ctx}",
        f"GPU layers: {offloaded}/{total_layers}",
        f"Status:     {status}",
    ]

    if parsed:
        lines += [
            f"ngl:        {parsed.get('ngl', 'N/A')}",
            f"ncmoe:      {parsed.get('ncmoe', 'N/A')}",
            f"ub:         {parsed.get('ub', 'N/A')}",
            f"fa:         {parsed.get('fa', 'N/A')}",
            f"ctk/ctv:    {parsed.get('ctk', 'N/A')}/{parsed.get('ctv', 'N/A')}",
        ]

    return lines

def fmt_mem(mib: float) -> str:
    if abs(mib) >= 1024:
        return f"{mib/1024:.2f} GiB"
    return f"{mib:.2f} MiB"

def draw_bar(used: float, cap: float, width: int = 40) -> str:
    if not cap:
        return "░" * width
    ratio = min(1.0, used / cap)
    filled = round(ratio * width)
    return f"{CYAN}{'█' * filled}{RESET}{DIM}{'░' * (width - filled)}{RESET}"

def visual_len(s: str) -> int:
    return len(re.sub(r'\033\[[0-9;]*m', '', s))

def pad_to(s: str, width: int) -> str:
    vl = visual_len(s)
    if vl >= width:
        return s
    return s + " " * (width - vl)

def fmt_diff(va: float, vb: float) -> str:
    diff = vb - va
    diff_pct = f"({diff/va*100:+.1f}%)" if va > 0 else ""
    if abs(diff) < 0.01:
        return f"{DIM}── no change{RESET}"
    elif diff < 0:
        return f"{GREEN}▼ {fmt_mem(diff)} {diff_pct}{RESET}"
    else:
        return f"{RED}▲ +{fmt_mem(diff)} {diff_pct}{RESET}"

def main():
    if len(sys.argv) != 3:
        print("Usage: ./llama-mem-diff.py a.json b.json")
        sys.exit(1)

    a = load_json(sys.argv[1])
    b = load_json(sys.argv[2])

    term_width = max(100, shutil.get_terminal_size((120, 40)).columns)
    cell_w = (term_width - 3) // 2

    title = " LLAMA.CPP MEMORY DIFF "
    print(f"\n{CYAN}{'═' * ((term_width - len(title)) // 2)}{RESET}{BOLD}{title}{RESET}{CYAN}{'═' * ((term_width - len(title)) // 2)}{RESET}\n")

    # ── Row 1: Run A | Run B ──
    lines_a = [f" {BOLD}{CYAN}RUN A{RESET}"] + [f" {l}" for l in model_meta_lines(a)]
    lines_b = [f" {BOLD}{YELLOW}RUN B{RESET}"] + [f" {l}" for l in model_meta_lines(b)]

    max_r1 = max(len(lines_a), len(lines_b))
    lines_a += [""] * (max_r1 - len(lines_a))
    lines_b += [""] * (max_r1 - len(lines_b))

    # ── Row 2: OVERVIEW | MEMORY BREAKDOWN ──
    bar_w = max(10, cell_w - 22)

    lines_vram = [f" {BOLD}OVERVIEW{RESET}", ""]
    for pool in ["VRAM", "RAM"]:
        t1 = a["allocated"][pool]["total_mib"]
        t2 = b["allocated"][pool]["total_mib"]
        cap = max(a["allocated"][pool].get("capacity_mib", 0),
                  b["allocated"][pool].get("capacity_mib", 0))
        diff = t2 - t1

        bar1 = draw_bar(t1, cap, width=bar_w)
        bar2 = draw_bar(t2, cap, width=bar_w)

        if diff < 0:
            diff_str = f"{GREEN}▼ {fmt_mem(diff)} (-{abs(diff/t1)*100:.1f}%){RESET}" if t1 > 0 else f"{GREEN}▼ {fmt_mem(diff)}{RESET}"
        elif diff > 0:
            diff_str = f"{RED}▲ +{fmt_mem(diff)} (+{diff/t1*100:.1f}%){RESET}" if t1 > 0 else f"{RED}▲ +{fmt_mem(diff)}{RESET}"
        else:
            diff_str = f"{DIM}no change{RESET}"

        lines_vram.append(f" {BOLD}{pool}{RESET}")
        lines_vram.append(f"  A:[{bar1}] {fmt_mem(t1)}")
        lines_vram.append(f"  B:[{bar2}] {fmt_mem(t2)}")
        lines_vram.append(f"  Δ: {diff_str}")
        lines_vram.append("")

    # ── Memory breakdown: VRAM / RAM / Total per component ──
    lines_comp = [f" {BOLD}MEMORY BREAKDOWN{RESET}", ""]

    comps = ["weights", "kv_cache", "prompt_cache", "recurrent_state", "compute_pp", "compute"]
    for comp in comps:
        va_vram = a["allocated"]["VRAM"]["components_mib"].get(comp, 0)
        va_ram  = a["allocated"]["RAM"]["components_mib"].get(comp, 0)
        vb_vram = b["allocated"]["VRAM"]["components_mib"].get(comp, 0)
        vb_ram  = b["allocated"]["RAM"]["components_mib"].get(comp, 0)

        va_total = va_vram + va_ram
        vb_total = vb_vram + vb_ram

        if va_total == 0 and vb_total == 0:
            continue

        lines_comp.append(f"  {BOLD}● {comp}{RESET}")

        for label, va, vb in [("VRAM", va_vram, vb_vram),
                               ("RAM",  va_ram,  vb_ram),
                               ("Total", va_total, vb_total)]:
            if va == 0 and vb == 0:
                continue
            diff_line = fmt_diff(va, vb)
            lines_comp.append(f"    {label.ljust(6)} {fmt_mem(va)} → {fmt_mem(vb)}  {diff_line}")

        lines_comp.append("")

    # ── Total summary: VRAM / RAM / Total ──
    total_a_vram = a["allocated"]["VRAM"]["total_mib"]
    total_a_ram  = a["allocated"]["RAM"]["total_mib"]
    total_b_vram = b["allocated"]["VRAM"]["total_mib"]
    total_b_ram  = b["allocated"]["RAM"]["total_mib"]
    total_a = a["grand_total_mib"]
    total_b = b["grand_total_mib"]

    lines_comp.append(f" {BOLD}TOTAL MEMORY{RESET}")
    lines_comp.append("")

    for label, ta, tb in [("VRAM", total_a_vram, total_b_vram),
                           ("RAM",  total_a_ram,  total_b_ram),
                           ("Total", total_a, total_b)]:
        diff = tb - ta
        diff_color = GREEN if diff < 0 else (RED if diff > 0 else DIM)
        diff_pct = f"({diff/ta*100:+.1f}%)" if ta > 0 else ""
        if abs(diff) < 0.01:
            lines_comp.append(f"  {DIM}{label.ljust(6)} {fmt_mem(ta)}  ── no change{RESET}")
        else:
            lines_comp.append(f"  {label.ljust(6)} {fmt_mem(ta)} → {fmt_mem(tb)}  {diff_color}{fmt_mem(diff)} {diff_pct}{RESET}")

    max_r2 = max(len(lines_vram), len(lines_comp))
    lines_vram += [""] * (max_r2 - len(lines_vram))
    lines_comp += [""] * (max_r2 - len(lines_comp))

    # ── Draw grid ──
    top = "┌" + "─" * cell_w + "┬" + "─" * cell_w + "┐"
    mid = "├" + "─" * cell_w + "┼" + "─" * cell_w + "┤"
    bot = "└" + "─" * cell_w + "┴" + "─" * cell_w + "┘"

    print(top)
    for la, lb in zip(lines_a, lines_b):
        print(f"│{pad_to(la, cell_w)}│{pad_to(lb, cell_w)}│")
    print(mid)
    for lv, lc in zip(lines_vram, lines_comp):
        print(f"│{pad_to(lv, cell_w)}│{pad_to(lc, cell_w)}│")
    print(bot)

    print(f"{DIM}{'═' * term_width}{RESET}\n")

if __name__ == "__main__":
    main()
