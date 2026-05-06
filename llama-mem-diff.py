#!/usr/bin/env python3
"""
llama-mem-diff.py — colored visual diff for two llama-mem-viz.py JSON reports.
"""

import json
import sys
import shutil
import re


USE_COLOR = sys.stdout.isatty()

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

RED    = "\033[31m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
GRAY   = "\033[90m"


def color(code: str) -> str:
    return code if USE_COLOR else ""


RESET  = color(RESET)
BOLD   = color(BOLD)
DIM    = color(DIM)
RED    = color(RED)
GREEN  = color(GREEN)
CYAN   = color(CYAN)
YELLOW = color(YELLOW)
GRAY   = color(GRAY)


COMPONENT_ORDER = [
    "weights",
    "kv_cache",
    "prompt_cache",
    "recurrent_state",
    "compute_pp",
    "compute",
]

COMPONENT_LABELS = {
    "weights":         "Weights",
    "kv_cache":        "KV Cache",
    "prompt_cache":    "Prompt Cache",
    "recurrent_state": "RS State",
    "compute_pp":      "Compute PP",
    "compute":         "Compute",
}


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def visible_len(s: str) -> int:
    return len(strip_ansi(s))


def pad_visible(s: str, width: int) -> str:
    return s + " " * max(0, width - visible_len(s))


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_mem(mib: float, short: bool = False, signed: bool = False) -> str:
    sign = ""
    if signed:
        if mib > 0:
            sign = "+"
        elif mib < 0:
            sign = "-"

    v = abs(mib) if signed else mib

    if abs(v) >= 1024:
        return f"{sign}{v / 1024:.2f} GiB" if not short else f"{sign}{v / 1024:.1f}G"

    return f"{sign}{v:.2f} MiB" if not short else f"{sign}{int(v)}M"


def pct_change(old: float, new: float) -> float | None:
    if abs(old) < 0.0001:
        if abs(new) < 0.0001:
            return 0.0
        return None
    return (new - old) / old * 100.0


def draw_bar(used: float, cap: float, width: int = 30, bar_color: str = CYAN) -> str:
    if not cap or cap <= 0:
        return f"{DIM}{'░' * width}{RESET}"

    ratio = min(1.0, max(0.0, used / cap))
    filled = round(ratio * width)
    empty = width - filled

    return f"{bar_color}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"


def draw_mini_bar(value: float, max_value: float, width: int = 12, bar_color: str = CYAN) -> str:
    if max_value <= 0:
        return f"{DIM}{'░' * width}{RESET}"

    ratio = min(1.0, max(0.0, value / max_value))
    filled = round(ratio * width)
    empty = width - filled

    return f"{bar_color}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"


def get_alloc(data: dict, pool: str) -> dict:
    return data.get("allocated", {}).get(pool, {}) or {}


def get_components(data: dict, pool: str) -> dict:
    return get_alloc(data, pool).get("components_mib", {}) or {}


def get_total(data: dict, pool: str) -> float:
    return float(get_alloc(data, pool).get("total_mib") or 0.0)


def get_capacity(data: dict, pool: str) -> float:
    return float(get_alloc(data, pool).get("capacity_mib") or 0.0)


def get_grand_total(data: dict) -> float:
    return float(data.get("grand_total_mib") or 0.0)


def model_meta_lines(data: dict) -> list[str]:
    info = data.get("model", {}) or {}
    status = data.get("status", {}) or {}

    name = info.get("name", "N/A")
    arch = info.get("arch", "N/A")
    quant = info.get("file_type", "N/A")
    ctx = info.get("ctx", "N/A")
    seqs = info.get("n_seq_max", "N/A")

    offloaded = info.get("layers_offloaded", "N/A")
    total_layers = info.get("layers_total", "N/A")

    oom = bool(status.get("oom"))
    ready = status.get("server_ready")
    exit_code = status.get("exit_code")

    if oom:
        run_status = f"OOM / failed"
    elif ready:
        run_status = f"ready"
    else:
        run_status = f"exit={exit_code}"

    return [
        f"Model:      {name}",
        f"Arch:       {arch}",
        f"Quant:      {quant}",
        f"Context:    {ctx}",
        f"Sequences:  {seqs}",
        f"GPU layers: {offloaded} / {total_layers}",
        f"Status:     {run_status}",
    ]


