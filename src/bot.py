import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.services.ai_service import AIService
from src.services.vector_db import VectorDBService
from src.services.content_processor import ContentProcessor
from src.utils import check_file_size
import traceback

logger = logging.getLogger(__name__)

# Initialize Services
# Note: In a real app, these singleton instantiations might be better in a startup event or dependencies
ai_service = AIService()
vector_db = VectorDBService()
content_processor = ContentProcessor()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text("Hello! I am your AI Assistant. Send me links or ask questions.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    text = update.message.text
    if not text:
        return

    # 1. Check if it's a URL
    if "http" in text:
        await update.message.reply_text("Processing link...")

        # Extract metadata
        # Splitting by space to find the first URL (simplified)
        url = next((word for word in text.split() if word.startswith("http")), None)

        metadata = content_processor.extract_link_metadata(url)
        if metadata:
            summary = await ai_service.summarize_content(metadata["content"])

            # Create a vector
            # We embed the summary + title for better retrieval
            doc_text = f"{metadata['title']}\n{summary}"
            embedding = await ai_service.get_embedding(doc_text)

            # Upsert to Pinecone
            # ID could be URL hash or random
            doc_id = str(hash(url))
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
        # 2. Treat as a question
        await update.message.reply_chat_action("typing")

        # Generate embedding for the question
        q_embedding = await ai_service.get_embedding(text)

        # Search Vector DB
        results = await vector_db.search(q_embedding, top_k=3)

        context_text = ""
        if results and results.matches:
            logger.info(f"Found {len(results.matches)} matches")
            for match in results.matches:
                logger.info(f"Match score: {match.score}")
                if match.score > 0.5: # Lowered threshold for better recall
                    meta = match.metadata
                    # Handle both 'text' and 'content' keys just in case
                    content = meta.get('text') or meta.get('content') or "No content"
                    title = meta.get('title', 'Unknown Source')
                    context_text += f"---\nSourceType: {meta.get('type', 'unknown')}\nTitle: {title}\nContent: {content}\n---\n\n"

        if not context_text:
            context_text = "No specific context found in memory."
            logger.info("No context found above threshold.")

        # Forward best match if confidence is high or intent is clear
        if results and results.matches:
            best_match = results.matches[0]

            # Detect explicit intent to "send" or "show"
            intent_keywords = ["пришли", "отправь", "покажи", "скинь", "дай", "найди", "выдай", "show", "send", "find"]
            has_retrieval_intent = any(kw in text.lower() for kw in intent_keywords)

            # Dynamic threshold: lower it if user explicitly asked
            forward_threshold = 0.55 if has_retrieval_intent else 0.7

            if best_match.score > forward_threshold:
                meta = best_match.metadata
                origin_chat_id = meta.get('chat_id')
                origin_message_id = meta.get('message_id')

                if origin_chat_id and origin_message_id:
                    try:
                        # Use copy_message instead of forward_message to support reply_to_message_id
                        await context.bot.copy_message(
                            chat_id=update.message.chat_id,
                            from_chat_id=origin_chat_id,
                            message_id=origin_message_id,
                            reply_to_message_id=update.message.message_id
                        )
                        logger.info(f"Successfully sent copy of message {origin_message_id} as reply")
                    except Exception as e:
                        logger.warning(f"Failed to copy message (probably deleted or restricted): {e}")
                        await update.message.reply_text("ℹ (Оригинальное сообщение удалено или недоступно, но вот информация из него):")

        # Prepare request - Explicitly ask for Russian
        prompt_with_russian_instruction = f"Answer the following question based on the context. YOU MUST RESPOND ONLY IN RUSSIAN (НА РУССКОМ ЯЗЫКЕ). Even if the context is in English, translate the important bits to Russian.\n\nContext:\n{context_text}\n\nQuestion: {text}"
        answer = await ai_service.answer_question(context_text, prompt_with_russian_instruction)
        await update.message.reply_text(answer)

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

        doc_id = str(hash(bytes(data)))
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

        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)

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
    if not update.message.voice: return
    await process_media(update, context, update.message.voice, "audio/ogg", "voice_note", "Transcribe and analyze intonation")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.audio: return
    mime = update.message.audio.mime_type or "audio/mpeg"
    await process_media(update, context, update.message.audio, mime, "audio_file", "Analyze music/audio")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc: return
    mime = doc.mime_type or ""
    if mime.startswith("image") or mime.startswith("video") or mime.startswith("audio"):
        await process_media(update, context, doc, mime, "document_media", "Analyze this attached media")
    else:
         await update.message.reply_text("I see the document, but deep analysis for this file type is coming soon.")

def setup_handlers(application):
    """Registers handlers to the application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
