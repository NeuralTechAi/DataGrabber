import os
import base64
import random
import threading
import time
from flask import current_app
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# One API call at a time across all parallel workers.
# This prevents simultaneous requests from blowing through rate limits.
_api_semaphore = threading.Semaphore(1)


def _call_with_backoff(fn, max_retries: int = 6, base_delay: float = 3.0):
    """Execute fn() inside the global API semaphore with exponential-backoff retry.

    Retries on HTTP 429 (rate limit) and transient 5xx errors.
    Delays: ~3s, ~6s, ~12s, ~24s, ~48s, ~96s before giving up.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            with _api_semaphore:
                return fn()
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            is_rate_limit = (
                "429" in err_str
                or "rate_limit" in err_str.lower()
                or "RateLimitError" in type(exc).__name__
                or "Too Many Requests" in err_str
            )
            is_transient = is_rate_limit or any(
                code in err_str for code in ("502", "503", "504", "500")
            )
            if is_transient and attempt < max_retries:
                # Exponential backoff with ±25 % jitter
                delay = base_delay * (2 ** attempt) * random.uniform(0.75, 1.25)
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{max_retries + 1}): "
                    f"{type(exc).__name__}. Retrying in {delay:.1f}s …"
                )
                time.sleep(delay)
                continue
            raise
    raise last_exc


class AIService:
    """Service for AI-related operations"""

    @staticmethod
    def get_settings(user=None):
        """Get AI provider/model and API key. If user is given and has saved settings, use those; else use app config/env."""
        from app.models import UserAISettings

        # Fallback from env/config
        fallback_provider = current_app.config.get("AI_PROVIDER", "gemini")
        fallback_model = current_app.config.get("AI_MODEL", "gemini-1.5-flash")
        gemini_api_key = os.getenv("GEMINI_API_KEY") or current_app.config.get("GEMINI_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY") or current_app.config.get("OPENAI_API_KEY")
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or current_app.config.get("OPENROUTER_API_KEY")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL") or current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        ollama_model = os.getenv("OLLAMA_MODEL") or current_app.config.get("OLLAMA_MODEL", "llama3.2")

        provider = fallback_provider
        model = fallback_model

        if user:
            settings = UserAISettings.query.filter_by(user_id=user.id).first()
            if settings and settings.ai_provider:
                provider = settings.ai_provider
                if provider == "openai":
                    model = settings.ai_model or "gpt-4o-mini"
                    openai_api_key = settings.openai_api_key or openai_api_key
                elif provider == "gemini":
                    model = settings.ai_model or "gemini-2.5-flash"
                    gemini_api_key = settings.gemini_api_key or gemini_api_key
                elif provider == "openrouter":
                    model = settings.ai_model or "openrouter/openai/gpt-4o-mini"
                    openrouter_api_key = settings.openrouter_api_key or openrouter_api_key
                elif provider == "ollama":
                    model = settings.ollama_model or ollama_model
                    ollama_base_url = settings.ollama_base_url or ollama_base_url

        if provider == "gemini":
            return {
                "provider": provider,
                "model": model,
                "api_key": gemini_api_key,
            }
        elif provider == "openai":
            return {
                "provider": provider,
                "model": model,
                "api_key": openai_api_key,
            }
        elif provider == "openrouter":
            return {
                "provider": provider,
                "model": model,
                "api_key": openrouter_api_key,
                "base_url": "https://openrouter.ai/api/v1",
            }
        elif provider == "ollama":
            return {
                "provider": provider,
                "model": model,
                "api_key": "ollama",
                "base_url": ollama_base_url,
            }
        else:
            return {
                "provider": "gemini",
                "model": model,
                "api_key": gemini_api_key,
            }

    @staticmethod
    def extract_data_with_ai(file_path: str, fields: list, file_type: str, user=None):
        """Extract structured data using the selected AI provider/model.
        For PDFs, returns a list of dicts (one per page).
        For images, returns a single dict.
        For text files, returns a single dict extracted from text content.
        If user is provided, uses that user's saved AI settings when set.
        """
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return [{"error": "File not found"}]
            
        # Verify file has content
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.warning(f"Empty file detected: {file_path}")
            return [{"error": "Empty file"}]
            
        # Enhanced logging for debugging
        logger.info(f"Processing file: {file_path} (type: {file_type}, size: {file_size} bytes)")
            
        # Special handling for .txt files - read content directly
        if file_type == 'document' and file_path.lower().endswith('.txt'):
            return AIService._extract_from_text_content(file_path, fields, user=user)

        # Normalize: .pdf files must be treated as 'pdf' regardless of the caller's
        # broader classification (e.g. 'document'), so provider-specific PDF logic fires.
        if file_path.lower().endswith('.pdf'):
            file_type = 'pdf'

        settings = AIService.get_settings(user=user)
        provider = settings["provider"]
        model = settings["model"]
        api_key = settings["api_key"]

        if provider == "gemini":
            # Validate API key before processing
            if not api_key:
                logger.error("Gemini API key not found in environment variables or config")
                return [{"error": "Gemini API key not configured"}]

            try:
                logger.info(f"Processing file {file_path} (type: {file_type}) with Gemini")
                logger.debug(f"Gemini API key present: {bool(api_key)}")
                result = AIService._extract_with_gemini_upload(file_path, fields, model, api_key, file_type)
                logger.info(f"Successfully processed {file_path} with Gemini")
                return result
            except Exception as e:
                logger.error(f"Error processing {file_path} with Gemini: {e}", exc_info=True)
                # Return a placeholder result with error message instead of raising
                return [{"error": f"Gemini processing error: {str(e)}"}]
        elif provider == "openai":
            if file_type == "pdf":
                try:
                    import fitz  # PyMuPDF
                except ImportError:
                    raise Exception("PyMuPDF is required for PDF processing. Install with: pip install pymupdf")

                try:
                    doc = fitz.open(file_path)
                    page_images = []
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(dpi=200)
                        page_images.append(pix.tobytes("png"))
                    doc.close()
                    # Send ALL pages in one request so the model sees the full document
                    result = AIService._extract_with_openai_vision_all_pages(page_images, fields, model, api_key)
                    return [result]
                except Exception as e:
                    logger.error(f"Error processing PDF {file_path} with OpenAI: {e}", exc_info=True)
                    return [{"error": f"PDF processing error: {str(e)}"}]
            elif file_type == "image":
                # Enhanced image handling with better error reporting
                try:
                    # Special logging for image processing
                    logger.info(f"IMAGE PROCESSING: Reading file {file_path} ({file_size} bytes)")
                    
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    
                    # Extra validation for image data
                    if len(img_bytes) < 100:
                        logger.warning(f"Suspiciously small image file: {file_path} ({len(img_bytes)} bytes)")
                    
                    logger.info(f"Processing image file {file_path} with OpenAI Vision ({len(img_bytes)} bytes)")
                    result = AIService._extract_with_openai_vision_bytes(img_bytes, fields, model, api_key)
                    return [result]
                except Exception as e:
                    logger.error(f"Error processing image {file_path} with OpenAI: {e}", exc_info=True)
                    return [{"error": f"Image processing error: {str(e)}"}]
            else:
                # Handle other file types - try as generic binary content
                try:
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    logger.info(f"Processing file {file_path} (type: {file_type}) as binary with OpenAI ({len(file_bytes)} bytes)")
                    result = AIService._extract_with_openai_vision_bytes(file_bytes, fields, model, api_key)
                    return [result]
                except Exception as e:
                    logger.error(f"Error processing file {file_path} with OpenAI: {e}", exc_info=True)
                    return [{"error": f"File processing error: {str(e)}"}]
        elif provider in ("openrouter", "ollama"):
            # For PDFs, extract text with PyMuPDF then run text-based extraction
            if file_type == 'pdf':
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(file_path)
                    text_content = "\n\n".join(page.get_text() for page in doc)
                    doc.close()
                    if not text_content.strip():
                        return [{field['name']: "Not found" for field in fields}]
                    if provider == "openrouter":
                        return AIService._extract_text_with_openrouter(text_content, fields, settings["model"], settings["api_key"])
                    else:
                        return AIService._extract_text_with_ollama(
                            text_content, fields, settings["model"],
                            settings.get("api_key"),
                            settings.get("base_url", "http://localhost:11434/v1"),
                        )
                except Exception as e:
                    logger.error(f"Error extracting PDF text for {provider}: {e}", exc_info=True)
                    return [{"error": f"PDF text extraction error: {str(e)}"}]

            logger.warning(f"{provider} file extraction is only supported for text content; got file_type={file_type}")
            return [{"error": f"{provider} provider only supports text-based extraction in this app. Convert file to text first."}]
        
        # Default error response instead of raising exception
        logger.error(f"No supported AI provider configured for {file_path}")
        return [{"error": "No supported AI provider configured"}]
    
    @staticmethod
    def _extract_from_text_content(file_path: str, fields: list, user=None):
        """Extract structured data from text file content using AI"""
        try:
            # Read the text content from the file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
            except UnicodeDecodeError:
                # Try with different encoding if UTF-8 fails
                with open(file_path, 'r', encoding='latin-1') as f:
                    text_content = f.read()
            
            if not text_content.strip():
                # Return empty data for empty files
                return [{field['name']: "Not found" for field in fields}]
            
            # Use the configured AI service to extract data from text
            settings = AIService.get_settings(user=user)
            provider = settings["provider"]
            
            if provider == "gemini":
                return AIService._extract_text_with_gemini(text_content, fields, settings["model"], settings["api_key"])
            elif provider == "openai":
                return AIService._extract_text_with_openai(text_content, fields, settings["model"], settings["api_key"])
            elif provider == "openrouter":
                return AIService._extract_text_with_openrouter(text_content, fields, settings["model"], settings["api_key"])
            elif provider == "ollama":
                return AIService._extract_text_with_ollama(
                    text_content,
                    fields,
                    settings["model"],
                    settings.get("api_key"),
                    settings.get("base_url", "http://localhost:11434/v1"),
                )
            else:
                raise Exception("No supported AI provider configured for text extraction.")
                
        except Exception as e:
            logger.error(f"Error extracting data from text file {file_path}: {e}")
            # Return default "not found" data rather than failing completely
            return [{field['name']: f"Error: {str(e)}" for field in fields}]
    
    @staticmethod
    def _extract_text_with_gemini(text_content: str, fields: list, model: str, api_key: str):
        """Extract structured data from text using Gemini with JSON output."""
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(model_name=model)
        prompt = (
            AIService._build_json_prompt(
                fields,
                context_hint="Carefully read the following text and extract the requested information.",
            )
            + f"\n\nTEXT CONTENT:\n{text_content}"
        )

        def _call():
            try:
                return gemini_model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
                )
            except Exception:
                return gemini_model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.0},
                )

        response = _call_with_backoff(_call)
        return [AIService._parse_json_response(response.text, fields)]

    @staticmethod
    def _extract_text_with_openai(text_content: str, fields: list, model: str, api_key: str):
        """Extract structured data from text using OpenAI with JSON output."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            AIService._build_json_prompt(
                fields,
                context_hint="Carefully read the following text and extract the requested information.",
            )
            + f"\n\nTEXT CONTENT:\n{text_content}"
        )
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Respond ONLY with a valid JSON object containing the extracted fields."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return [AIService._parse_json_response(response.choices[0].message.content, fields)]

    @staticmethod
    def _extract_text_with_openrouter(text_content: str, fields: list, model: str, api_key: str):
        """Extract structured data from text using OpenRouter (OpenAI-compatible) with JSON output."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        prompt = (
            AIService._build_json_prompt(
                fields,
                context_hint="Carefully read the following text and extract the requested information.",
            )
            + f"\n\nTEXT CONTENT:\n{text_content}"
        )
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Respond ONLY with a valid JSON object containing the extracted fields."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return [AIService._parse_json_response(response.choices[0].message.content, fields)]

    @staticmethod
    def _extract_text_with_ollama(text_content: str, fields: list, model: str, api_key: str, base_url: str):
        """Extract structured data from text using an Ollama-compatible OpenAI endpoint with JSON output."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key or "ollama", base_url=base_url)
        prompt = (
            AIService._build_json_prompt(
                fields,
                context_hint="Carefully read the following text and extract the requested information.",
            )
            + f"\n\nTEXT CONTENT:\n{text_content}"
        )
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Respond ONLY with a valid JSON object containing the extracted fields."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return [AIService._parse_json_response(response.choices[0].message.content, fields)]
    
    # ------------------------------------------------------------------ #
    #  Shared helpers for prompt construction and response parsing        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_json_prompt(fields: list, context_hint: str = "") -> str:
        """Build a prompt that instructs the model to return a strict JSON object."""
        field_specs = "\n".join(
            f'  "{f["name"]}": <{f.get("description", f["name"])}>'
            for f in fields
        )
        field_names = ", ".join(f'"{f["name"]}"' for f in fields)
        intro = f"{context_hint}\n\n" if context_hint else ""
        return (
            f"{intro}"
            f"Extract the following fields and return ONLY a valid JSON object "
            f"with exactly these keys: {field_names}\n\n"
            f"Expected JSON structure:\n{{\n{field_specs}\n}}\n\n"
            "Rules:\n"
            "- Search the ENTIRE document for each field — check every section\n"
            "- For list fields (skills, technologies, experience items), join with ', '\n"
            '- If a field truly cannot be found anywhere, use exactly: "Not found"\n'
            "- Strip any surrounding markdown, bullets, or numbering from values\n"
            "- Return ONLY the JSON object — no explanation, no extra text"
        )

    @staticmethod
    def _parse_json_response(text: str, fields: list) -> dict:
        """Parse AI response into a structured dict.
        Tries strict JSON first, then falls back to line-by-line key:value matching."""
        import json, re
        if not text:
            return {f["name"]: "Not found" for f in fields}

        # 1. Try JSON parse (handle optional markdown fences)
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned.rstrip())
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                result = {}
                for f in fields:
                    raw = obj.get(f["name"], "Not found")
                    result[f["name"]] = str(raw).strip() if raw else "Not found"
                return result
        except Exception:
            pass

        # 2. Fallback: case-insensitive key:value line scanning
        data: dict = {}
        field_map = {f["name"].lower().replace(" ", "_"): f["name"] for f in fields}
        field_map.update({f["name"].lower(): f["name"] for f in fields})
        for line in text.split("\n"):
            if ":" not in line:
                continue
            raw_key, _, raw_val = line.partition(":")
            key_norm = re.sub(r"[^a-z0-9_]", "_", raw_key.strip().lower()).strip("_")
            matched = None
            for fk, fn in field_map.items():
                norm_fk = re.sub(r"[^a-z0-9_]", "_", fk)
                if norm_fk == key_norm or norm_fk in key_norm or key_norm in norm_fk:
                    matched = fn
                    break
            if matched and matched not in data:
                val = raw_val.strip().strip('"').strip("'").strip()
                if val and val.lower() not in ("", "n/a"):
                    data[matched] = val

        for f in fields:
            data.setdefault(f["name"], "Not found")
        return data

    @staticmethod
    def _merge_page_results(page_results: list, fields: list) -> dict:
        """Merge per-page extraction dicts into one, taking first non-'Not found' value."""
        merged = {f["name"]: "Not found" for f in fields}
        for page_data in page_results:
            if not isinstance(page_data, dict):
                continue
            for f in fields:
                name = f["name"]
                val = page_data.get(name, "Not found")
                if merged[name] == "Not found" and val and val != "Not found":
                    merged[name] = val
        return merged

    # ------------------------------------------------------------------ #
    #  OpenAI Vision helpers                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_with_openai_vision_bytes(img_bytes, fields, model, api_key):
        """Extract from a single image using OpenAI Vision with JSON output."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        prompt = AIService._build_json_prompt(
            fields,
            context_hint="Carefully analyze this document image and extract the requested information.",
        )
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Read the document carefully and respond ONLY with a valid JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                        },
                    ],
                },
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return AIService._parse_json_response(response.choices[0].message.content, fields)

    @staticmethod
    def _extract_with_openai_vision_all_pages(page_images: list, fields: list, model: str, api_key: str) -> dict:
        """Send ALL PDF page images in ONE OpenAI Vision request → single merged result."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = AIService._build_json_prompt(
            fields,
            context_hint=(
                "You are analyzing a multi-page document. All pages are provided below as images. "
                "Read through ALL pages carefully before answering — data may be spread across pages."
            ),
        )
        content: list = [{"type": "text", "text": prompt}]
        for img_bytes in page_images:
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
            })
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Read every page carefully and respond ONLY with a valid JSON object."
                    ),
                },
                {"role": "user", "content": content},
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return AIService._parse_json_response(response.choices[0].message.content, fields)

    @staticmethod
    def _extract_with_openai_vision(file_path, fields, model, api_key, file_type):
        """Extract from an image file using OpenAI Vision with JSON output."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        mime = "image/jpeg" if file_type == "image" else "image/png"
        prompt = AIService._build_json_prompt(
            fields,
            context_hint="Carefully analyze this document image and extract the requested information.",
        )
        kwargs = dict(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise data extraction assistant. "
                        "Read the document carefully and respond ONLY with a valid JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}},
                    ],
                },
            ],
            max_tokens=2000,
        )

        def _call():
            try:
                kw = {**kwargs, "response_format": {"type": "json_object"}}
                return client.chat.completions.create(**kw)
            except Exception:
                return client.chat.completions.create(**kwargs)

        response = _call_with_backoff(_call)
        return AIService._parse_json_response(response.choices[0].message.content, fields)
    
    @staticmethod
    def _extract_with_gemini_upload(file_path: str, fields: list, model: str, api_key: str, file_type: str):
        """Extract data using Google Gemini file upload with JSON output."""
        try:
            genai.configure(api_key=api_key)
            gemini_model = genai.GenerativeModel(model_name=model)

            try:
                uploaded_file = genai.upload_file(path=file_path)
                logger.debug(f"File successfully uploaded to Gemini: {file_path}")
            except Exception as upload_error:
                logger.error(f"Error uploading file to Gemini: {upload_error}", exc_info=True)
                return [{field['name']: f"Upload error: {str(upload_error)}" for field in fields}]

            context_prompt = AIService._get_context_prompt_for_file_type(file_type)
            prompt = AIService._build_json_prompt(fields, context_hint=context_prompt)

            def _call():
                try:
                    return gemini_model.generate_content(
                        contents=[prompt, uploaded_file],
                        generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
                    )
                except Exception:
                    return gemini_model.generate_content(
                        contents=[prompt, uploaded_file],
                        generation_config={"temperature": 0.0},
                    )

            response = _call_with_backoff(_call)
            logger.info(f"Successfully extracted data from {file_path} (type: {file_type}) with Gemini")
            data = AIService._parse_json_response(response.text, fields)
            return [data]

        except Exception as e:
            logger.error(f"Error with Gemini extraction: {e}", exc_info=True)
            return [{field['name']: f"Extraction error: {str(e)}" for field in fields}]
    
    @staticmethod
    def _get_context_prompt_for_file_type(file_type: str) -> str:
        """Generate context-specific prompts based on file type"""
        prompts = {
            'document': "Analyze this document and extract the requested information from the text content.",
            'image': "Analyze this image and extract any visible text, data, or information that matches the requested fields.",
            'data': "Analyze this data file (spreadsheet/CSV) and extract information from the rows, columns, and data structure.",
            'audio': "Analyze this audio file and extract any spoken information, transcribed content, or metadata that matches the requested fields.",
            'video': "Analyze this video file and extract information from any visible text, spoken content, or visual elements that match the requested fields.",
            'code': "Analyze this code file and extract relevant information from comments, documentation, variable names, or code structure.",
            'archive': "Analyze the contents of this archive file and extract information from the contained files and their structure.",
            'pdf': "Analyze this PDF document and extract the requested information from all pages, including text, tables, and any structured data."
        }
        
        return prompts.get(file_type, "Analyze this file and extract the requested information from its content.")
    
    def get_available_providers():
        """Get available AI providers and their models - Gemini as default.
        
        This now includes OpenRouter and Ollama when configured.
        """
        providers = {}

        # Try environment variables first, then config
        gemini_api_key = os.getenv('GEMINI_API_KEY') or current_app.config.get('GEMINI_API_KEY')
        openai_api_key = os.getenv('OPENAI_API_KEY') or current_app.config.get('OPENAI_API_KEY')
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY') or current_app.config.get('ANTHROPIC_API_KEY')
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
        ollama_base_url = os.getenv('OLLAMA_BASE_URL') or current_app.config.get('OLLAMA_BASE_URL')
        enable_anthropic = current_app.config.get('ENABLE_ANTHROPIC', False)
        enable_openai = current_app.config.get('ENABLE_OPENAI', True)
    
        # Gemini provider (default)
        if gemini_api_key:
            providers['gemini'] = {
                'name': 'Google Gemini',
                'models': [
                    {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash', 'vision': True},
                    {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash', 'vision': True},
                    {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'vision': True},
                    {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash', 'vision': True},
                    {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro', 'vision': True}
                ]
            }
    
        # OpenAI provider (optional)
        if enable_openai and openai_api_key:
            providers['openai'] = {
                'name': 'OpenAI',
                'models': [
                    {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'vision': True},
                    {'id': 'gpt-4o', 'name': 'GPT-4o', 'vision': True},
                    {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'vision': True},
                    {'id': 'gpt-4', 'name': 'GPT-4', 'vision': False},
                    {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'vision': False}
                ]
            }
    
        # Anthropic provider (optional)
        if enable_anthropic and anthropic_api_key:
            providers['anthropic'] = {
                'name': 'Anthropic',
                'models': [
                    {'id': 'claude-3-5-sonnet-20241022', 'name': 'Claude 3.5 Sonnet', 'vision': True},
                    {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'vision': True},
                    {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'vision': True},
                    {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'vision': True}
                ]
            }
    
        # OpenRouter provider (optional)
        if openrouter_api_key:
            providers['openrouter'] = {
                'name': 'OpenRouter',
                'models': [
                    {'id': 'openrouter/openai/gpt-4o-mini', 'name': 'GPT-4o Mini (OpenRouter)', 'vision': False},
                    {'id': 'openrouter/anthropic/claude-3.5-sonnet', 'name': 'Claude 3.5 Sonnet (OpenRouter)', 'vision': False},
                ]
            }
        
        # Ollama provider (optional, assumes local endpoint)
        if ollama_base_url:
            providers['ollama'] = {
                'name': 'Ollama (local)',
                'models': [
                    {'id': current_app.config.get('OLLAMA_MODEL', 'llama3.2'), 'name': 'Default Ollama model', 'vision': False},
                ]
            }
        
        return providers
    
    @staticmethod
    def get_default_provider_and_model():
        """Get the default provider and model for new projects"""
        providers = AIService.get_available_providers()
        
        # Default to Gemini if available
        if 'gemini' in providers and providers['gemini']['models']:
            return 'gemini', providers['gemini']['models'][0]['id']
        
        # Fallback to OpenAI if available
        if 'openai' in providers and providers['openai']['models']:
            return 'openai', providers['openai']['models'][0]['id']
        
        # Fallback to first available provider and model
        for provider_id, provider in providers.items():
            if provider['models']:
                return provider_id, provider['models'][0]['id']
        
        # No providers available
        return None, None