#!/usr/bin/env python3
"""
llama-mem-diff.py — professional visual diff between two llama-mem-viz runs
Shows difference in ALL important flags: -ngl, -ncmoe, -ub, -fa, -ctk, -ctv, etc.
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

def diff_flag(a: str, b: str, flag_name: str) -> str:
    if a == b:
        return f"{a}"
    return f"{RED}{a}{RESET} → {GREEN}{b}{RESET}"

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

def main():
    if len(sys.argv) != 3:
        print("Usage: ./llama-mem-diff.py a.json b.json")
        sys.exit(1)

    a = load_json(sys.argv[1])
    b = load_json(sys.argv[2])

    term_width = max(88, shutil.get_terminal_size((120, 40)).columns)
    title = " LLAMA.CPP MEMORY DIFF "
    print(f"\n{CYAN}{'═' * ((term_width - len(title)) // 2)}{RESET}{BOLD}{title}{RESET}{CYAN}{'═' * ((term_width - len(title)) // 2)}{RESET}\n")

    # Side-by-side config
    meta_a = model_meta_lines(a)
    meta_b = model_meta_lines(b)

    box_w = (term_width - 6) // 2
    print(f"┌─ {BOLD}{CYAN}RUN A{RESET} {'─' * (box_w - 10)}┐   ┌─ {BOLD}{YELLOW}RUN B{RESET} {'─' * (box_w - 10)}┐")
    for la, lb in zip(meta_a, meta_b):
        la = la[:box_w-4].ljust(box_w-4)
        lb = lb[:box_w-4].ljust(box_w-4)
        print(f"│ {la} │   │ {lb} │")
    print(f"└{'─' * (box_w - 2)}┘   └{'─' * (box_w - 2)}┘")

    # Memory pools
    for pool in ["VRAM", "RAM"]:
        t1 = a["allocated"][pool]["total_mib"]
        t2 = b["allocated"][pool]["total_mib"]
        cap = max(a["allocated"][pool].get("capacity_mib", 0), b["allocated"][pool].get("capacity_mib", 0))
        diff = t2 - t1

        bar1 = draw_bar(t1, cap)
        bar2 = draw_bar(t2, cap)

        diff_str = f"{GREEN}▼ {fmt_mem(diff)} (-{abs(diff/t1)*100:.1f}%)" if diff < 0 else f"{RED}▲ +{fmt_mem(diff)} (+{diff/t1*100:.1f}%)" if t1 > 0 else f"{RED}▲ +{fmt_mem(diff)}"

        print(f"\n{BOLD}{pool} OVERVIEW{RESET}")
        print(f"  A: [{bar1}] {fmt_mem(t1):>11}")
        print(f"  B: [{bar2}] {fmt_mem(t2):>11}")
        print(f"  Δ: {diff_str}")

    # Component diff
    print(f"\n{DIM}{'─' * term_width}{RESET}")
    print(f"{BOLD}{'COMPONENT BREAKDOWN':^{term_width}}{RESET}")
    print(f"{DIM}{'─' * term_width}{RESET}")

    comps = ["weights", "kv_cache", "prompt_cache", "recurrent_state", "compute_pp", "compute"]
    for comp in comps:
        va = a["allocated"]["VRAM"]["components_mib"].get(comp, 0) + a["allocated"]["RAM"]["components_mib"].get(comp, 0)
        vb = b["allocated"]["VRAM"]["components_mib"].get(comp, 0) + b["allocated"]["RAM"]["components_mib"].get(comp, 0)
        if va == 0 and vb == 0:
            continue

        diff = vb - va
        diff_pct = f"({diff/va*100:+.1f}%)" if va > 0 else ""
        
        if abs(diff) < 0.01:
            # No change → dim the entire line
            label = f"{DIM} ● {comp.ljust(15)} A: {fmt_mem(va):>10} → B: {fmt_mem(vb):>10} → no change{RESET}"
            print(label)
        elif diff < 0:
            print(f" ● {comp.ljust(15)} A: {fmt_mem(va):>10} → B: {fmt_mem(vb):>10} → {GREEN}▼ {fmt_mem(diff)} {diff_pct}{RESET}")
        else:
            print(f" ● {comp.ljust(15)} A: {fmt_mem(va):>10} → B: {fmt_mem(vb):>10} → {RED}▲ +{fmt_mem(diff)} {diff_pct}{RESET}")

    # Total
    total_a = a["grand_total_mib"]
    total_b = b["grand_total_mib"]
    total_diff = total_b - total_a
    print(f"\n{BOLD}TOTAL MEMORY USAGE{RESET}")
    print(f"  A: {fmt_mem(total_a)}")
    print(f"  B: {fmt_mem(total_b)}")
    diff_color = GREEN if total_diff < 0 else RED
    print(f"  Δ: {diff_color}{fmt_mem(total_diff)} ({total_diff/total_a*100:+.1f}%){RESET}")
    print(f"{DIM}{'═' * term_width}{RESET}\n")

if __name__ == "__main__":
    main()
