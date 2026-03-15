# Neural Inbox

## Introduction

I am a first-year student specializing in Big Data Analysis, and this is my project.

**Neural Inbox serves as the logical continuation of my previous project, [Smart Tasker Bot](https://github.com/sabr2007/smart-tasker-bot).** While Smart Tasker was highly effective at scheduling and task management, I realized I needed a system that could do more than just remind me of deadlines. Neural Inbox was designed from the ground up to be a complete "Second Brain."

The key difference in this evolution is the underlying architecture: Neural Inbox leverages vector embeddings and semantic search. This means it doesn't just record tasks—it actively understands the context of your notes, connects related ideas, and retrieves resources based on meaning rather than just exact keywords.

## Project Overview

Neural Inbox is an AI-powered personal assistant integrated directly into Telegram. It uses natural language processing, multimodal AI, and semantic search to manage your tasks, ideas, notes, and projects. Whether you send a quick text, a voice message on the go, a photo, or a document, the bot understands the context, extracts the key entities, and organizes them perfectly in a builtin Telegram Mini App.

## Key Features

* **The "Second Brain" Concept:** Moving beyond simple to-do lists, the system categorizes your inputs into tasks, ideas, notes, resources, or contacts, automatically structuring the chaos of daily life.
* **Semantic Search & Auto-Linking:** The core differentiator. It uses vector embeddings to automatically suggest links between related notes, ideas, and tasks. You can find what you're looking for by searching for concepts, even if you don't remember the exact phrasing.
* **Multimodal Input Processing:** Send text, voice messages, photos, or documents (PDF, DOCX). The system automatically transcribes voice notes using OpenAI's Whisper and analyzes images using GPT-4o Vision.
* **Intelligent Entity Extraction:** The AI understands context, parses relative dates (e.g., "tomorrow at 10"), extracts actionable items, and sets up deadlines without manual data entry.
* **Telegram Mini App Dashboard:** A visual interface built with React and Tailwind CSS that allows you to manage projects, view tasks on a calendar, and search through your inbox without leaving Telegram.
* **Reliable Reminders & Recurrence:** Set up daily, weekly, or monthly recurring tasks. The bot sends automated push notifications with interactive quick actions (Complete, Snooze).

## Technical Architecture

This project features a hybrid architecture combining an asynchronous Telegram bot for immediate interactions, a fast web backend API, and a modern frontend for the Mini App, all orchestrated by an autonomous AI agent layer.

## Technology Stack

* **Core:** Python 3.11+
* **Bot Framework:** `aiogram` (Asynchronous)
* **Web Backend:** FastAPI, Uvicorn
* **Database:** PostgreSQL with the `pgvector` extension, `asyncpg`, SQLAlchemy, and Alembic
* **Frontend:** React, Vite, Tailwind CSS, TanStack Query
* **AI Engine:** OpenAI API (`gpt-4o`, `gpt-4o-mini`, Whisper, `text-embedding-3-small`)

## How It Works

1. **Input Analysis:** User messages (text, voice, images, documents) are intercepted and pre-processed. Voice is transcribed and images are analyzed.
2. **Entity Structuring:** The Intelligent Agent passes the context to the LLM to extract structured data (tasks, dates, projects, recurrence patterns) and categorize the information as a note, task, or resource.
3. **Vectorization & Storage:** Items are stored in a PostgreSQL database. Simultaneously, vector embeddings are generated via OpenAI and stored using `pgvector` to enable the hybrid semantic search and auto-linking features.
4. **Interface Integration:** The React-based Telegram WebApp fetches data via the FastAPI backend, providing a seamless visual UI to drag, edit, and navigate through your second brain.

## Getting Started

Follow these steps to deploy the bot locally.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd neural-inbox1

```

### 2. Environment Configuration

Create a `.env` file in the root directory with the following variables:

```ini
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
WEBAPP_URL=https://your-webapp-url.com # Optional, used for the Mini App button

```

### 3. Build the Frontend

```bash
cd webapp
npm install
npm run build
cd ..

```

### 4. Install Backend Dependencies

```bash
pip install -r requirements.txt

```

### 5. Launch

```bash
python -m src.main

```

*(Note: A `Dockerfile` and `railway.toml` are also included in the repository for containerized or Railway deployments).*

---

Developed by a Big Data Analysis student.
