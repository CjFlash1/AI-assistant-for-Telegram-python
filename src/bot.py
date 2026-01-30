import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.services.ai_service import AIService
from src.services.vector_db import VectorDBService
from src.services.content_processor import ContentProcessor
from src.utils import check_file_size
import traceback
import hashlib
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Initialize Services
# Note: In a real app, these singleton instantiations might be better in a startup event or dependencies
ai_service = AIService()
vector_db = VectorDBService()
content_processor = ContentProcessor()

# Search results cache for two-stage retrieval
# Format: {user_id: {'matches': [...], 'timestamp': datetime}}
user_search_cache = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text("Hello! I am your AI Assistant. Send me links or ask questions.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    text = update.message.text
    if not text:
        return

    user_id = update.message.from_user.id

    # 0. Check for "покажи #N" command (two-stage retrieval)
    show_match = re.match(r'покажи\s+(?:#)?(\d+)', text.lower().strip())
    if show_match:
        result_num = int(show_match.group(1))
        await handle_show_result(update, context, user_id, result_num)
        return

    # 1. Check if it's a URL
    if "http" in text:
        await update.message.reply_text("Processing link...")

        # Extract metadata
        # Splitting by space to find the first URL (simplified)
        url = next((word for word in text.split() if word.startswith("http")), None)

        metadata = await content_processor.extract_link_metadata(url)
        if metadata:
            summary = await ai_service.summarize_content(metadata["content"])

            # Create a vector
            # We embed the summary + title for better retrieval
            doc_text = f"{metadata['title']}\n{summary}"
            embedding = await ai_service.get_embedding(doc_text)

            # Upsert to Pinecone
            # ID could be URL hash or random
            doc_id = hashlib.sha256(url.encode()).hexdigest()
            upsert_metadata = {
                "url": url,
                "title": metadata["title"],
                "text": summary, # Storing summary in metadata for context retrieval
                "type": "link",
                "chat_id": update.message.chat_id,
                "message_id": update.message.message_id,
                "thread_id": update.message.message_thread_id
            }

            success = await vector_db.upsert(doc_id, embedding, upsert_metadata)

            if success:
                # Send full analysis for links too
                await update.message.reply_text(f"✅ Analyzed Link:\n\n{summary}")
            else:
                await update.message.reply_text("Failed to save to memory.")
        else:
            await update.message.reply_text("Could not extract content from link.")

    else:
        # 1. Classify Intent
        classification = await ai_service.classify_intent(text)
        intent = classification.get("intent", "ASK")
        search_filter = classification.get("filter") or {}

        # Enforce Chat ID filter for privacy
        search_filter["chat_id"] = update.effective_chat.id

        logger.info(f"Intent classified: {intent}, Filter: {search_filter}")

        # 2. Treat as a question
        await update.message.reply_chat_action("typing")

        # Generate embedding for the question
        q_embedding = await ai_service.get_embedding(text)

        # Search Vector DB with Filter
        results = await vector_db.search(q_embedding, top_k=20, filter=search_filter)

        context_text = ""
        relevant_matches = []

        if results and results.matches:
            # 3. Smart Re-ranking with LLM
            relevant_matches = await ai_service.rerank_results(text, results.matches)

            # Cache results for two-stage retrieval
            user_search_cache[user_id] = {
                'matches': relevant_matches,
                'timestamp': datetime.now()
            }

            # Combine text for AI answer from RERANKED results (not raw)
            for match in relevant_matches[:5]:
                context_text += f"{match.metadata.get('text', '')}\n---\n"

        # 4. Two-Stage Retrieval: Show text summary or auto-forward single result
        if relevant_matches:
            if len(relevant_matches) == 1:
                # Single result: forward immediately with short description
                match = relevant_matches[0]
                meta = match.metadata

                # Show short description first
                type_emoji = {
                    "image": "📸",
                    "video": "🎥",
                    "document": "📄",
                    "voice_note": "🎙️",
                    "audio": "🎵",
                    "link": "🔗"
                }.get(meta.get('type'), "📎")

                description = meta.get('text', 'Нет описания')[:150]
                if len(meta.get('text', '')) > 150:
                    description += "..."

                await update.message.reply_text(f"🔍 Нашёл:\n{type_emoji} {meta.get('type', 'контент')}\n{description}")

                # Try to forward original
                origin_chat_id = meta.get('chat_id')
                origin_message_id = meta.get('message_id')

                if origin_chat_id and origin_message_id:
                    try:
                        msg_id = int(float(origin_message_id))
                        chat_id = int(float(origin_chat_id))

                        await context.bot.copy_message(
                            chat_id=update.message.chat_id,
                            from_chat_id=chat_id,
                            message_id=msg_id,
                            reply_to_message_id=update.message.message_id
                        )
                    except Exception as e:
                        logger.warning(f"Failed to copy single result: {e}")
                        # Already showed description, so user has the info
            else:
                # Multiple results: show summary with reference keys
                summary = await create_search_summary(relevant_matches, text)
                await update.message.reply_text(summary)
        else:
            # No relevant matches (either no results or reranking filtered all)
            await update.message.reply_text(
                "К сожалению, я не нашел информации по вашему запросу в своей памяти.\n\n"
                "💡 Попробуйте:\n"
                "• Переформулировать запрос\n"
                "• Использовать другие ключевые слова\n"
                "• Проверить, сохранена ли эта информация"
            )

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE, file_obj, mime_type: str, type_label: str, user_note: str = ""):
    """Generic media processor."""
    print(f">>> Processing {type_label} (mime: {mime_type})")
    try:
        if hasattr(file_obj, 'file_size') and not check_file_size(file_obj.file_size):
            await update.message.reply_text("File too large (>20MB). Skipping analysis.")
            return

        await update.message.reply_chat_action("upload_document")

        status_msg = await update.message.reply_text(f"Analyzing {type_label}...")

        print(f"    - Downloading {type_label}...")
        new_file = await file_obj.get_file()
        data = await new_file.download_as_bytearray()

        print(f"    - Analyzing via AI...")
        description = await ai_service.analyze_multimodal(mime_type, bytes(data), user_note)
        print(f"    - AI Result: {description[:50]}...")

        # Use SHA-256 for stable content tracking
        doc_id = hashlib.sha256(bytes(data)).hexdigest()
        upsert_metadata = {
            "text": description,
            "type": type_label,
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "thread_id": update.message.message_thread_id,
            "mime": mime_type
        }

        embedding = await ai_service.get_embedding(f"{type_label}: {description}")
        success = await vector_db.upsert(doc_id, embedding, upsert_metadata)

        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        except:
            pass  # Message already deleted

        if success:
            await update.message.reply_text(f"✅ Saved {type_label}:\n\n{description}")
        else:
             await update.message.reply_text(f"⚠ Analyzed but DB failed:\n\n{description}")

    except Exception as e:
        logger.error(f"Media Process Error: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text("Error processing media.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: return
    photo = update.message.photo[-1]
    await process_media(update, context, photo, "image/jpeg", "image", "Analyze this image")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_obj = update.message.video or update.message.video_note
    if not video_obj: return
    await process_media(update, context, video_obj, "video/mp4", "video", "Analyze this video content.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages with intent classification."""
    if not update.message.voice:
        return

    voice = update.message.voice

    # Download and transcribe
    status_msg = await update.message.reply_text("🎙️ Обрабатываю голосовое сообщение...")

    try:
        new_file = await context.bot.get_file(voice.file_id)
        data = await new_file.download_as_bytearray()

        # Transcribe using AI (Google or Whisper fallback)
        transcription = await ai_service.analyze_multimodal("audio/ogg", bytes(data), "Transcribe this voice message")

        # Extract just the text from the transcription result
        # The result might be formatted like "🎙️ Транскрипция:\n\n<text>"
        transcription_text = transcription.split("\n\n", 1)[-1] if "\n\n" in transcription else transcription
        transcription_text = transcription_text.replace("🎙️ Транскрипция (Whisper API):", "").strip()
        transcription_text = transcription_text.replace("Транскрипция:", "").strip()

        logger.info(f"Voice transcribed: {transcription_text[:100]}...")

        # Classify intent
        classification_result = await ai_service.classify_voice_intent(transcription_text)
        intent = classification_result.get("intent", "SAVE")
        result_num = classification_result.get("number")

        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        except:
            pass

        # Show transcribed text to user
        if intent in ["QUERY", "SELECT"]:
             await update.message.reply_text(f"🗣️ \"{transcription_text}\"")

        if intent == "SELECT" and result_num:
            # Handle selection command (e.g., "show number 2")
            logger.info(f"Voice classified as SELECT: #{result_num}")
            user_id = update.message.from_user.id
            await handle_show_result(update, context, user_id, int(result_num))

        elif intent == "QUERY":
            # Treat as a text query - call search logic directly
            logger.info(f"Voice classified as QUERY, processing as search...")

            # Classify intent for search
            classification = await ai_service.classify_intent(transcription_text)
            search_intent = classification.get("intent", "ASK")
            search_filter = classification.get("filter")

            logger.info(f"Search intent: {search_intent}, Filter: {search_filter}")

            # Generate embedding and search
            await update.message.reply_chat_action("typing")
            q_embedding = await ai_service.get_embedding(transcription_text)
            results = await vector_db.search(q_embedding, top_k=20, filter=search_filter)

            context_text = ""
            relevant_matches = []

            if results and results.matches:
                relevant_matches = await ai_service.rerank_results(transcription_text, results.matches)

                # Cache results
                user_id = update.message.from_user.id
                user_search_cache[user_id] = {
                    'matches': relevant_matches,
                    'timestamp': datetime.now()
                }

                for match in relevant_matches[:5]:
                    context_text += f"{match.metadata.get('text', '')}\n---\n"

            # Show results
            if relevant_matches:
                if len(relevant_matches) == 1:
                    # Single result: forward with description
                    match = relevant_matches[0]
                    meta = match.metadata

                    type_emoji = {
                        "image": "📸", "video": "🎥", "document": "📄",
                        "voice_note": "🎙️", "audio": "🎵", "link": "🔗"
                    }.get(meta.get('type'), "📎")

                    description = meta.get('text', 'Нет описания')[:150]
                    if len(meta.get('text', '')) > 150:
                        description += "..."

                    await update.message.reply_text(f"🔍 Нашёл:\n{type_emoji} {meta.get('type', 'контент')}\n{description}")

                    # Try to forward original
                    if meta.get('chat_id') and meta.get('message_id'):
                        try:
                            await context.bot.copy_message(
                                chat_id=update.message.chat_id,
                                from_chat_id=int(float(meta.get('chat_id'))),
                                message_id=int(float(meta.get('message_id'))),
                                reply_to_message_id=update.message.message_id
                            )
                        except Exception as e:
                            logger.warning(f"Failed to copy single result: {e}")
                else:
                    # Multiple results: show summary
                    summary = await create_search_summary(relevant_matches, transcription_text)
                    await update.message.reply_text(summary)
            else:
                await update.message.reply_text(
                    "К сожалению, я не нашел информации по вашему запросу в своей памяти.\n\n"
                    "💡 Попробуйте:\n"
                    "• Переформулировать запрос\n"
                    "• Использовать другие ключевые слова\n"
                    "• Проверить, сохранена ли эта информация"
                )
        else:
            # SAVE: Process as media (original behavior)
            logger.info(f"Voice classified as SAVE, storing...")
            await process_media(update, context, voice, "audio/ogg", "voice_note", f"Voice note: {transcription_text[:100]}")

    except Exception as e:
        logger.error(f"Voice processing failed: {e}")
        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        except:
            pass  # Message already deleted or inaccessible
        await update.message.reply_text(f"Ошибка обработки голосового сообщения: {str(e)[:100]}")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.audio: return
    mime = update.message.audio.mime_type or "audio/mpeg"
    await process_media(update, context, update.message.audio, mime, "audio_file", "Analyze music/audio")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location messages with reverse geocoding."""
    location = update.message.location
    if not location:
        return

    latitude = location.latitude
    longitude = location.longitude

    status_msg = await update.message.reply_text("📍 Обрабатываю геолокацию...")

    try:
        address = "Адрес не определён"
        place_name = ""

        # 1. Check if it's a Venue (has name/address from Telegram)
        if update.message.venue:
            venue = update.message.venue
            place_name = venue.title
            address = venue.address
            logger.info(f"Venue detected: {place_name} ({address})")

        # 2. If no address yet, try Reverse Geocoding
        if address == "Адрес не определён" or not address:
            try:
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="telegram_memory_bot")
                location_info = await asyncio.to_thread(
                    geolocator.reverse,
                    f"{latitude}, {longitude}",
                    language="ru"
                )
                address = location_info.address if location_info else "Адрес не найден"
            except Exception as e:
                logger.warning(f"Geocoding failed: {e}")

        # Create description
        description = f"📍 Геолокация"
        if place_name:
            description += f": {place_name}"

        description += f"""
Координаты: {latitude}, {longitude}
Адрес: {address}

🗺️ Google Maps: https://maps.google.com/?q={latitude},{longitude}
"""

        # Save to vector DB
        embedding = await ai_service.get_embedding(f"Место: {address}")
        doc_id = hashlib.sha256(f"{latitude}{longitude}".encode()).hexdigest()

        metadata = {
            "text": description,
            "type": "location",
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "thread_id": update.message.message_thread_id
        }

        success = await vector_db.upsert(doc_id, embedding, metadata)

        try:
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        except:
            pass  # Message already deleted

        if success:
            await update.message.reply_text(f"✅ Сохранено:\n{description}")
        else:
            await update.message.reply_text("Ошибка сохранения геолокации.")

    except Exception as e:
        logger.error(f"Location processing failed: {e}")
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        await update.message.reply_text(f"Ошибка обработки геолокации: {str(e)[:100]}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc: return

    mime_type = doc.mime_type or "application/octet-stream"
    file_name = doc.file_name or "document"

    # Process all documents using multimodal analysis
    label = f"document ({file_name})"
    await process_media(update, context, doc, mime_type, label, f"Analyze this document: {file_name}")

async def create_search_summary(matches: list, query: str) -> str:
    """
    Creates a text summary with reference keys [#1], [#2], etc.
    """
    if not matches:
        return "Ничего не найдено."

    # Limit to top 5 results
    top_matches = matches[:5]

    summary_parts = [f"🔍 Нашёл {len(matches)} совпадений по запросу:\n"]

    for idx, match in enumerate(top_matches, 1):
        meta = match.metadata

        # Type emoji mapping
        type_emoji = {
            "image": "📸",
            "video": "🎥",
            "document": "📄",
            "voice_note": "🎙️",
            "audio": "🎵",
            "link": "🔗"
        }.get(meta.get('type'), "📎")

        # Get text preview
        text_preview = meta.get('text', 'Нет описания')[:200]
        if len(meta.get('text', '')) > 200:
            text_preview += "..."

        # Format entry
        type_label = meta.get('type', 'контент')
        summary_parts.append(
            f"[#{idx}] {type_emoji} {type_label}\n"
            f"{text_preview}\n"
        )

    # Add hint
    if len(matches) > 5:
        summary_parts.append(f"\n📌 Показаны топ-5 из {len(matches)} результатов.")

    summary_parts.append("\n💡 Напиши 'покажи #2' чтобы увидеть оригинал.")

    return "\n".join(summary_parts)

async def handle_show_result(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, result_num: int):
    """
    Handles 'покажи #N' command to show original message or DB data.
    """
    # Check if user has cached results
    if user_id not in user_search_cache:
        await update.message.reply_text("Сначала задай вопрос, чтобы я нашёл информацию.")
        return

    cache_entry = user_search_cache[user_id]
    matches = cache_entry['matches']

    # Check if result number is valid
    if result_num < 1 or result_num > len(matches):
        await update.message.reply_text(f"Результат #{result_num} не найден. Доступны результаты от #1 до #{len(matches)}.")
        return

    match = matches[result_num - 1]
    meta = match.metadata

    # Try to forward original message
    origin_chat_id = meta.get('chat_id')
    origin_message_id = meta.get('message_id')

    if origin_chat_id and origin_message_id:
        try:
            msg_id = int(float(origin_message_id))
            chat_id = int(float(origin_chat_id))

            logger.info(f"Forwarding result #{result_num}: {meta.get('type')} from {chat_id}:{msg_id}")
            await context.bot.copy_message(
                chat_id=update.message.chat_id,
                from_chat_id=chat_id,
                message_id=msg_id,
                reply_to_message_id=update.message.message_id
            )
            return
        except Exception as e:
            logger.warning(f"Failed to copy message #{result_num}: {e}")

    # Fallback: Show DB data for deleted/inaccessible message
    await show_deleted_message_info(update, meta, result_num)

async def show_deleted_message_info(update: Update, meta: dict, result_num: int):
    """
    Shows maximum information from DB about a deleted/inaccessible message.
    """
    type_emoji = {
        "image": "📸",
        "video": "🎥",
        "document": "📄",
        "voice_note": "🎙️",
        "audio": "🎵",
        "link": "🔗"
    }.get(meta.get('type'), "📎")

    info_parts = [
        f"⚠️ Оригинал сообщения [#{result_num}] недоступен (удалён или нет доступа).\n",
        f"{type_emoji} **{meta.get('type', 'Контент').capitalize()}**",
        f"Чат ID: `{meta.get('chat_id', 'N/A')}`",
        f"Сообщение ID: `{meta.get('message_id', 'N/A')}`",
        "",
        "**Что я помню:**",
        meta.get('text', 'Нет описания')
    ]

    if meta.get('url'):
        info_parts.append(f"\n🔗 Ссылка: {meta['url']}")

    await update.message.reply_text("\n".join(info_parts))

def setup_handlers(application):
    """Registers handlers to the application."""
    # Debug log for all updates
    async def debug_log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"Incoming Update: Type={'Text' if update.message and update.message.text else 'Other'}, Chat={update.effective_chat.id if update.effective_chat else 'N/A'}")
        return

    application.add_handler(MessageHandler(filters.ALL, debug_log_update), group=-1)

    application.add_handler(CommandHandler("start", start_command))

    # Catch-all text handler (includes groups/channels if privacy disabled)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Explicitly catch media with or without captions
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Debug: Catch anything else to log it
    async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"Unhandled Update: {update.to_dict()}")

    application.add_handler(MessageHandler(filters.ALL, fallback_handler), group=99)

    # Global Error Handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Exception while handling an update: {context.error}")
        logger.error(traceback.format_exc())
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                await update.effective_message.reply_text("Произошла ошибка при обработке запроса. Попробуйте еще раз.")
            except Exception:
                pass  # Can't reply, just log

    application.add_error_handler(error_handler)
