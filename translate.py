import os
import yaml
from openai import OpenAI
import subprocess
import re
from glob import glob
import sys
import difflib
import json
import uuid
import requests

# OpenAI API settings
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    print('ERROR: API_KEY environment variable is required')
    sys.exit(1)

BASE_URL = os.getenv('BASE_URL', 'https://openrouter.ai/api/v1')
print('* Base URL:', BASE_URL)

AI_MODEL = os.getenv('AI_MODEL', 'gpt-4')
print('* AI Model:', AI_MODEL)

TARGET_LANG = os.getenv('TARGET_LANG', 'Simplified-Chinese')
print('* Target Language:', TARGET_LANG)

# Input and output files
INPUT_FILES = os.getenv('INPUT_FILES', '')
if not INPUT_FILES:
    print('ERROR: INPUT_FILES environment variable is required')
    sys.exit(1)
print('* Input Files:', INPUT_FILES)

OUTPUT_FILES = os.getenv('OUTPUT_FILES', '')
if not OUTPUT_FILES:
    print('ERROR: OUTPUT_FILES environment variable is required')
    sys.exit(1)
print('* Output Files:', OUTPUT_FILES)

def read_prompt_from_file(prompt_text):
    """Read prompt from file if it's a file path"""
    if os.path.exists(prompt_text) and os.path.isfile(prompt_text):
        try:
            with open(prompt_text, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Warning: Could not read prompt file {prompt_text}: {e}")
    return prompt_text


PROMPT = os.getenv('PROMPT', '')
PROMPT = read_prompt_from_file(PROMPT)
print('* Prompt:', PROMPT if PROMPT else '[Custom prompt will be used]')

# Second AI model for refinement
REFINE_ENABLED = os.getenv('REFINE_ENABLED', 'true').lower() == 'true'
print('* Refinement Enabled:', REFINE_ENABLED)

# For refinement, we can specify a different OpenAI model
REFINE_AI_MODEL = os.getenv('REFINE_AI_MODEL', AI_MODEL)
print('* Refinement AI Model:', REFINE_AI_MODEL)

# Temperature settings for controlling randomness (0.0 to 1.0)
# Lower values make output more deterministic, higher values more creative
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.3'))
print('* Temperature:', TEMPERATURE)

REFINE_TEMPERATURE = float(os.getenv('REFINE_TEMPERATURE', TEMPERATURE))
print('* Refinement Temperature:', REFINE_TEMPERATURE)

REFINE_PROMPT = os.getenv('REFINE_PROMPT', '')
REFINE_PROMPT = read_prompt_from_file(REFINE_PROMPT)
print('* Refinement Prompt:', REFINE_PROMPT if REFINE_PROMPT else '[Custom prompt will be used]')

COMMIT_MESSAGE = os.getenv('COMMIT_MESSAGE', 'Add LLM Translations')
print('* Commit Message Title:', COMMIT_MESSAGE)

def extract_yaml_and_content(md_text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)", md_text, re.DOTALL)
    if match:
        yaml_part, content = match.groups()
        yaml_data = yaml.safe_load(yaml_part.strip())
        return yaml_data, content.strip()
    return None, md_text.strip()


def reconstruct_markdown(yaml_data, translated_content):
    yaml_str = yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False)
    return f"---\n{yaml_str}---\n\n{translated_content}"


def call_openai(model, user_prompt, temperature=None):
    """Call OpenAI API with the specified model
    
    Args:
        model: The AI model to use
        user_prompt: The prompt to send to the model
        temperature: The temperature parameter (0.0 to 1.0) controlling randomness
    """
    # Initialize OpenAI client with base_url if provided
    client_kwargs = {'api_key': API_KEY}
    if BASE_URL:
        client_kwargs['base_url'] = BASE_URL
    
    client = OpenAI(**client_kwargs)
    
    # Use provided temperature or default to global TEMPERATURE
    if temperature is None:
        temperature = TEMPERATURE
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return ""


def translate_text(text):
    """Translates text using OpenAI."""
    # If user provided a custom prompt, use it; otherwise use the default prompt
    if PROMPT:
        user_prompt = PROMPT + "\n\n" + text
    else:
        user_prompt = f"Translate this text to {TARGET_LANG}. If the text contains YAML front matter (between --- delimiters at the beginning), preserve the YAML structure and only translate values that should be translated, keeping keys and formatting intact. Also preserve all HTML tags, code blocks, and markdown formatting:\n\n{text}"
    
    return call_openai(AI_MODEL, user_prompt, temperature=TEMPERATURE)


