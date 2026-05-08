"""
Convert merged HuggingFace model to GGUF q4_K_M for Ollama.

Requires llama.cpp to be cloned and compiled locally:
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp && make -j$(nproc)
    pip install -r requirements.txt  # for convert_hf_to_gguf.py

Set LLAMA_CPP_DIR env var or pass --llama-cpp to point at the llama.cpp root.
"""

import argparse
import os
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export merged model to GGUF")
    parser.add_argument("--merged", default="output/merged", help="Path to merged HF model")
    parser.add_argument("--out", default="output/home-security.gguf", help="Output GGUF path")
    parser.add_argument(
        "--llama-cpp",
        default=os.getenv("LLAMA_CPP_DIR", "./llama.cpp"),
        help="Path to llama.cpp root directory",
    )
    args = parser.parse_args()

    merged = Path(args.merged).resolve()
    out = Path(args.out).resolve()
    llama_cpp = Path(args.llama_cpp).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    convert_script = llama_cpp / "convert_hf_to_gguf.py"
    if not convert_script.exists():
        raise FileNotFoundError(
            f"convert_hf_to_gguf.py not found at {convert_script}. "
            "Clone and build llama.cpp first: https://github.com/ggerganov/llama.cpp"
        )

    f16_gguf = out.with_suffix(".f16.gguf")
    print(f"Converting {merged} → {f16_gguf}")
    subprocess.run(
        ["python", str(convert_script), str(merged), "--outfile", str(f16_gguf), "--outtype", "f16"],
        check=True,
    )

    quantize_bin = llama_cpp / "llama-quantize"
    if not quantize_bin.exists():
        quantize_bin = llama_cpp / "build" / "bin" / "llama-quantize"
    if not quantize_bin.exists():
        raise FileNotFoundError(f"llama-quantize not found in {llama_cpp}. Run 'make' in llama.cpp directory.")

    print(f"Quantizing {f16_gguf} → {out} (q4_K_M)")
    subprocess.run([str(quantize_bin), str(f16_gguf), str(out), "q4_K_M"], check=True)

    f16_gguf.unlink(missing_ok=True)
    print(f"\nGGUF ready: {out}")
    print(f"Register with Ollama:\n  ollama create home-security -f training/Modelfile")


if __name__ == "__main__":
    main()
