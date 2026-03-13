"""
Deploy Qwen3-VL-8B-Thinking (text-only) on Modal with vLLM.
Optimized for PDF/text prompts, skips vision encoder to save GPU memory.

Run: modal deploy modal_qwen_vl.py
"""

import subprocess
import modal

# -----------------------------
# Modal Image Setup
# -----------------------------
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12")
    # Install core dependencies first to reduce build memory usage
    .uv_pip_install("torch")
    .uv_pip_install("vllm>=0.11.0")
    .uv_pip_install("huggingface-hub>=0.36.0", "qwen-vl-utils==0.0.14")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# -----------------------------
# Model Config
# -----------------------------
MODEL_NAME = "Qwen/Qwen3-VL-8B-Thinking"

# Text-only flags: skips vision encoder to save GPU memory
TEXT_ONLY_FLAGS = [
    "--limit-mm-per-prompt.video", "0",
    "--limit-mm-per-prompt.image", "0",
]

# -----------------------------
# Modal Volumes (Cache)
# -----------------------------
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

# -----------------------------
# App Config
# -----------------------------
app = modal.App("qwen-vllm-inference")
N_GPU = 1
VLLM_PORT = 8000
MINUTES = 60
FAST_BOOT = True

# -----------------------------
# vLLM Serve Function
# -----------------------------
@app.function(
    image=vllm_image,
    gpu=f"H100:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=10 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * MINUTES)
def serve():
    """Start vLLM server for text-only workloads."""
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--uvicorn-log-level=info",
        "--served-model-name", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        *TEXT_ONLY_FLAGS,
        "--enforce-eager" if FAST_BOOT else "--no-enforce-eager",
        "--tensor-parallel-size", str(N_GPU),
    ]
    print("Starting vLLM server with command:")
    print(" ".join(cmd))
    subprocess.Popen(" ".join(cmd), shell=True)

# -----------------------------
# Local Entrypoint for Testing
# -----------------------------
@app.local_entrypoint()
def main():
    print("Deploy with: modal deploy modal_qwen_vl.py")
    print("Run locally for testing: modal serve modal_qwen_vl.py")
    print("Volumes for caching Hugging Face and vLLM are already mounted.")
