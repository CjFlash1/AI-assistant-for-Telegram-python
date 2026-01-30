# 🧠 AI Second Brain Telegram Bot / ИИ Бот "Второй Мозг"

[English](#english) | [Русский](#русский)

---

<a name="english"></a>
## 🇬🇧 English Documentation

A powerful, multimodal "Second Brain" Telegram bot that allows you to store, index, and retrieve any information (text, voice, images, videos, documents, locations). Powered by **Google Gemini**, **OpenRouter**, **Pinecone**, and **Whisper**.

### ✨ Key Features

#### 🔐 Privacy & Security
- **Multi-User Isolation**: Data is separated by `chat_id`. Multiple users can use the same bot instance without seeing each other's data.

#### 🎙️ Advanced Voice Interactions
- **Smart Intent Classification**: The bot automatically understands if you want to **SAVE** information, **QUERY** (search) for it, or **SELECT** a result.
- **Voice Search**: "Find the invoice from January" -> The bot searches your memory.
- **Voice Selection**: "Show result #2" -> The bot forwards the original message or detail.
- **Transcription**: All voice notes are transcribed (via OpenAI Whisper) and searchable.

#### 📸 Multimodal Intelligence
- **Image Analysis**: Detailed descriptions of photos using Google Gemini 2.0 Flash (with OpenRouter fallback).
- **QR & Barcode Recognition**: Automatically detects and decodes QR codes/barcodes in images using `pyzbar`.
- **Video & Audio Analysis**: Summarizes video content and audio files.

#### 📍 Location Intelligence
- **Geocoding**: Saves shared locations with address lookup (Reverse Geocoding via Nominatim).
- **Venue Support**: Recognizes specific places (restaurants, shops) if shared via Telegram.

#### 🔍 Search & Retrieval
- **Semantic Search**: Vector-based search using Pinecone embeddings.
- **Reranking**: LLM-based reranking for high relevance.
- **Reference System**: Search results are numbered ([#1], [#2]) for easy selection.

---

### 📂 Project Structure

```
python_bot/
├── run.py                 # Entry point to start the bot
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
│
└── src/
    ├── bot.py             # Main bot logic (handlers, message routing, voice/text flow)
    ├── config.py          # Configuration loader
    ├── main.py            # Application builder & handler registration
    ├── prompts.py         # System prompts for AI analysis
    │
    └── services/
        ├── ai_service.py       # AI integration (Gemini, OpenRouter, Whisper, QR decoding)
        ├── vector_db.py        # Pinecone database interactions (Upsert, Search)
        └── content_processor.py # Link extraction and metadata processing
```

### 🚀 Installation & Setup

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
   *Note: For QR detection, ensure you have Visual C++ Redistributable installed on Windows or `libzbar0` on Linux.*

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

### 📖 User Manual

**1. Saving Information**
Simply send any message to the bot. It will be analyzed, embedded, and saved to your private memory.
- **Text**: Notes, thoughts, links.
- **Photos**: Screenshots, receipts, QR codes (automatically decoded).
- **Voice**: "Remind me the door code is 1234" (Saved automatically).
- **Location**: Share a location to save a place with its address.

**2. Searching Information**
You can ask questions via text or voice.
- **Text**: "Where is the office?", "Show me the QR code for wifi".
- **Voice**: Just ask! "Find the photo of the contract".

**3. Selecting Results**
When the bot finds multiple items, it shows a summary list:
> 1. 📄 Meeting Notes (Score: 0.95)
> 2. 📸 Screenshot (Score: 0.89)

To see the original item, you can say (text or voice):
- "Show number 1"
- "Open the second one"
- "Show #2"

---

<a name="русский"></a>
## 🇷🇺 Документация на Русском

Мощный мультимодальный Телеграм-бот "Второй Мозг", который позволяет сохранять, индексировать и находить любую информацию (текст, голосовые, фото, видео, документы, локации). Использует технологии **Google Gemini**, **OpenRouter**, **Pinecone** и **Whisper**.

### ✨ Ключевые Возможности

#### 🔐 Приватность и Безопасность
- **Изоляция Пользователей**: Данные разделены по `chat_id`. Несколько пользователей могут использовать одного бота, и каждый будет видеть только свои данные.

#### 🎙️ Голосовое Управление
- **Умная Классификация**: Бот автоматически понимает, хотите ли вы **СОХРАНИТЬ** информацию или **НАЙТИ** (запросить) её.
- **Поиск Голосом**: "Найди счет за январь" -> Бот ищет в вашей базе знаний.
- **Выбор Голосом**: "Покажи номер 2" -> Бот пересылает оригинальное сообщение или детали.
- **Транскрибация**: Все голосовые заметки расшифровываются (OpenAI Whisper) и становятся доступными для текстового поиска.

#### 📸 Мультимодальный Интеллект
- **Анализ Изображений**: Подробное описание фото с помощью Google Gemini 2.0 Flash (с резервным каналом OpenRouter).
- **QR и Штрихкоды**: Автоматическое обнаружение и декодирование QR-кодов на фото (через `pyzbar`).
- **Видео и Аудио**: Суммаризация содержимого видео и аудиофайлов.

#### 📍 Геолокация
- **Геокодинг**: Сохранение отправленных локаций с автоматическим поиском адреса (через Nominatim).
- **Поддержка Заведений**: Распознавание конкретных мест (название магазина, кафе), если они указаны при отправке.

#### 🔍 Поиск
- **Семантический Поиск**: Векторный поиск через Pinecone.
- **Reranking**: Умная сортировка результатов с помощью LLM для максимальной точности.
- **Система Ссылок**: Результаты нумеруются ([#1], [#2]) для удобного выбора.

---

### 📂 Структура Проекта

```
python_bot/
├── run.py                 # Точка входа для запуска бота
├── requirements.txt       # Python зависимости
├── .env                   # Переменные окружения (API ключи)
│
└── src/
    ├── bot.py             # Основная логика бота (хендлеры, маршрутизация сообщений)
    ├── config.py          # Загрузка конфигурации
    ├── main.py            # Сборка приложения
    ├── prompts.py         # Системные промпты для AI
    │
    └── services/
        ├── ai_service.py       # Интеграция с AI (Gemini, OpenRouter, Whisper, QR)
        ├── vector_db.py        # Работа с базой данных Pinecone
        └── content_processor.py # Извлечение метаданных из ссылок
```

### 🚀 Установка и Запуск

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repo-url>
   cd python_bot
   ```

2. **Создайте виртуальное окружение (Python 3.9+):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```
   *Примечание: Для работы с QR-кодами убедитесь, что установлен Visual C++ Redistributable (Windows) или `libzbar0` (Linux).*

4. **Настройте окружение (.env):**
   Создайте файл `.env` (можно скопировать `.env.example`):
   ```env
   TELEGRAM_BOT_TOKEN=ваш_токен
   OPENAI_API_KEY=ключ_для_whisper
   GOOGLE_API_KEY=ключ_gemini
   OPENROUTER_API_KEY=ключ_openrouter
   PINECONE_API_KEY=ключ_pinecone
   PINECONE_INDEX_NAME=имя_индекса
   ```

5. **Запустите бота:**
   ```bash
   python run.py
   ```

### 📖 Инструкция Пользователя

**1. Сохранение Информации**
Просто отправьте любое сообщение боту. Он проанализирует его, сохранит в векторную базу и запомнит.
- **Текст**: Заметки, идеи, ссылки.
- **Фото**: Скриншоты, чеки, QR-коды (распознаются автоматически).
- **Голос**: "Напомни, код от двери 1234" (Сохраняется автоматически).
- **Локация**: Отправьте геопозицию, чтобы сохранить место и адрес.

**2. Поиск Информации**
Задавайте вопросы текстом или голосом.
- **Текст**: "Где находится офис?", "Покажи QR код от вайфая".
- **Голос**: Просто спросите! "Найди фото договора".

**3. Выбор Результата**
Если бот нашел несколько вариантов, он покажет список:
> 1. 📄 Заметки встречи (Score: 0.95)
> 2. 📸 Скриншот (Score: 0.89)

Чтобы увидеть оригинал, скажите (текстом или голосом):
- "Покажи номер 1"
- "Открой второй"
- "Давай #2"