def refine_translation(translated_text, original_text=None):
    """Refines the translated text using a different OpenAI model.
    
    Args:
        translated_text: The translated text to refine
        original_text: The original source text (if provided)
    """
    if not REFINE_ENABLED:
        return translated_text
    
    # If user provided a custom refinement prompt, use it; otherwise use the default prompt
    if REFINE_PROMPT:
        user_prompt = REFINE_PROMPT + "\n\n"
        if original_text:
            user_prompt += f"Original text:\n{original_text}\n\nTranslated text to refine:\n{translated_text}"
        else:
            user_prompt += translated_text
    else:
        if original_text:
            user_prompt = f"Please refine and polish the following {TARGET_LANG} translation while preserving all formatting, markup, and technical terms. Make it sound more natural and fluent. If the text contains YAML front matter (between --- delimiters at the beginning), ensure the YAML structure remains intact and only values that should be translated are modified.\n\nOriginal text:\n{original_text}\n\nTranslated text to refine:\n{translated_text}"
        else:
            user_prompt = f"Please refine and polish the following {TARGET_LANG} translation while preserving all formatting, markup, and technical terms. Make it sound more natural and fluent. If the text contains YAML front matter (between --- delimiters at the beginning), ensure the YAML structure remains intact and only values that should be translated are modified.\n\n{translated_text}"
    
    print(f"Refining translation with OpenAI (Model: {REFINE_AI_MODEL}, Temperature: {REFINE_TEMPERATURE})...")
    
    return call_openai(REFINE_AI_MODEL, user_prompt, temperature=REFINE_TEMPERATURE)


def get_input_files():
    """Get the list of input files from the INPUT_FILES environment variable"""
    # Split by spaces, but handle paths that might have leading ./ from git diff output
    input_files = []
    for f in INPUT_FILES.split():
        f = f.strip()
        if f:
            # Normalize paths by removing leading ./ if present
            if f.startswith('./'):
                f = f[2:]
            input_files.append(f)
    
    print(f"Processing input files: {input_files}")
    return input_files

def show_diff(text1, text2):
    """Show differences between two texts using difflib
    
    Args:
        text1: Original text
        text2: Modified text
    """
    # Split texts into lines
    text1_lines = text1.splitlines()
    text2_lines = text2.splitlines()
    
    # Generate diff
    diff = difflib.unified_diff(
        text1_lines, 
        text2_lines,
        fromfile='Original Translation',
        tofile='Refined Translation',
        lineterm=''
    )
    
    # Print diff or a message if no differences
    diff_output = '\n'.join(diff)
    if diff_output:
        print(diff_output)
    else:
        print("No differences found between original and refined translations.")

def create_pull_request(github_token, github_repository, branch_name, commit_message, translation_table):
    """Create a pull request using GitHub API or GitHub CLI
    
    Args:
        github_token: GitHub token for authentication
        github_repository: Repository in format 'owner/repo'
        branch_name: Branch name to create PR from
        commit_message: Commit message (will be used for PR title/body)
        translation_table: Table of translated files for PR body
    """
    try:
        # Extract PR title from commit message (first line)
        pr_title = "🌐 Add LLM Translations"
        
        # Create PR body with translation table
        pr_body = f"## Automated Translation\n\n{commit_message.split('\n\n', 1)[1] if '\n\n' in commit_message else commit_message}"
        
        # Check if we're in GitHub Actions environment
        in_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        # If we're in GitHub Actions, try to use GitHub CLI first
        if in_github_actions:
            print("Creating PR using GitHub CLI (gh)...")
            try:
                # Try to use GitHub CLI which has automatic authentication in Actions
                # First, create a temporary file with the PR body
                pr_body_file = "pr_body.md"
                with open(pr_body_file, "w") as f:
                    f.write(pr_body)
                
                # Create PR using gh cli
                result = subprocess.run(
                    ["gh", "pr", "create", 
                     "--title", pr_title,
                     "--body-file", pr_body_file,
                     "--head", branch_name],
                    capture_output=True,
                    text=True
                )
                
                # Clean up the temporary file
                if os.path.exists(pr_body_file):
                    os.remove(pr_body_file)
                    
                if result.returncode == 0:
                    print(f"Successfully created PR: {result.stdout.strip()}")
                    return
                else:
                    print(f"Failed to create PR using GitHub CLI: {result.stderr}")
                    print("Falling back to GitHub API...")
            except Exception as cli_error:
                print(f"Error using GitHub CLI: {str(cli_error)}")
                print("Falling back to GitHub API...")
        
        # Use GitHub API as fallback or primary method
        # GitHub API endpoint for creating PRs
        api_url = f"https://api.github.com/repos/{github_repository}/pulls"
        
        # Default branch is usually 'main' or 'master'
        # Get the default branch using GitHub API
        repo_url = f"https://api.github.com/repos/{github_repository}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get repository info to determine default branch
        repo_response = requests.get(repo_url, headers=headers)
        if repo_response.status_code != 200:
            print(f"Failed to get repository info: {repo_response.status_code}")
            print(repo_response.json())
            return
            
        default_branch = repo_response.json()["default_branch"]
        
        # Create the pull request
        pr_data = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": default_branch
        }
        
        response = requests.post(api_url, headers=headers, json=pr_data)
        
        if response.status_code == 201:
            pr_number = response.json()["number"]
            pr_url = response.json()["html_url"]
            print(f"Successfully created PR #{pr_number}: {pr_url}")
        else:
            print(f"Failed to create PR: {response.status_code}")
            print(response.json())
    except Exception as e:
        print(f"Error creating pull request: {str(e)}")

