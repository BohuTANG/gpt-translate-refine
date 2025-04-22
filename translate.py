import os
import yaml
import openai
import subprocess
import re
import requests
from glob import glob

API_KEY = os.getenv('API_KEY')
TARGET_LANG = os.getenv('TARGET_LANG', 'Persian') # Default: Persian
TARGET_LANG_CODE = os.getenv('TARGET_LANG_CODE', 'fa') # Default: fa
FILE_EXTS = os.getenv('FILE_EXTS','md') # Default: Markdown files
OUTPUT_FORMAT = os.getenv('OUTPUT_FORMAT', '*-{lang}.{ext}') # Default: *-fa.md

SYSTEM_PROMPT = os.getenv(
    'SYSTEM_PROMPT', 
    'You are a translator specializing in software development. Preserve YAML metadata, HTML, and other markuo formats or codes. and also technical terms in general software development DO NOT translate them to target language. Translate the text to {TARGET_LANG}.'
)
USER_PROMPT = os.getenv(
    'USER_PROMPT', 
    'Translate this text to {TARGET_LANG} while keeping YAML keys, Any html or json markups unchanged:\n{text}'
)
AI_SERVICE = os.getenv('AI_SERVICE', 'openai')
AI_MODEL = os.getenv('MODEL', 'gpt-4')

if not API_KEY:
    raise ValueError('Missing OpenAI API key!')

openai.api_key = API_KEY


def extract_yaml_and_content(md_text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)", md_text, re.DOTALL)
    if match:
        yaml_part, content = match.group()
        yaml_data = yaml.safe_load(yaml_part)
        return yaml_data, content.strip()
    return None, md_text.strip()


def reconstruct_markdown(yaml_data, translated_content):
    yaml_str = yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False)
    return f"---\n{yaml_str}---\n\n{translated_content}"


def translate_text(text):
    """Determines the AI provider and fetches the translation."""
    system_prompt = SYSTEM_PROMPT.replace('{TARGET_LANG}', TARGET_LANG)
    user_prompt = USER_PROMPT.replace('{TARGET_LANG}', TARGET_LANG).replace('{text}', text)

    if AI_SERVICE.lower() == 'openai':
        return translate_with_openai(system_prompt, user_prompt)

    elif AI_SERVICE.lower() == 'gemini':
        return translate_with_gemini(system_prompt, user_prompt)

    elif AI_SERVICE.lower() == 'claude':
        return translate_with_claude(system_prompt, user_prompt)

    elif AI_SERVICE.lower() == 'azure':
        return translate_with_azure(text)
    else:
        raise ValueError(f'Unsupported AI service: {AI_SERVICE}')


def get_changed_files():
    file_exts = [ext.strip() for ext in FILE_EXTS.split(",")]

    base_branch = os.getenv("GITHUB_BASE_REF") or os.getenv("INPUT_BASE_BRANCH") or "main"

    # Fetch base branch
    subprocess.run(["git", "fetch", "origin", base_branch, "--depth=2"], check=True)

    base_result = subprocess.run(
        ["git", "merge-base", "HEAD", f"origin/{base_branch}"],
        capture_output=True,
        text=True,
        check=True
    )
    base_commit = base_result.stdout.strip()

    if not base_commit:
        raise RuntimeError("Could not determine base commit for diff.")
    
    diff_result = subprocess.run(
        ["git", "diff", "--name-only", base_commit, "HEAD"],
        capture_output=True,
        text=True,
        check=True
    )
    all_changed = diff_result.stdout.splitlines()

    changed_files = [
        f for f in all_changed if any(f.endswith(f".{ext}") for ext in file_exts)
    ]

    return changed_files


def get_translated_filename(file_path):
    ext = file_path.split(".")[-1]
    base_name = ".".join(file_path.split(".")[:-1])  # Remove extension
    lang_code = f'-{TARGET_LANG_CODE.lower()}'
    return OUTPUT_FORMAT.replace("{lang}", lang_code).replace("{ext}", ext).replace("*", base_name)


def translate_with_openai(system_prompt, user_prompt):
    """Translation using OpenAI """
    response = openai.ChatCompletion.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response["choices"][0]["message"]["content"].strip()


def translate_with_gemini(system_prompt, user_prompt):
    """Translation using Google Gemini API."""
    prompt = f'{system_prompt}\n\n{user_prompt}'
    gemini_api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateText"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": AI_MODEL,
        "prompt": prompt,
        "temperature": 0.7,
    }
    response = requests.post(f"{gemini_api_url}?key={API_KEY}", json=payload, headers=headers)
    return response.json().get("candidates", [{}])[0].get("output", "").strip()


def translate_with_claude(system_prompt, user_prompt):
    """Translation using Anthropic Claude API."""
    prompt = f'{system_prompt}\n\n{user_prompt}'
    claude_api_url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": AI_MODEL,
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": prompt }
        ],
    }
    response = requests.post(claude_api_url, json=payload, headers=headers)
    return response.json().get("content", "").strip()


def translate_with_azure(text):
    """Translation using Microsoft Azure Translator API."""
    azure_endpoint = "https://api.cognitive.microsofttranslator.com/translate"
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY,
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": os.getenv("AZURE_REGION", "westeurope"),
    }
    params = {"api-version": "3.0", "to": TARGET_LANG_CODE}
    body = [{"text": text}]
    response = requests.post(azure_endpoint, params=params, headers=headers, json=body)
    return response.json()[0]["translations"][0]["text"].strip()


def main():
    changed_files = get_changed_files()
    if not changed_files:
        print("No changed files detected.")
        return

    for file_path in changed_files:
        print(f"Processing: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            file_text = f.read()

        # Extract YAML front matter if it's an md file
        if file_path.endswith(".md"):
            yaml_data, content = extract_yaml_and_content(file_text)
        else:
            yaml_data, content = None, file_text.strip()

        translated_content = translate_text(content)

        # Reconstruct if it's markdown with YAML front matter
        translated_file_text = (
            reconstruct_markdown(yaml_data, translated_content)
            if yaml_data
            else translated_content
        )

        # Generate target filename
        translated_file_path = get_translated_filename(file_path)

        # Save translated file
        with open(translated_file_path, "w", encoding="utf-8") as f:
            f.write(translated_file_text)

        print(f"Translated file saved to: {translated_file_path}")

    # Git commit and push
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"])
    subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"])
    subprocess.run(["git", "add", "*"])
    subprocess.run(["git", "commit", "-m", f"Add translated files in {TARGET_LANG}"])
    subprocess.run(["git", "push"])

if __name__ == "__main__":
    main()