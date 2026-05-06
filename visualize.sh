./llama-mem-viz.py -m $HOME/.lmstudio/models/unsloth/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf \
	--fit off -rea off -c 65536 --seed 42 \
	-ngl 41 \
	-ncmoe 38 \
	-fa on \
	--mlock \
	-ctk q8_0 -ctv q8_0 \
	-t 8 \
	-ub 2048 \
	-np 1

