# olaiedge/model_catalog.py
"""
Model Catalog & Zero-Setup Model Manager for OlaiEdge.
Manages discovery, verification, and non-blocking background downloads of curated edge models.
"""
import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional
import urllib.request


EDGE_MODEL_CATALOG = {
    "qwen2.5-1.5b": {
        "id": "qwen2.5-1.5b",
        "name": "Qwen 2.5 1.5B Instruct",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 986,
        "min_ram_mb": 1500,
        "recommended_context": 4096,
        "ideal_for": "Code Editors, Tool Calling, Multi-Step ReAct Agents",
    },
    "llama-3.2-1b": {
        "id": "llama-3.2-1b",
        "name": "Meta Llama 3.2 1B Instruct",
        "filename": "llama-3.2-1b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "size_mb": 720,
        "min_ram_mb": 1200,
        "recommended_context": 2048,
        "ideal_for": "Ultra-Low RAM Laptops, Note-Taking, Instant Text Summaries",
    },
    "gemma-2b-q4": {
        "id": "gemma-2b-q4",
        "name": "Google Gemma 2B Instruct",
        "filename": "gemma-2b-q4.gguf",
        "url": "https://huggingface.co/google/gemma-2b-it-GGUF/resolve/main/2b_it_v2.gguf",
        "size_mb": 1930,
        "min_ram_mb": 2500,
        "recommended_context": 2048,
        "ideal_for": "Drafting, Analytical Reasoning, Accounting Formulas",
    },
    "smollm2-1.7b": {
        "id": "smollm2-1.7b",
        "name": "HuggingFace SmolLM2 1.7B Instruct",
        "filename": "smollm2-1.7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF/resolve/main/smollm2-1.7b-instruct-q4_k_m.gguf",
        "size_mb": 1050,
        "min_ram_mb": 1600,
        "recommended_context": 4096,
        "ideal_for": "Fast Autocomplete, Local CAD Commands",
    },
}


class ModelManager:
    """
    Manages edge model discovery, GGUF binary verification, and automated downloads.
    """

    @staticmethod
    def get_default_models_dir() -> Path:
        """Returns standard platform-appropriate models directory, with workspace fallback."""
        candidates = []
        if os.name == "nt":
            appdata = os.environ.get("LOCALAPPDATA")
            if appdata:
                candidates.append(Path(appdata) / "OlaiEdge" / "models")
        candidates.append(Path.home() / ".cache" / "olaiedge" / "models")
        candidates.append(Path.cwd() / ".olaiedge" / "models")

        for target in candidates:
            try:
                target.mkdir(parents=True, exist_ok=True)
                return target
            except (PermissionError, OSError):
                continue

        fallback = Path.cwd() / "models"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    @classmethod
    def list_catalog(cls) -> List[Dict[str, Any]]:
        """Returns the curated catalog of recommended edge models."""
        return list(EDGE_MODEL_CATALOG.values())

    @classmethod
    def find_local_models(cls, extra_dirs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Scans workspace, package directory, and user cache for existing .gguf models."""
        search_dirs = [
            Path.cwd(),
            cls.get_default_models_dir(),
            Path(__file__).parent,
            Path(__file__).parent.parent,
        ]
        if extra_dirs:
            search_dirs.extend([Path(d) for d in extra_dirs if os.path.isdir(d)])

        found_models: Dict[str, Dict[str, Any]] = {}

        for directory in search_dirs:
            if not directory.exists():
                continue
            for file_path in directory.glob("*.gguf"):
                abs_path = str(file_path.resolve())
                if abs_path not in found_models:
                    file_size_mb = round(file_path.stat().st_size / (1024 * 1024), 1)
                    is_valid_gguf = cls.verify_gguf_header(abs_path)
                    found_models[abs_path] = {
                        "filename": file_path.name,
                        "path": abs_path,
                        "size_mb": file_size_mb,
                        "is_valid_gguf": is_valid_gguf,
                    }

        return list(found_models.values())

    @staticmethod
    def verify_gguf_header(file_path: str) -> bool:
        """Verifies that the file begins with GGUF magic bytes (0x46554747)."""
        if not os.path.isfile(file_path):
            return False
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                return header == b"GGUF"
        except Exception:
            return False

    @classmethod
    def resolve_model_path(cls, model_identifier_or_path: str) -> str:
        """
        Resolves a model name (e.g. 'qwen2.5-1.5b' or 'gemma-2b-q4.gguf') to an absolute file path.
        """
        if os.path.isfile(model_identifier_or_path):
            return os.path.abspath(model_identifier_or_path)

        if model_identifier_or_path in EDGE_MODEL_CATALOG:
            meta = EDGE_MODEL_CATALOG[model_identifier_or_path]
            filename = meta["filename"]
        else:
            filename = model_identifier_or_path

        search_paths = [
            Path.cwd() / filename,
            cls.get_default_models_dir() / filename,
            Path(__file__).parent / filename,
            Path(__file__).parent.parent / filename,
        ]
        for p in search_paths:
            if p.is_file():
                return str(p.resolve())

        raise FileNotFoundError(
            f"Model '{model_identifier_or_path}' could not be located. "
            f"Use ModelManager.download_model('{model_identifier_or_path}') to download it."
        )

    @classmethod
    def download_model(
        cls,
        model_id: str,
        dest_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[float, float, float], None]] = None,
    ) -> str:
        """Downloads a curated edge model with progress tracking."""
        if model_id not in EDGE_MODEL_CATALOG:
            valid_ids = ", ".join(EDGE_MODEL_CATALOG.keys())
            raise ValueError(f"Unknown model '{model_id}'. Available: {valid_ids}")

        meta = EDGE_MODEL_CATALOG[model_id]
        target_dir = Path(dest_dir) if dest_dir else cls.get_default_models_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_path = target_dir / meta["filename"]

        if dest_path.exists() and cls.verify_gguf_header(str(dest_path)):
            return str(dest_path.resolve())

        temp_path = dest_path.with_suffix(".download")

        def _reporthook(count, block_size, total_size):
            if total_size <= 0:
                return
            downloaded = count * block_size
            percent = min(100.0, downloaded * 100.0 / total_size)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            if progress_callback:
                progress_callback(percent, mb_down, mb_total)
            else:
                sys.stdout.write(f"\r[OlaiEdge Download] {percent:5.1f}% | {mb_down:.1f} MB / {mb_total:.1f} MB")
                sys.stdout.flush()

        try:
            urllib.request.urlretrieve(meta["url"], str(temp_path), reporthook=_reporthook)
            if not progress_callback:
                print()
            if not cls.verify_gguf_header(str(temp_path)):
                if temp_path.exists():
                    temp_path.unlink()
                raise ValueError("Downloaded file failed GGUF integrity validation.")

            temp_path.rename(dest_path)
            return str(dest_path.resolve())
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Download failed for '{model_id}': {e}")