def find_files_in_directory(directory_path, extensions=None):
    """Recursively find all files in a directory, optionally filtering by extensions
    
    Args:
        directory_path: Path to the directory to search
        extensions: Optional list of file extensions to include (e.g., ['.md', '.txt'])
        
    Returns:
        List of file paths found in the directory
    """
    files = []
    
    # Ensure the directory path exists
    if not os.path.exists(directory_path):
        print(f"Directory not found: {directory_path}")
        return files
        
    # Walk through the directory recursively
    for root, _, filenames in os.walk(directory_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            
            # Filter by extension if extensions are provided
            if extensions:
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in extensions:
                    files.append(file_path)
            else:
                files.append(file_path)
    
    return files


def get_output_path(file_path):
    # If OUTPUT_FILES is specified, map input path to output path
    if OUTPUT_FILES:
        # Extract pattern from OUTPUT_FILES (e.g., "docs/cn/**/*.{md,json}")
        output_pattern = OUTPUT_FILES
        
        # Handle file extensions in pattern
        if '{' in output_pattern and '}' in output_pattern:
            ext_pattern = output_pattern[output_pattern.find('{')+1:output_pattern.find('}')]
            # Keep the file extension from the original file
            _, file_ext = os.path.splitext(file_path)
            file_ext = file_ext.lstrip('.')
            
            # Replace the pattern with the actual extension
            if ',' in ext_pattern:  # Multiple extensions like {md,json}
                output_pattern = output_pattern.replace('{' + ext_pattern + '}', file_ext)
    
        # Handle directory wildcards like **/
        if '**' in output_pattern:
            # Get the base directory from the pattern (before **)
            pattern_base_dir = output_pattern.split('**/')[0]
            
            # Get the directory structure from the input file
            input_dir = os.path.dirname(file_path)
            
            # Extract the relative part of the path that should be preserved
            # For example, if input_file is 'docs/en/guides/00-products/02-dc/05-support.md'
            # and pattern is 'docs/cn/**/*.md', we want to preserve 'guides/00-products/02-dc'
            
            # First, determine the common prefix to remove
            input_parts = input_dir.split('/')
            
            # Find the language directory (typically 'en' in the input path)
            if len(input_parts) >= 2:
                lang_index = -1
                for i, part in enumerate(input_parts):
                    if part == 'en':
                        lang_index = i
                        break
                
                if lang_index != -1:
                    # Keep the directory structure after the language directory
                    relative_path = '/'.join(input_parts[lang_index+1:])
                    
                    # Get the filename without extension
                    file_name = os.path.basename(file_path)
                    file_name_without_ext, file_ext = os.path.splitext(file_name)
                    file_ext = file_ext.lstrip('.')
                    
                    # Construct the output path preserving the directory structure
                    return os.path.join(pattern_base_dir, relative_path, file_name_without_ext + '.' + file_ext)
            
            # Fallback if we can't determine the language directory
            file_name = os.path.basename(file_path)
            file_name_without_ext, file_ext = os.path.splitext(file_name)
            file_ext = file_ext.lstrip('.')
            return os.path.join(pattern_base_dir, file_name_without_ext + '.' + file_ext)
        else:
            return output_pattern


def main():
    input_files = get_input_files()
    if not input_files:
        print("No input files specified.")
        return

    # Process each input path (could be a file or directory)
    for input_path in input_files:
        print(f"Processing: {input_path}")
        if not os.path.exists(input_path):
            print(f"Path not found, skipping: {input_path}")
            # Print the current working directory to help with debugging
            print(f"Current working directory: {os.getcwd()}")
            # Try to list parent directory contents if possible
            parent_dir = os.path.dirname(input_path)
            if os.path.exists(parent_dir):
                print(f"Contents of parent directory {parent_dir}:")
                print("\n".join(os.listdir(parent_dir)))
            else:
                print(f"Parent directory not found: {parent_dir}")
            continue
        
        # Determine if it's a file or directory
        files_to_process = []
        if os.path.isdir(input_path):
            print(f"{input_path} is a directory, finding files recursively...")
            # Common document extensions - can be customized as needed
            doc_extensions = ['.md', '.txt', '.json']
            files_to_process = find_files_in_directory(input_path, doc_extensions)
            print(f"Found {len(files_to_process)} files in directory {input_path}")
        else:
            # It's a regular file
            files_to_process = [input_path]
        
        # Process each file
        for file_path in files_to_process:
            print(f"Translating file: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()
                
            # Directly translate the entire file content, including YAML front matter if present
            translated_content = translate_text(file_text)
            print(f"\n===== TRANSLATION COMPLETED FOR {file_path} =====\n")
            
            # Apply refinement if enabled
            if REFINE_ENABLED:
                refined_content = refine_translation(translated_content, original_text=file_text)
                # Show only the differences between original and refined translations
                print("\n===== REFINEMENT DIFFERENCES =====\n")
                show_diff(translated_content, refined_content)
                print("\n===== END OF REFINEMENT DIFFERENCES =====\n")
                print("Translation refined with second AI model (with original text as reference)")
            else:
                refined_content = translated_content
                
            # The translated text is the final output, no reconstruction needed
            translated_file_text = refined_content

            # Generate target filename
            translated_file_path = get_output_path(file_path)

            # Save translated file
            os.makedirs(os.path.dirname(translated_file_path), exist_ok=True)
            with open(translated_file_path, "w", encoding="utf-8") as f:
                f.write(translated_file_text)
            print(f"Saved translated file: {translated_file_path}")

    # Prepare commit message with table of translated files
    translation_table = []
    for source_file, output_file in zip(input_files, [get_output_path(f) for f in input_files]):
        translation_table.append(f"| `{source_file}` | `{output_file}` | {TARGET_LANG} |")
    
    table_content = "\n".join(translation_table)
    commit_message = f"{COMMIT_MESSAGE}\n\n## ✅ Translated to {TARGET_LANG} - {len(input_files)} file{'s' if len(input_files) > 1 else ''}\n\n| **Source** | **Output** | **Language** |\n| :--- | :--- | :--- |\n{table_content}"
    
    # Get GitHub environment variables
    # In GitHub Actions, we can access the token through various environment variables
    github_token = os.getenv('GITHUB_TOKEN') or os.getenv('INPUT_GITHUB_TOKEN')
    
    # Check for token in standard GitHub Actions locations
    if not github_token:
        # Try common environment variable names for GitHub token
        for env_var in ['GH_TOKEN', 'GITHUB_PAT', 'INPUT_TOKEN']:
            token = os.getenv(env_var)
            if token:
                github_token = token
                print(f"Using GitHub token from {env_var}")
                break
    
    # Try to get token from GitHub Actions environment file
    github_env_file = os.getenv('GITHUB_ENV')
    if not github_token and github_env_file and os.path.exists(github_env_file):
        try:
            with open(github_env_file, 'r') as f:
                for line in f:
                    if line.startswith('GITHUB_TOKEN=') or line.startswith('GH_TOKEN='):
                        github_token = line.split('=', 1)[1].strip()
                        print(f"Using GitHub token from environment file")
                        break
        except Exception as e:
            print(f"Warning: Could not read GitHub environment file: {e}")
    
    # If still no token and we're in GitHub Actions, use the default token
    if not github_token and os.getenv('GITHUB_ACTIONS') == 'true':
        # In GitHub Actions, we need to get the token from the GITHUB_TOKEN secret
        print("Using auto-generated GitHub token from Actions environment")
        # This is just a placeholder - in GitHub Actions, the token should be passed as an input
        github_token = os.getenv('GITHUB_TOKEN', '')
    
    github_repository = os.getenv('GITHUB_REPOSITORY')
    github_ref = os.getenv('GITHUB_REF')
    github_actor = os.getenv('GITHUB_ACTOR')
    github_run_id = os.getenv('GITHUB_RUN_ID')
    
    # If we're running in GitHub Actions
    if (github_token or os.getenv('GITHUB_ACTIONS') == 'true') and github_repository:
        print("Running in GitHub Actions environment, setting up git...")
        
        # Set git config
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
        
        # Create a new branch for the PR
        branch_name = f"translate-{github_run_id if github_run_id else str(uuid.uuid4())[:8]}"
        print(f"Creating branch: {branch_name}")
        subprocess.run(["git", "checkout", "-b", branch_name])
        
        # Add and commit changes
        subprocess.run(["git", "add", "*"])
        subprocess.run(["git", "commit", "-m", commit_message])
        
        # Push to the new branch
        print(f"Pushing to branch: {branch_name}")
        subprocess.run(["git", "push", "origin", branch_name])
        
        # Create PR using GitHub API
        create_pull_request(github_token, github_repository, branch_name, commit_message, translation_table)
    else:
        # Regular git operations for local runs
        print("Running in local environment, performing standard git operations...")
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"])
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"])
        subprocess.run(["git", "add", "*"])
        subprocess.run(["git", "commit", "-m", commit_message])
        subprocess.run(["git", "push"])

if __name__ == "__main__":
    main()