from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ROBO1040 OCR API"
    api_key: str = "change-me-to-a-strong-secret"
    ocr_lang: str = "eng"
    ocr_dpi: int = 200
    ocr_max_side_px: int = 2400
    max_upload_mb: int = 25
    single_form_max_pages: int = 1
    brokerage_max_pages: int = 3
    max_pages: int = 3
    allowed_origins: str = "*"
    # Extraction pipeline (PyMuPDF → PP-StructureV3 → PaddleOCR)
    use_digital_pdf: bool = True
    digital_pdf_min_chars: int = 200
    digital_pdf_quality_threshold: float = 0.30  # max fraction of single-char words
    use_pp_structure: bool = True
    use_kie: bool = True
    use_image_preprocessing: bool = False  # enable after threshold tuning


    # PaddleOCR-VL (self-hosted VLM parser) — prefer for scans when available
    use_paddleocr_vl: bool = True
    paddleocr_vl_device: str | None = None  # e.g. "gpu:0" or "cpu"
    paddleocr_vl_model_name: str | None = None
    paddleocr_vl_model_dir: str | None = None
    paddleocr_vl_backend: str | None = None  # e.g. vllm-server / transformers
    paddleocr_vl_server_url: str | None = None
    # Schema-driven extraction (rules + optional local LLM)
    use_schema_extract: bool = True
    schema_llm_base_url: str | None = None  # e.g. http://host.docker.internal:11434/v1
    schema_llm_model: str | None = None  # e.g. qwen2.5:7b
    schema_llm_timeout_s: float = 45.0
    # Label memory mined from ground truth (CPU-only boost)
    label_memory_path: str | None = "training/learned_patterns.json"
    pp_structure_config: str | None = None
    kie_ser_model_dir: str | None = None
    kie_re_model_dir: str | None = None




@lru_cache
def get_settings() -> Settings:
    return Settings()
