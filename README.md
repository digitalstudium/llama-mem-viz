# llama-mem-viz

`llama-mem-viz` is a lightweight stdlib-only Python tool for visualizing RAM/VRAM usage of `llama.cpp` (`llama-server` or `llama-cli`).

It parses `llama-server `logs in real time and helps identify memory usage, GPU offloading behavior, and Out-Of-Memory (OOM) failures.

![tool output](./output.png)

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

```bash
git clone https://github.com/digitalstudium/llama-mem-viz.git
cd llama-mem-viz
chmod +x llama-mem-viz.py
pyton3 llama-mem-viz.py
```

## Usage

### Run together with llama-server

Pass normal llama-server arguments directly to the script:

```bash
./llama-mem-viz.py -m model.gguf -c 65536 -ngl 40
```

## Example bash script

```bash
./visualize.sh
```

## Windows / macOS note

This project was developed and tested on Linux only.

Windows and macOS support is currently untested and may be partially broken.

