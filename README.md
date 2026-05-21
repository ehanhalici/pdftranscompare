# pdftranscompare

A high-performance pipeline that accurately extracts, cleans, tokenizes, and translates PDF documents side-by-side using a local Large Language Model (LLM). Built for NixOS and optimized for CUDA.

This project is specifically engineered to prevent CUDA Out of Memory (OOM) errors on GPUs with limited VRAM (e.g., 12 GB RTX 4070) by strictly enforcing Lazy Loading and sequential VRAM management.

## Features

* **NixOS & CUDA Native:** Utilizes `shell.nix` to isolate and configure CUDA drivers, libraries (`libcublas`, `cudart`), and `llama-cpp-python` dependencies seamlessly.
* **Anti-OOM Memory Management:** Ensures that `marker-pdf` (PyTorch/Surya) and `llama-cpp-python` never occupy VRAM simultaneously. Execution is strictly sequential with forced GPU cache clearing (`torch.cuda.empty_cache()`) between heavy tasks.
* **LazyProxy Architecture:** Heavy dependencies and LLM instantiations are delayed until the exact moment of execution, reducing startup time to near zero and preventing global VRAM reservation.
* **Advanced Text Repair:** Integrates `wordninja` and `nltk` to automatically repair broken words and reconstruct proper sentences after PDF extraction.

## System Requirements

1. **OS:** NixOS or any Linux distribution with the Nix package manager installed.
2. **Hardware:** NVIDIA GPU with CUDA support.
3. **LLM Model:** `translategemma-4b-it.Q8_0.gguf`.
* Default expected path: `~/llm-models/translategemma-4b-it.Q8_0.gguf`



## Installation

The project uses Nix for system-level dependencies and `uv` for lightning-fast Python package management.

### 1. Enter the Nix Development Shell

Navigate to the project directory and start the Nix shell. This sets up the necessary `LD_LIBRARY_PATH` and CUDA environment variables:

```bash
nix-shell

```

### 2. Install Python Dependencies

Once inside the Nix shell, use `uv` to create the virtual environment (`.venv`) and sync dependencies from `pyproject.toml`:

```bash
uv sync

```

## Usage

The pipeline takes a PDF file as input and generates step-by-step HTML outputs (`step_1` to `step_4`), culminating in a side-by-side translated document.

Run the main pipeline:

```bash
python main.py <pdf_file_path> [output_directory] [start_page] [end_page]

```

### Example:

```bash
python main.py ~/Downloads/sample.pdf . 1 10

```

## Project Structure

* `shell.nix`: Defines system dependencies, CUDA libraries, and the `llama-cpp-python-cuda` override for NixOS.
* `pyproject.toml`: Python project metadata and dependencies managed by `uv`.
* `lazy_loader.py`: Contains the `LazyProxy` class for delayed module importing.
* `pdf_to_html.py`: Uses `marker-pdf` to extract text and layout, embedding images as base64 in HTML.
* `translate.py`: Implements a lazy-loaded, VRAM-friendly functional wrapper for `llama_cpp` and the `translategemma` model.
* `pdf_translate_and_merge.py`: Merges English source text and translated output into side-by-side HTML structures.
* `html_index_sentences.py`: Uses `nltk` for sentence tokenization and `wordninja` to fix broken words inside HTML tags.
* `environs.py`: Validates environment variables controlling VRAM limits (`INFERENCE_RAM`) and batch sizes (`DETECTOR_BATCH_SIZE`).

## Configuration and Tuning

If you encounter memory issues with very large PDFs or limited VRAM, adjust the following variables in `environs.py` or export them in `shell.nix`:

* `PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"`: Prevents PyTorch memory fragmentation.
* `DETECTOR_BATCH_SIZE="1"`: Forces Surya layout models to process one page at a time, preventing sudden VRAM spikes.
* `INFERENCE_RAM="4"`: Sets a hard ceiling on the VRAM PyTorch is allowed to allocate.
