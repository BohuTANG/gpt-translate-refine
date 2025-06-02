# 🚀  Translate Files with OpenAI (GitHub Action)
---
This GitHub Action detects changes in specified file types (Markdown, JSON, TXT, etc.), translates the modified content using OpenAI models, and commits the translations back to your repository.

- ✅ Supports multiple file extensions
- ✅ Preserves YAML front matter in markdown files
- ✅ Allows custom output file formats
- ✅ Automatically commits and pushes translated files
- ✅ Optional two-stage translation with refinement by a second OpenAI model

---
## 🛠 How It Works
- Detects changed files (based on extensions like .md, .json, .txt).
- Extracts and preserves YAML front matter (if applicable).
- Sends content to AI API for translation.
- Optionally refines the translation using a second AI model for improved quality.
- Saves the translated version with a custom filename format (e.g., *-fr.md, translated_*.json).
- Commits and pushes the translated files back to the repository.

---
## 🚀 Usage

### GitHub Actions Workflow

```yaml
name: Translate Documentation

on:
  push:
    branches:
      - main
    paths:
      - 'docs/en/**'

jobs:
  translate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
          
      - name: Run Translation Action
        uses: BohuTANG/gpt-translate-refine@v1.0.0
        with:
          api_key: ${{ secrets.OPENAI_API_KEY }}
          # base_url: "https://api.openrouter.ai/api/v1"  # Optional: custom OpenAI-compatible API endpoint
          ai_model: "gpt-4"      # OpenAI model to use
          target_lang: "Chinese"
          input_files: "README.md docs/getting-started.md"
          output_files: "docs/cn/**/*.{md}"
          # Optional refinement settings (enabled by default)
          refine_ai_model: "gpt-4-turbo"  # Specify a different OpenAI model for refinement
          # Optional git settings
          commit_message: "Add LLM Translations"  # Custom commit message title
```
## 🔧 Parameters

### Required Parameters
- `api_key`: OpenAI API key.
- `input_files`: Space-separated list of files to translate (e.g., "README.md docs/guide.md").
- `output_files`: Output file pattern (e.g., 'docs/cn/**/*.{md,json}').

### Optional Parameters
- `base_url`: Custom OpenAI API endpoint URL (default: **https://openrouter.ai/api/v1**).
- `ai_model`: OpenAI model to use (default: **gpt-4**).
- `target_lang`: Target language for translation (default: **Simplified-Chinese**).

### Prompt Customization
- `prompt`: Customize the prompt for the AI model. Can be text or a file path.

### Refinement Options
- `refine_enabled`: Enable second OpenAI model for refinement after translation (default: **true**).
- `refine_ai_model`: OpenAI model for refinement. If not specified, uses the same as primary translation.
- `refine_prompt`: Customize the prompt for refinement. Can be text or a file path.

### Git Options
- `commit_message`: Custom commit message title (default: **Add LLM Translations**).

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
## 🧪 Local Testing

```bash
# Basic usage (uses default OpenRouter endpoint and Simplified-Chinese as target language)
docker build -t translate-action .
docker run -e API_KEY="your-api-key" -e INPUT_FILES="README.md docs/guide.md" -e OUTPUT_FILES="docs/cn/**/*.{md}" translate-action

# With custom settings
docker run -e API_KEY="your-api-key" -e BASE_URL="https://api.openai.com/v1" -e TARGET_LANG="French" -e INPUT_FILES="README.md" -e OUTPUT_FILES="docs/fr/README.md" -e REFINE_ENABLED="true" -e REFINE_AI_MODEL="gpt-4-turbo" translate-action

# Using file-based prompts
docker run -e API_KEY="your-api-key" -e INPUT_FILES="docs/en/guides/00-products/02-dc/05-support.md" -e OUTPUT_FILES="docs/cn/**/*.{md,json}" -e AI_MODEL="gpt-4" -e PROMPT=".github/workflows/prompt.txt" -e REFINE_AI_MODEL="gpt-4-turbo" -e REFINE_PROMPT=".github/workflows/prompt_refine.txt" translate-action
```

### Managing Docker Images

To check existing Docker images:
```bash
docker images | grep translate-action
```

To remove the Docker image (useful when making changes and need to rebuild):
```bash
docker rmi translate-action
```

### Working with Files in Different Directories

If your files to translate are in a different directory than where you're running the action, you have two options:

#### Option 1: Change to the correct directory first
```bash
cd /path/to/your/docs/repo && docker run -e API_KEY="your-api-key" -e INPUT_FILES="docs/en/file.md" -e OUTPUT_FILES="docs/cn/**/*.md" translate-action
```

#### Option 2: Mount the directory as a volume
```bash
docker run -v /path/to/your/docs/repo:/workspace -w /workspace -e API_KEY="your-api-key" -e INPUT_FILES="docs/en/file.md" -e OUTPUT_FILES="docs/cn/**/*.md" translate-action
```
