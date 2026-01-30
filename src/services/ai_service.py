# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
from langchain.prompts import PromptTemplate
from langchain.schema.messages import HumanMessage, SystemMessage
from src.config import settings
import google.generativeai as genai
import logging
import json
import re
from typing import Dict, List, Any
import base64
import asyncio
import traceback
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # 1. Embeddings: LOCAL (Free & Stable)
        # Using all-mpnet-base-v2 (768 dimensions) to match Pinecone index
        # Loading directly with sentence-transformers to avoid LangChain dependency conflicts
        self.embeddings = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

        # 2. OpenRouter Models (Priority: Free -> Cheap)
        # Free model for intent classification and simple summaries
        self.llm_free = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.0-flash-001", # Fallback to reliable model
            temperature=0.3,
        )

        # High-quality but extremely cheap model for primary tasks (Gemini 2.0 Flash)
        self.llm_openrouter = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.0-flash-001",
            temperature=0.3,
        )

        # 3. OpenAI Client (for Whisper audio fallback only)
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # 4. Fallback: Google Direct - DISABLED temporarily (Dependency Conflict)
        self.llm_google = None
        # ChatGoogleGenerativeAI(
        #     model="gemini-2.0-flash-001",
        #     google_api_key=settings.GOOGLE_API_KEY,
        #     temperature=0.3
        # )

    async def classify_intent(self, query: str) -> Dict:
        """
        Classifies user query into SEARCH, ASK, or BOTH.
        Also suggests metadata filters.
        """
        prompt = f"""Analyze this Telegram bot query: "{query}"

        Determine if the user is:
        1. Explicitly requesting a file/document/media (SEARCH).
        2. Asking a general question based on history (ASK).
        3. Both (BOTH).

        Guidelines for 'filter':
        - If the user specifically mentions "счет", "чек", "invoice", "инвойс" or "pdf", use {{"type": "document"}}.
        - If the user is vague (e.g., "what was there about light?"), use {{"type": null}} to search everything.
        - If the user asks for a video or image, use the respective type.

        Respond ONLY with a JSON object:
        {{
            "intent": "SEARCH" | "ASK" | "BOTH",
            "filter": {{ "type": "document" | "image" | "video" | "link" | null }},
            "reasoning": "short explanation"
        }}
        """
        try:
            # Use FREE model for intent classification
            response = await self.llm_free.ainvoke([HumanMessage(content=prompt)])
            import json
            import re
            match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"intent": "ASK", "filter": None}
        except Exception as e:
            logger.warning(f"Free intent classification failed, using primary: {e}")
            try:
                response = await self.llm_openrouter.ainvoke([HumanMessage(content=prompt)])
                import json
                import re
                match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except Exception as e2:
                logger.error(f"Intent classification failed: {e2}")
            return {"intent": "ASK", "filter": None}

    async def classify_voice_intent(self, transcription: str) -> dict:
        """
        Determines if a voice message is a QUERY, SAVE, or SELECT command.
        Returns: {"intent": "QUERY"|"SAVE"|"SELECT", "number": int|None}
        """
        prompt = f"""Проанализируй это голосовое сообщение: "{transcription}"

Определи намерение пользователя:
- QUERY: Пользователь задаёт вопрос или ищет информацию
- SAVE: Пользователь диктует информацию для сохранения (заметки, мысли, описание)
- SELECT: Пользователь просит показать конкретный результат поиска (например: "покажи номер 2", "давай второй", "третий вариант", "открой номер 5")

Примеры QUERY:
- "Что было на той встрече про офис?"
- "Найди счёт от января"
- "Покажи фото с конференции"

Примеры SAVE:
- "Запомни, встреча завтра в 3 часа"
- "Это важный момент для презентации"

Примеры SELECT:
- "Покажи номер 2" -> intent: SELECT, number: 2
- "Давай третий" -> intent: SELECT, number: 3
- "Открой второй результат" -> intent: SELECT, number: 2

Ответь ТОЛЬКО валидным JSON:
{{
  "intent": "QUERY" | "SAVE" | "SELECT",
  "number": <integer or null>
}}
"""

        try:
            response = await self.llm_free.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            # Clean up JSON if needed
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "")

            import json
            result = json.loads(content)

            intent = result.get("intent", "SAVE").upper()
            number = result.get("number")

            logger.info(f"Voice intent classified: {intent} (num={number}) for: {transcription[:50]}...")
            return {"intent": intent, "number": number}

        except Exception as e:
            logger.error(f"Voice intent classification failed: {e}")
            # Default to SAVE to avoid losing information
            return {"intent": "SAVE", "number": None}

    async def rerank_results(self, query: str, candidates: list) -> list:
        """
        Uses LLM to pick specific message_ids that are truly relevant from the candidates.
        """
        if not candidates: return []

        context_items = []
        for i, cand in enumerate(candidates):
            meta = cand.metadata
            context_items.append({
                "index": i,
                "type": meta.get('type'),
                "text": str(meta.get('text'))[:300],
                "message_id": meta.get('message_id')
            })

        prompt = f"""Query: "{query}"
        Candidates: {json.dumps(context_items, ensure_ascii=False)}

        Task: Identify which CANDIDATE indices are DIRECTLY relevant to the query.
        For a file request, only pick files that match the description.
        If multiple files match (e.g. multiple bills), pick all of them.

        Respond ONLY with a JSON list of indices, e.g.: [0, 2]
        If nothing is relevant, respond with: []
        """
        try:
            # Use FREE model for reranking
            response = await self.llm_free.ainvoke([HumanMessage(content=prompt)])
            match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if match:
                indices = json.loads(match.group())
                # Return the full candidate object so we have access to metadata
                return [candidates[i] for i in indices if i < len(candidates)]
            return []
        except Exception as e:
            logger.warning(f"Free reranking failed, using primary: {e}")
            try:
                response = await self.llm_openrouter.ainvoke([HumanMessage(content=prompt)])
                match = re.search(r'\[.*\]', response.content, re.DOTALL)
                if match:
                    indices = json.loads(match.group())
                    return [candidates[i] for i in indices if i < len(candidates)]
            except Exception as e2:
                logger.error(f"Reranking failed: {e2}")
            return candidates[:1] # Fallback to top result

    async def get_embedding(self, text: str) -> list[float]:
        """Generates embeddings using local HuggingFace model."""
        try:
            # Simple async wrapper for local computation
            # encode() returns numpy array, convert to list
            embedding = await asyncio.to_thread(self.embeddings.encode, text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return [0.0] * 768

    async def answer_question(self, context: str, question: str) -> str:
        """Generates an answer based on context, with fallback logic."""
        system_msg = SystemMessage(content="You are a highly detailed and helpful assistant. You MUST respond ONLY in Russian (на русском языке). NEVER use English, even if the context or question is in English. Always translate relevant information to Russian.")

        prompt_text = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer (in Russian):"
        human_msg = HumanMessage(content=prompt_text)

        # Primary: OpenRouter
        try:
            response = await self.llm_openrouter.ainvoke([system_msg, human_msg])
            return response.content
        except Exception as e:
            logger.error(f"OpenRouter Answer failed: {e}")
            return "Извините, сейчас я не могу ответить на этот вопрос. Попробуйте еще раз позже."

            # except Exception as e:
            #     logger.warning(f"OpenRouter Answer failed ({e}), switching to Google direct fallback...")
            #     # Secondary: Google Direct
            #     try:
            #         response = await self.llm_google.ainvoke([system_msg, human_msg])
            #         return response.content
            #     except Exception as e2:
            #         logger.error(f"Both AI providers failed. Google error: {e2}")
            #         return "Извините, сейчас я не могу ответить на этот вопрос. Попробуйте еще раз позже."

    async def summarize_content(self, content: str) -> str:
        """Summarizes content to extract key information, using FREE model first."""
        prompt_text = f"Summarize the following content briefly, extracting the main points.\n\n{content}"
        system_msg = SystemMessage(content="You are a highly detailed assistant. You MUST respond ONLY in Russian (на русском языке). NEVER use English, even if the input is English.")
        human_msg = HumanMessage(content=prompt_text)

        # 1. Try FREE OpenRouter model first
        try:
            response = await self.llm_free.ainvoke([system_msg, human_msg])
            return response.content
        except Exception as e:
            logger.warning(f"Free summary failed, trying paid OpenRouter. Error: {e}")
            try:
                # 2. Try Paid High-Quality OpenRouter (Flash 001)
                response = await self.llm_openrouter.ainvoke([system_msg, human_msg])
                return response.content
            except Exception as e2:
                logger.error(f"Paid summary failed: {e2}")
                # Google fallback disabled
                return "Ошибка при создании краткого описания."

                # try:
                #     # 3. Try Google Direct
                #     response = await self.llm_google.ainvoke([system_msg, human_msg])
                #     return response.content
                # except Exception as e3:
                #     logger.error(f"All summary methods failed: {e3}")
                #     return \"Ошибка при создании краткого описания.\"

    def decode_qr_barcode(self, image_data: bytes) -> str:
        """
        Decodes QR codes and barcodes from image data.
        Returns: Decoded data as formatted string or empty string if none found.
        """
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            import io

            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"QR/Barcode detection: Image size {image.size}, mode {image.mode}")

            # Try decoding original image first
            decoded_objects = decode(image)

            # If nothing found, try preprocessing
            if not decoded_objects:
                logger.info("QR/Barcode: No codes found in original, trying preprocessing...")

                # Convert to grayscale (better for some QR codes)
                gray_image = image.convert('L')
                decoded_objects = decode(gray_image)

                # If still nothing, try upscaling (helps with small QR codes)
                if not decoded_objects:
                    logger.info("QR/Barcode: Trying upscaled image...")
                    upscaled = gray_image.resize(
                        (gray_image.width * 2, gray_image.height * 2),
                        Image.Resampling.LANCZOS
                    )
                    decoded_objects = decode(upscaled)

            if not decoded_objects:
                logger.info("QR/Barcode: No codes detected after all attempts")
                return ""

            results = []
            for obj in decoded_objects:
                code_type = obj.type  # QRCODE, EAN13, CODE128, etc.
                try:
                    data = obj.data.decode('utf-8')
                except:
                    data = obj.data.decode('latin-1', errors='ignore')

                logger.info(f"QR/Barcode detected: {code_type} = {data[:50]}...")
                results.append(f"{code_type}: {data}")

            return "\n".join(results)

        except ImportError:
            logger.warning("pyzbar not installed, skipping QR/barcode detection")
            return ""
        except Exception as e:
            logger.error(f"QR/Barcode decoding failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""

    async def analyze_multimodal(self, mime_type: str, data: bytes, user_prompt: str = "") -> str:
        """
        Analyzes multimodal content (Images, Audio, Video, PDF, Text) with fallback logic.
        """
        from src.prompts import ANALYSIS_SYSTEM_PROMPT
        full_prompt = f"{ANALYSIS_SYSTEM_PROMPT}\n\nUser Note: {user_prompt}"
        system_instruction = "You are a highly detailed assistant. You MUST respond ONLY in Russian (на русском языке). NEVER use English, even if the input is English. Translate extracted text if necessary."

        # --- STEP 0: Special handling for text-based documents ---
        text_mimes = ["text/plain", "text/csv", "text/markdown", "application/json"]
        if mime_type in text_mimes:
            try:
                text_content = data.decode('utf-8', errors='ignore')
                final_request = f"{full_prompt}\n\nDocument Content:\n{text_content}"
                print(f"    - Processing text document ({mime_type})...")
                # Use answer_question logic to get a summary
                return await self.answer_question(f"Type: {mime_type}\nContent:\n{text_content}", "Опиши и проанализируй этот документ максимально подробно.")
            except Exception as e:
                logger.warning(f"Failed to decode text document: {e}")

        # --- STEP 1: Try Google Direct (Multimodal) ---
        try:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-001')

            # Map MIME types if needed (Gemini SDK uses specific strings)
            # Gemini supports: image/*, audio/*, video/*, application/pdf
            print(f"    - Attempting Google Direct ({mime_type})...")

            # For PDF, we can use the Direct SDK
            response = await asyncio.to_thread(
                model.generate_content,
                [full_prompt, {"mime_type": mime_type, "data": data}]
            )

            if response and response.text:
                description = response.text

                # Add QR/Barcode detection for images
                if mime_type.startswith("image/"):
                    qr_data = self.decode_qr_barcode(data)
                    if qr_data:
                        description += f"\n\n📱 Распознанные коды:\n{qr_data}"

                return description

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg:
                logger.warning(f"Google Quota exhausted for multimodal. Falling back.")
                # await self._notify_admin(f"⚠️ Google {mime_type} quota exhausted. Using fallback.")
            else:
                logger.error(f"Google Direct Multimodal failed: {e}")

        # --- STEP 1.5: Whisper Fallback (Audio/Voice) ---
        if mime_type.startswith("audio/"):
            try:
                print(f"    - Attempting Whisper API Fallback ({mime_type})...")
                return await self._transcribe_via_whisper(data, mime_type)
            except Exception as e:
                logger.error(f"Whisper API failed: {e}")
                # await self._notify_admin(f"❌ Whisper API failed for audio: {str(e)[:100]}")

        # --- STEP 1.6: OpenRouter Vision Fallback (Images) ---
        if mime_type.startswith("image/"):
            try:
                print(f"    - Attempting OpenRouter Vision Fallback ({mime_type})...")
                # Encode image to base64
                base64_image = base64.b64encode(data).decode('utf-8')

                message = HumanMessage(
                    content=[
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                )
                # Use primary OpenRouter model (user's reliable one)
                response = await self.llm_openrouter.ainvoke([message])
                description = response.content

                # Add QR/Barcode detection for images (same as Google path)
                qr_data = self.decode_qr_barcode(data)
                if qr_data:
                    description += f"\n\n📱 Распознанные коды:\n{qr_data}"

                return description
            except Exception as e:
                logger.error(f"OpenRouter Vision failed: {e}")
                # await self._notify_admin(f"❌ OpenRouter Vision failed: {str(e)[:100]}")

        # --- STEP 2: PDF Local Extraction Fallback (if PDF) ---
        if mime_type == "application/pdf":
            try:
                print("    - Attempting local PDF text extraction fallback...")
                import io
                from pypdf import PdfReader
                pdf_file = io.BytesIO(data)
                reader = PdfReader(pdf_file)
                pdf_text = ""
                for page in reader.pages:
                    pdf_text += page.extract_text() + "\n"

                if pdf_text.strip():
                    return await self.answer_question(f"PDF Content:\n{pdf_text[:10000]}", "Опиши и проанализируй этот PDF документ.")
            except Exception as e:
                logger.error(f"Local PDF extraction failed: {e}")

        # --- STEP 3: Fallback to OpenRouter (Images/Audio/Video/General) ---
        try:
            print(f"    - Falling back to OpenRouter for {mime_type}...")

            if mime_type.startswith("image/"):
                encoded_data = base64.b64encode(data).decode('utf-8')
                message = [
                    SystemMessage(content=system_instruction),
                    HumanMessage(content=[
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_data}"}}
                    ])
                ]
                response = await self.llm_openrouter.ainvoke(message)
                return response.content
            else:
                # For non-image media on OpenRouter, try base64 trick or explain limitation
                encoded_data = base64.b64encode(data).decode('utf-8')
                message = [
                    SystemMessage(content=system_instruction),
                    HumanMessage(content=[
                        {"type": "text", "text": f"{full_prompt}\n(Processing media via secondary provider)"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_data}"}}
                    ])
                ]
                response = await self.llm_openrouter.ainvoke(message)
                return response.content

        except Exception as e:
            logger.error(f"Final fallback failed for multimodal: {e}")
            return f"Error: Не удалось проанализировать документ/медиа. (Ошибка: {str(e)})"

    async def _transcribe_via_whisper(self, audio_data: bytes, mime_type: str) -> str:
        """
        Whisper API fallback for audio transcription.
        Cost: $0.006 per minute
        """
        import tempfile
        import os

        # Whisper requires a file, not bytes
        # Map mime_type to file extension
        ext_map = {
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "audio/mp4": "m4a",
            "audio/wav": "wav",
            "audio/webm": "webm"
        }
        ext = ext_map.get(mime_type, "ogg")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            loop = asyncio.get_event_loop()
            with open(tmp_path, "rb") as audio_file:
                transcription = await loop.run_in_executor(
                    None,
                    lambda: self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ru",  # Russian for better accuracy
                        response_format="text"
                    )
                )

            # Format the response
            result = f"🎙️ Транскрипция (Whisper API):\n\n{transcription}"
            logger.info(f"Whisper transcription successful ({len(transcription)} chars)")
            return result
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def _notify_admin(self, message: str):
        """
        Sends notification to admin via Telegram.
        Used for quota exhaustion and critical errors.
        """
        try:
            # Import here to avoid circular dependency
            from src.main import telegram_app

            if telegram_app and telegram_app.bot:
                await telegram_app.bot.send_message(
                    chat_id=settings.TELEGRAM_ADMIN_ID,
                    text=f"🤖 Bot Alert:\n{message}"
                )
                logger.info(f"Admin notified: {message}")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
            # Don't raise - notification failure shouldn't break the main flow
