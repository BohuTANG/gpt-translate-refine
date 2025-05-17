# 🚀  Translate Files with Multiple AI APIs (GitHub Action)
---
This GitHub Action detects changes in specified file types (Markdown, JSON, TXT, etc.), translates the modified content using various AI models (OpenAI GPT-4, Google Gemini, Anthropic Claude, Microsoft Azure Translator), and commits the translations back to your repository.

- ✅ Supports multiple file extensions
- ✅ Preserves YAML front matter in markdown files
- ✅ Allows custom output file formats
- ✅ Automatically commits and pushes translated files
- ✅ Supports multiple AI provioders (OpenAI ChatGPT, Google Gemini, Claude, Azure)

---
## 🛠 How It Works
- Detects changed files (based on extensions like .md, .json, .txt).
- Extracts and preserves YAML front matter (if applicable).
- Sends content to AI API for translation.
- Saves the translated version with a custom filename format (e.g., *-fr.md, translated_*.json).
- Commits and pushes the translated files back to the repository.

---
## 📌 Example Usage
Add the following workflow to your `.github/workflows/translate.yml` file (or add the step in any of your pipelines!):

```yaml
name: Translate Files

on:
  push:
    branches:
      - main

jobs:
  translate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3

      - name: Run Translation Action
        uses: imaun/gpt-translate-action@v1.8.8
        with:
          api_key: ${{ secrets.API_KEY }}
          ai_service: "openai"  # Options: openai, gemini, claude, azure
          ai_model: "gpt-4"      # Specify model (e.g., gemini-pro, claude-v1)
          target_lang: "French"
          target_lang_code: "fr"
          file_extensions: "md,json,txt"
          output_format: "translated_*.{ext}"
          base_branch: main # Default is GITHUB_BASE_REF from env
```
## ⚙️ Inputs
- `api_key` (Required): Your AI provider API key (stored as a GitHub Secret).
- `ai_service`: AI provider to use. Currently supported values: (openai, gemini, claude, azure)
- `ai_model`: AI model to use (e.g., gpt-4, gemini-pro, claude-v1).
- `target_lang`: The language to translate into (default: **Persian**).
- `target_lang_code`: The language code to be used in output format (default: **fa**).
- `file_exts`: Comma-separated list of file types to process (default: **md**).
- `output_format`: Format for translated files. Use {lang} for language and {ext} for extension.
- `base_branch`: The base branch to diff against (if not automatically detected). Default is `GITHUB_BASE_REF` from env.

## 🎯 Example Output Filenames
- `*-{lang}.{ext}`: about-fa.md
- `translated_*.{ext}`: translated_about.json

## 🔑 Setting Up the API Key
- Go to **Settings** → **Secrets and Variables** → **Actions** in your repository.
- Click **New Repository Secret**.
- Add a secret named `API_KEY` and paste your AI service API key.

---
## 📌 Example Translated File
Original Markdown (about.md):

```md
---
slug: "about"
title: "About Me"
author: "John Doe"
description: "This is my personal website."
---

Welcome to my personal website! Here you can find my projects and blog posts.
```
Translated (about-fr.md for French):

```md
---
slug: "about"
title: "À propos de moi"
author: "John Doe"
description: "Ceci est mon site Web personnel."
---

Bienvenue sur mon site personnel ! Vous pouvez y trouver mes projets et articles de blog.
```
---
## 🛠 Running Locally (For Testing)
```bash
docker build -t translate-action .
docker run -e API_KEY="your-api-key" -e AI_SERVICE="gemini" -e TARGET_LANG="French" -e TARGET_LANG_CODE="fr" translate-action
```