def print_side_by_side_meta(data_a: dict, data_b: dict, term_width: int) -> None:
    left_title = f"{BOLD}{CYAN}RUN A{RESET}"
    right_title = f"{BOLD}{YELLOW}RUN B{RESET}"

    gap = 3
    box_w = max(38, (term_width - gap) // 2)
    box_w = min(box_w, 68)

    lines_a = model_meta_lines(data_a)
    lines_b = model_meta_lines(data_b)
    max_lines = max(len(lines_a), len(lines_b))

    lines_a += [""] * (max_lines - len(lines_a))
    lines_b += [""] * (max_lines - len(lines_b))

    print(
        f"┌─ {left_title} "
        f"{'─' * max(0, box_w - visible_len(left_title) - 4)}┐"
        f"{' ' * gap}"
        f"┌─ {right_title} "
        f"{'─' * max(0, box_w - visible_len(right_title) - 4)}┐"
    )

    for la, lb in zip(lines_a, lines_b):
        la = la[: box_w - 4]
        lb = lb[: box_w - 4]
        print(
            f"│ {la.ljust(box_w - 4)} │"
            f"{' ' * gap}"
            f"│ {lb.ljust(box_w - 4)} │"
        )

    print(
        f"└{'─' * (box_w - 2)}┘"
        f"{' ' * gap}"
        f"└{'─' * (box_w - 2)}┘"
    )


def diff_text(old: float, new: float) -> str:
    diff = new - old

    if abs(diff) < 0.01:
        return f"{DIM}no change{RESET}"

    pct = pct_change(old, new)

    if diff > 0:
        if pct is None:
            return f"{RED}▲ {fmt_mem(diff, signed=True)}{RESET}"
        return f"{RED}▲ {fmt_mem(diff, signed=True)} ({pct:+.1f}%){RESET}"

    if pct is None:
        return f"{GREEN}▼ {fmt_mem(diff, signed=True)}{RESET}"

    return f"{GREEN}▼ {fmt_mem(diff, signed=True)} ({pct:+.1f}%){RESET}"


def print_pool_overview(data_a: dict, data_b: dict, term_width: int) -> None:
    for pool in ["VRAM", "RAM"]:
        total_a = get_total(data_a, pool)
        total_b = get_total(data_b, pool)

        cap_a = get_capacity(data_a, pool)
        cap_b = get_capacity(data_b, pool)
        cap = max(cap_a, cap_b)

        bar_w = min(42, max(24, term_width - 64))

        bar_a = draw_bar(total_a, cap, bar_w, CYAN)
        bar_b = draw_bar(total_b, cap, bar_w, YELLOW)

        cap_label = fmt_mem(cap, short=True) if cap > 0 else "N/A"

        print()
        print(f"{BOLD}{pool} OVERVIEW{RESET}")
        print(f"  A │ [{bar_a}] {fmt_mem(total_a):>11} / {cap_label}")
        print(f"  B │ [{bar_b}] {fmt_mem(total_b):>11} / {cap_label}")
        print(f"  Δ │ {diff_text(total_a, total_b)}")


def all_components(data_a: dict, data_b: dict) -> list[str]:
    keys = set()

    for pool in ["VRAM", "RAM"]:
        keys.update(get_components(data_a, pool).keys())
        keys.update(get_components(data_b, pool).keys())

    ordered = [c for c in COMPONENT_ORDER if c in keys]
    extra = sorted(k for k in keys if k not in ordered)

    return ordered + extra


def print_component_breakdown(data_a: dict, data_b: dict, term_width: int) -> None:
    sep = "─" * term_width

    print()
    print(f"{DIM}{sep}{RESET}")
    print(f"{BOLD}{'COMPONENT BREAKDOWN':^{term_width}}{RESET}")
    print(f"{DIM}{sep}{RESET}")

    comps = all_components(data_a, data_b)

    for comp in comps:
        label = COMPONENT_LABELS.get(comp, comp)

        vram_a = float(get_components(data_a, "VRAM").get(comp, 0.0))
        vram_b = float(get_components(data_b, "VRAM").get(comp, 0.0))
        ram_a = float(get_components(data_a, "RAM").get(comp, 0.0))
        ram_b = float(get_components(data_b, "RAM").get(comp, 0.0))

        if not any([vram_a, vram_b, ram_a, ram_b]):
            continue

        print()
        print(f" {BOLD}● {label}{RESET}")

        max_value = max(vram_a, vram_b, ram_a, ram_b, 0.01)

        rows = [
            ("VRAM", vram_a, vram_b),
            ("RAM", ram_a, ram_b),
        ]

        for pool, val_a, val_b in rows:
            if abs(val_a) < 0.01 and abs(val_b) < 0.01:
                continue

            bar_a = draw_mini_bar(val_a, max_value, width=12, bar_color=CYAN)
            bar_b = draw_mini_bar(val_b, max_value, width=12, bar_color=YELLOW)

            print(
                f"    {DIM}{pool:<4}{RESET} │ "
                f"A: [{bar_a}] {fmt_mem(val_a):>11} │ "
                f"B: [{bar_b}] {fmt_mem(val_b):>11} │ "
                f"Δ: {diff_text(val_a, val_b)}"
            )


def print_total_summary(data_a: dict, data_b: dict, term_width: int) -> None:
    total_a = get_grand_total(data_a)
    total_b = get_grand_total(data_b)

    title = " TOTAL MEMORY USAGE "
    side = max(0, (term_width - len(title)) // 2)

    print()
    print(f"{DIM}{'═' * side}{RESET}{BOLD}{title}{RESET}{DIM}{'═' * side}{RESET}")
    print(f"  Total memory A (RAM + VRAM): {fmt_mem(total_a)}")
    print(f"  Total memory B (RAM + VRAM): {fmt_mem(total_b)}")
    print(f"  Difference B - A:            {diff_text(total_a, total_b)}")
    print(f"{DIM}{'═' * term_width}{RESET}")
    print()


def print_oom_warning(data: dict, label: str) -> None:
    status = data.get("status", {}) or {}
    if not status.get("oom"):
        return

    print()
    print(f"{RED}{BOLD}WARNING: {label} ended with OOM / launch failure{RESET}")

    fatal = status.get("fatal_error")
    failed_component = status.get("failed_component")
    failed_category = status.get("failed_category")
    failed_alloc = status.get("failed_alloc_mib")
    deficit = status.get("estimated_deficit_mib")

    if fatal:
        print(f"  Reason: {fatal}")
    if failed_category:
        print(f"  Failed pool: {failed_category}")
    if failed_component:
        print(f"  Failed component: {failed_component}")
    if failed_alloc is not None:
        print(f"  Failed allocation: {fmt_mem(float(failed_alloc))}")
    if deficit is not None:
        print(f"  Estimated deficit: {fmt_mem(float(deficit))}")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 llama-mem-diff.py a.json b.json", file=sys.stderr)
        sys.exit(2)

    data_a = load_json(sys.argv[1])
    data_b = load_json(sys.argv[2])

    term_width = max(88, shutil.get_terminal_size((120, 40)).columns)

    title = " LLAMA.CPP MEMORY DIFF "
    side = max(0, (term_width - len(title)) // 2)

    print()
    print(f"{CYAN}{'═' * side}{RESET}{BOLD}{title}{RESET}{CYAN}{'═' * side}{RESET}")
    print()

    print_side_by_side_meta(data_a, data_b, term_width)

    print_oom_warning(data_a, "Run A")
    print_oom_warning(data_b, "Run B")

    print_pool_overview(data_a, data_b, term_width)
    print_component_breakdown(data_a, data_b, term_width)
    print_total_summary(data_a, data_b, term_width)


if __name__ == "__main__":
    main()
