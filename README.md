# llama_mem_viz

`llama_mem_viz` is a lightweight stdlib-only Python tool for visualizing RAM/VRAM usage of `llama.cpp` (`llama-server` or `llama-cli`).

It parses `llama-server `logs in real time and helps identify memory usage, GPU offloading behavior, and Out-Of-Memory (OOM) failures.

## Features

- RAM / VRAM memory visualization
- Per-component breakdown:
  - Weights
  - KV Cache
  - Compute buffers
  - Output buffers
  - Recurrent state
- OOM / allocation failure detection
- JSON output mode
- No external dependencies (`pip install` not required)

## Installation

No installation is required.

1. Download `llama_mem_viz.py`
2. (Optional) make it executable:

```bash
chmod +x llama_mem_viz.py
```

3. Run with Python 3.10+

## Usage

### Run together with llama-server

Pass normal llama-server arguments directly to the script:

```bash
./llama_mem_viz.py -m model.gguf -c 65536 -ngl 40
```

## Example bash script

```bash
./visualize.sh
```

## Windows / macOS note

This project was developed and tested on Linux only.

Windows and macOS support is currently untested and may be partially broken.

