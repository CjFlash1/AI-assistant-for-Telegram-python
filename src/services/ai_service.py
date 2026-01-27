from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.messages import HumanMessage, SystemMessage
from src.config import settings
import google.generativeai as genai
import logging
import base64
import asyncio
import traceback

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # 1. Embeddings: strictly Google (cheap, fast, specific model)
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.GOOGLE_API_KEY
        )

        # 2. Main Chat LLM: OpenRouter (Primary)
        # Using a model that provides good balance. User mentioned "Gemini 2.5 quality".
        self.llm_openrouter = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.0-flash-001",
            temperature=0.3,
        )

        # 3. Fallback/Media LLM: Google Direct (Secondary)
        # Used if OpenRouter fails or for specific tasks if needed.
        self.llm_google = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-001",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.3
        )

    async def get_embedding(self, text: str) -> list[float]:
        """Generates embedding for a given text."""
        try:
            return await self.embeddings.aembed_query(text)
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise e

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
            logger.warning(f"OpenRouter Answer failed ({e}), switching to Google direct fallback...")
            # Secondary: Google Direct
            try:
                response = await self.llm_google.ainvoke([system_msg, human_msg])
                return response.content
            except Exception as e2:
                logger.error(f"Both AI providers failed. Google error: {e2}")
                return "Извините, сейчас я не могу ответить на этот вопрос. Попробуйте еще раз позже."

    async def summarize_content(self, content: str) -> str:
        """Summarizes content to extract key information, with fallback logic."""
        prompt_text = f"Summarize the following content briefly, extracting the main points.\n\n{content}"

        # Prepare request - Combine System and Human messages
        system_msg = SystemMessage(content="You are a highly detailed assistant. You MUST respond ONLY in Russian (на русском языке). NEVER use English, even if the input is English.")
        human_msg = HumanMessage(content=prompt_text)

        # Try OpenRouter first
        try:
            response = await self.llm_openrouter.ainvoke([system_msg, human_msg])
            return response.content
        except Exception as e:
            logger.warning(f"OpenRouter summary failed, using fallback. Error: {e}")
            try:
                response = await self.llm_google.ainvoke([system_msg, human_msg])
                return response.content
            except Exception as e2:
                logger.error(f"Summary fallback failed: {e2}")
                return "Error summarizing content."

    async def analyze_multimodal(self, mime_type: str, data: bytes, user_prompt: str = "") -> str:
        """
        Analyzes multimodal content with fallback logic:
        1. Google Direct (Native SDK) - Free Tier
        2. OpenRouter (LangChain) - Paid Tier Fallback
        """
        from src.prompts import ANALYSIS_SYSTEM_PROMPT
        full_prompt = f"{ANALYSIS_SYSTEM_PROMPT}\n\nUser Note: {user_prompt}"

        # --- STEP 1: Try Google Direct ---
        try:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-001')

            print(f"    - Attempting Google Direct ({mime_type})...")
            response = await asyncio.to_thread(
                model.generate_content,
                [full_prompt, {"mime_type": mime_type, "data": data}]
            )

            if response and response.text:
                return response.text

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                logger.warning(f"Google Quota Exhausted, falling back to OpenRouter. Error: {e}")
            else:
                logger.error(f"Google Direct failed with non-quota error: {e}")
                # We still try fallback for other errors too

        # --- STEP 2: Fallback to OpenRouter ---
        try:
            print(f"    - Falling back to OpenRouter for {mime_type}...")

            if mime_type.startswith("image/"):
                # OpenRouter supports images via standard OpenAI format
                encoded_data = base64.b64encode(data).decode('utf-8')
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded_data}"}
                        }
                    ]
                )
                response = await self.llm_openrouter.ainvoke([message])
                return response.content
            else:
                # For Audio/Video, OpenRouter's support via LangChain is limited.
                # However, we can try to pass it as a generic media or inform the user.
                # For now, we try to use the same 'image_url' trick which sometimes works for Gemini on OpenRouter.
                encoded_data = base64.b64encode(data).decode('utf-8')
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url", # Generic media trick
                            "image_url": {"url": f"data:{mime_type};base64,{encoded_data}"}
                        }
                    ]
                )
                response = await self.llm_openrouter.ainvoke([message])
                return response.content

        except Exception as e:
            logger.error(f"Both Google and OpenRouter failed for multimodal: {e}")
            logger.error(traceback.format_exc())
            return f"Error: All AI providers failed or quota reached. (Last error: {str(e)})"
