# Notion Formatter 🚀

A simple tool to automatically format messy Notion pages into nicely structured Markdown and append the result back into the same page.

## ✨ Features

- **Direct Notion integration**: Uses a Notion internal integration token to read and write page content.
- **OpenRouter LLM Formatting (latest)**: Uses OpenRouter to call modern open‑weight models and turn raw Notion text into clean Markdown (headings, paragraphs, lists, code blocks).
- **Markdown → Notion blocks**: Converts the LLM’s Markdown output back into Notion blocks that are appended to the page.
- **One‑click flow**: Paste a Notion page URL in the tiny web UI and the formatted output gets added under the original content.

## 🛠 Tech Stack

- **Backend**: Python / Flask (`server.py`)
- **LLM Gateway**: [OpenRouter](https://openrouter.ai/) HTTP API
- **Notion SDK**: `notion-client`
- **Config**: `python-dotenv` for `.env` loading

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.8+
- A Notion integration token ([My Integrations](https://www.notion.so/my-integrations))
- An OpenRouter API key ([Get one here](https://openrouter.ai/keys))

### 2. Setup Environment
Create a `.env` file in the root directory:

```bash
NOTION_TOKEN=your_notion_integration_token
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 3. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python3 server.py
```

By default the app runs on **http://localhost:3000**.

## 📖 Usage

1. Open `http://localhost:3000` in your browser.
2. Paste a Notion page URL that your integration has access to.
3. Click **"Format & Append"**.
4. The server:
	- fetches the page’s text from Notion,
	- sends it to an OpenRouter model with a "formatter, not writer" prompt,
	- converts the Markdown response into Notion blocks,
	- appends the formatted content to the same page.

You’ll see a success or error message in the browser.

## 🔐 Notes

- Keep your `NOTION_TOKEN` and `OPENROUTER_API_KEY` secret and **never commit `.env` to git**.
- Make sure your Notion integration is shared with the pages/databases you want to format.
