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

def extract_meta(data: dict) -> dict:
    """Извлекает чистые параметры для сравнения."""
    info = data.get("model", {}) or {}
    cli_args = data.get("cli_args", "N/A")
    parsed = parse_cli_args(cli_args)
    
    return {
        "name": info.get("name", "N/A"),
        "arch": info.get("arch", "N/A"),
        "quant": info.get("file_type", "N/A"),
        "ctx": str(info.get("ctx", "N/A")),
        "offloaded": str(info.get("layers_offloaded", "N/A")),
        "total_layers": str(info.get("layers_total", "N/A")),
        "status": "ready" if data.get("status", {}).get("server_ready") else "failed",
        "ngl": parsed.get("ngl", "N/A"),
        "ncmoe": parsed.get("ncmoe", "N/A"),
        "ub": parsed.get("ub", "N/A"),
        "fa": parsed.get("fa", "N/A"),
        "ctk": parsed.get("ctk", "N/A"),
        "ctv": parsed.get("ctv", "N/A"),
    }

def generate_meta_rows(a: dict, b: dict) -> tuple[list[str], list[str]]:
    """Генерирует списки строк для левой и правой колонок с подсветкой различий."""
    meta_a = extract_meta(a)
    meta_b = extract_meta(b)

    lines_a = [f" {BOLD}{CYAN}RUN A{RESET}"]
    lines_b = [f" {BOLD}{YELLOW}RUN B{RESET}"]

    def add_compared_line(label: str, val_a: str, val_b: str, is_status: bool = False):
        if is_status:
            # Специфический статус-контроль (failed -> красный, ready -> зеленый)
            formatted_a = f"{GREEN}{BOLD}{val_a}{RESET}" if val_a == "ready" else f"{RED}{BOLD}{val_a}{RESET}"
            formatted_b = f"{GREEN}{BOLD}{val_b}{RESET}" if val_b == "ready" else f"{RED}{BOLD}{val_b}{RESET}"
        else:
            # Если значения отличаются, подсвечиваем их желтым цветом
            if val_a != val_b:
                formatted_a = f"{YELLOW}{BOLD}{val_a}{RESET}"
                formatted_b = f"{YELLOW}{BOLD}{val_b}{RESET}"
            else:
                formatted_a = val_a
                formatted_b = val_b

        lines_a.append(f" {label:<12} {formatted_a}")
        lines_b.append(f" {label:<12} {formatted_b}")

    # Сравнение базовой информации
    add_compared_line("Model:", meta_a["name"], meta_b["name"])
    
    arch_a = f"{meta_a['arch']} ({meta_a['quant']})"
    arch_b = f"{meta_b['arch']} ({meta_b['quant']})"
    add_compared_line("Arch:", arch_a, arch_b)
    
    add_compared_line("Context:", meta_a["ctx"], meta_b["ctx"])
    
    gpu_a = f"{meta_a['offloaded']}/{meta_a['total_layers']}"
    gpu_b = f"{meta_b['offloaded']}/{meta_b['total_layers']}"
    add_compared_line("GPU layers:", gpu_a, gpu_b)
    
    # Статус выводим с флагом is_status=True
    add_compared_line("Status:", meta_a["status"], meta_b["status"], is_status=True)

    # Разделитель перед параметрами запуска
    lines_a.append("")
    lines_b.append("")

    # Сравнение CLI флагов
    for flag in ["ngl", "ncmoe", "ub", "fa"]:
        add_compared_line(f"{flag}:", meta_a[flag], meta_b[flag])

    ctk_ctv_a = f"{meta_a['ctk']}/{meta_a['ctv']}"
    ctk_ctv_b = f"{meta_b['ctk']}/{meta_b['ctv']}"
    add_compared_line("ctk/ctv:", ctk_ctv_a, ctk_ctv_b)

    return lines_a, lines_b

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
    lines_a, lines_b = generate_meta_rows(a, b)

    max_r1 = max(len(lines_a), len(lines_b))
    lines_a += [""] * (max_r1 - len(lines_a))
    lines_b += [""] * (max_r1 - len(lines_b))

    # ── Row 2: MEMORY OVERVIEW | MEMORY BREAKDOWN ──
    bar_w = max(10, cell_w - 22)

    lines_vram = [f" {BOLD}MEMORY OVERVIEW{RESET}", ""]
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

    # Total memory
    total_a = a["grand_total_mib"]
    total_b = b["grand_total_mib"]
    total_cap = (
        max(a["allocated"]["VRAM"].get("capacity_mib", 0), b["allocated"]["VRAM"].get("capacity_mib", 0)) +
        max(a["allocated"]["RAM"].get("capacity_mib", 0), b["allocated"]["RAM"].get("capacity_mib", 0))
    )
    diff = total_b - total_a

    bar1 = draw_bar(total_a, total_cap, width=bar_w)
    bar2 = draw_bar(total_b, total_cap, width=bar_w)

    if diff < 0:
        diff_str = f"{GREEN}▼ {fmt_mem(diff)} (-{abs(diff/total_a)*100:.1f}%){RESET}" if total_a > 0 else f"{GREEN}▼ {fmt_mem(diff)}{RESET}"
    elif diff > 0:
        diff_str = f"{RED}▲ +{fmt_mem(diff)} (+{diff/total_a*100:.1f}%){RESET}" if total_a > 0 else f"{RED}▲ +{fmt_mem(diff)}{RESET}"
    else:
        diff_str = f"{DIM}no change{RESET}"

    lines_vram.append(f" {BOLD}Total{RESET}")
    lines_vram.append(f"  A:[{bar1}] {fmt_mem(total_a)}")
    lines_vram.append(f"  B:[{bar2}] {fmt_mem(total_b)}")
    lines_vram.append(f"  Δ: {diff_str}")
    lines_vram.append("")

    # ── Memory breakdown ──
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
            diff_line = fmt_diff(va, vb)
            if label == "Total":
                colored_diff = diff_line.replace(RESET, CYAN)
                lines_comp.append(f"    {CYAN}Total {RESET}{CYAN}{fmt_mem(va)} → {fmt_mem(vb)}  {colored_diff}{RESET}")
            else:
                lines_comp.append(f"    {label.ljust(6)} {fmt_mem(va)} → {fmt_mem(vb)}  {diff_line}")

        lines_comp.append("")

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
