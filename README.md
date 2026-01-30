# 🧠 AI Second Brain Telegram Bot

A powerful, multimodal "Second Brain" Telegram bot that allows you to store, index, and retrieve any information (text, voice, images, videos, documents, locations). Powered by **Google Gemini**, **OpenRouter**, **Pinecone**, and **Whisper**.

## ✨ Key Features

### 🔐 Privacy & Security
- **Multi-User Isolation**: Data is separated by `chat_id`. Multiple users can use the same bot instance without seeing each other's data.

### 🎙️ Advanced Voice Interactions
- **Smart Intent Classification**: The bot automatically understands if you want to **SAVE** information or **QUERY** (search) for it.
- **Voice Search**: "Find the invoice from January" -> The bot searches your memory.
- **Voice Selection**: "Show result #2" -> The bot forwards the original message or detail.
- **Transcription**: All voice notes are transcribed (via OpenAI Whisper) and searchable.

### 📸 Multimodal Intelligence
- **Image Analysis**: Detailed descriptions of photos using Google Gemini 2.0 Flash (with OpenRouter fallback).
- **QR & Barcode Recognition**: Automatically detects and decodes QR codes/barcodes in images.
- **Video & Audio Analysis**: Summarizes video content and audio files.

### 📍 Location Intelligence
- **Geocoding**: Saves shared locations with address lookup (Reverse Geocoding via Nominatim).
- **Venue Support**: Recognizes specific places (restaurants, shops) if shared via Telegram.

### 🔍 Search & Retrieval
- **Semantic Search**: vector-based search using Pinecone.
- **Reranking**: LLM-based reranking for high relevance.
- **Reference System**: Search results are numbered ([#1], [#2]) for easy selection.

---

## 📂 Project Structure

```
python_bot/
├── run.py                 # Entry point to start the bot
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
│
└── src/
    ├── bot.py             # Main bot logic (handlers, message routing)
    ├── config.py          # Configuration loader
    ├── main.py            # Application builder & handler registration
    ├── prompts.py         # System prompts for AI analysis
    │
    └── services/
        ├── ai_service.py       # AI integration (Gemini, OpenRouter, Whisper, QR)
        ├── vector_db.py        # Pinecone database interactions
        └── content_processor.py # Link extraction and metadata
```

### Key Modules:
- **`ai_service.py`**: The "Brain". Handles all calls to LLMs (Google, OpenRouter), voice transcription (Whisper), and image tools (Pyzbar).
- **`vector_db.py`**: The "Memory". Manages upserting and searching vectors in Pinecone.
- **`bot.py`**: The "Interface". Processes Telegram updates, handles user flow, and manages the conversation state.

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd python_bot
   ```

2. **Create a virtual environment (Python 3.9+):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Note: For QR detection, ensure you have visual c++ redistributable installed on Windows or `libzbar0` on Linux.*

4. **Configure Environment:**
   Create a `.env` file based on `.env.example`:
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   OPENAI_API_KEY=your_key_for_whisper
   GOOGLE_API_KEY=your_gemini_key
   OPENROUTER_API_KEY=your_openrouter_key
   PINECONE_API_KEY=your_pinecone_key
   PINECONE_INDEX_NAME=your_index
   ```

5. **Run the Bot:**
   ```bash
   python run.py
   ```

---

## 📖 User Manual

### 1. Saving Information
Simply send any message to the bot. It will be analyzed, embedded, and saved to your private memory.
- **Text**: Notes, thoughts, links.
- **Photos**: Screenshots, receipts, QR codes (automatically decoded).
- **Voice**: "Remind me the door code is 1234" (Saved automatically).
- **Location**: Share a location to save a place.

### 2. Searching Information
You can ask questions via text or voice.
- **Text**: "Where is the office?", "Show me the QR code for wifi".
- **Voice**: Just ask! "Find the photo of the contract".

### 3. Selecting Results
When the bot finds multiple items, it shows a summary list:
> 1. 📄 Meeting Notes (Score: 0.95)
> 2. 📸 Screenshot (Score: 0.89)

To see the original item, you can say (text or voice):
- "Show number 1"
- "Open the second one"
- "Show #2"

The bot will forward the original message to you.

### 4. Special Features
- **QR Codes**: Send a photo of a QR code -> Bot replies with the decoded link/text.
- **Locations**: Send a location -> Bot saves the address and Google Maps link.
