#!/usr/bin/env python3

import os
import sys
from typing import List, Dict, Tuple

from src.config import Config
from src.translator import Translator, TextUtils
from src.file_processor import FileProcessor
from src.git_operations import GitOperations


class TranslationWorkflow:
    """Main class for handling the translation workflow"""
    
    def __init__(self, config):
        self.config = config
        self.file_processor = FileProcessor(config)
        self.translator = Translator(config)
        self.git_ops = GitOperations(config)
        
        # Track processed files
        self.processed_files = []
        self.output_files = []
        self.directory_files_map = {}
    
    def process_input_path(self, input_path):
        """Process a single input path (file or directory)"""
        print(f"Processing input path: {input_path}")
        
        # Check if path exists
        if not os.path.exists(input_path):
            self._handle_missing_path(input_path)
            return
        
        # Process directory or file
        if os.path.isdir(input_path):
            files = self._process_directory(input_path)
            for file_path in files:
                self._translate_file(file_path)
        else:
            self._translate_file(input_path)
    
    def _handle_missing_path(self, input_path):
        """Handle case when input path doesn't exist"""
        cwd = os.getcwd()
        print(f"Error: Path not found: {input_path}")
        print(f"Current working directory: {cwd}")
        
        # Show parent directory contents to help debug
        parent_dir = os.path.dirname(input_path) or '.'
        if os.path.exists(parent_dir):
            print(f"Contents of parent directory ({parent_dir}):")
            for item in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item)
                item_type = 'dir' if os.path.isdir(item_path) else 'file'
                print(f"  - {item} ({item_type})")
        else:
            print(f"Parent directory does not exist: {parent_dir}")
    
    def _process_directory(self, directory_path):
        """Process a directory and return files to translate"""
        print(f"Processing directory: {directory_path}")
        files = self.file_processor.find_files_recursively(directory_path)
        print(f"Found {len(files)} files in directory")
        
        # Store files for this directory
        self.directory_files_map[directory_path] = files
        return files
    
    def _translate_file(self, file_path):
        """Translate a single file"""
        print(f"Translating file: {file_path}")
        
        # Read file content
        content = self.file_processor.read_file(file_path)
        if not content:
            print(f"Error: Could not read file or file is empty: {file_path}")
            return
        
        # Get output path
        output_path = self.file_processor.get_output_path(file_path)
        if not output_path:
            print(f"Error: Could not determine output path for: {file_path}")
            return
        
        print(f"Output path: {output_path}")
        
        # Special handling for Markdown files with YAML frontmatter
        yaml_data = None
        has_frontmatter = False
        
        if file_path.lower().endswith('.md'):
            yaml_data, content, has_frontmatter = self.file_processor.extract_yaml_and_content(content)
        
        # Translate content
        print(f"Translating with model: {self.config.ai_model}...")
        translated_content = self.translator.translate(content)
        
        if not translated_content:
            print(f"Error: Translation failed for: {file_path}")
            return
        
        # Apply refinement if enabled
        if self.config.refine_enabled:
            translated_content = self._refine_translation(translated_content, content)
        
        # Reconstruct Markdown with YAML frontmatter if needed
        if has_frontmatter:
            translated_content = self.file_processor.reconstruct_markdown(yaml_data, translated_content, has_frontmatter)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Write translated content to output file
        if self.file_processor.write_file(output_path, translated_content):
            print(f"✅ Translation saved to: {output_path}")
            
            # Track processed files
            self.processed_files.append(file_path)
            self.output_files.append(output_path)
        else:
            print(f"❌ Error: Could not write to output file: {output_path}")
    
    def _refine_translation(self, translated_content, original_text):
        """Refine translation and show diff between original and refined versions"""
        print("Refining translation...")
        refined_content = self.translator.refine(translated_content, original_text)
        
        if not refined_content:
            print("⚠️ Refinement failed, using original translation")
            return translated_content
        
        # Show diff between original translation and refined translation
        TextUtils.show_diff(translated_content, refined_content)
        print("✅ Refinement applied successfully")
        
        return refined_content
    
    def prepare_commit_message(self, input_files):
        """Prepare commit message with formatted table of translated files"""
        # Create a table for the commit message
        translation_table = [
            "| **Source** | **Output/Count** | **Language** |",
            "| :--- | :--- | :--- |"
        ]
        
        # Check if we have directories in the input
        has_directories = any(os.path.isdir(p) for p in input_files if os.path.exists(p))
        
        # Add directory summaries if applicable
        if has_directories:
            for input_path in input_files:
                if os.path.exists(input_path) and os.path.isdir(input_path):
                    dir_files = self.directory_files_map.get(input_path, [])
                    translation_table.append(
                        f"| 📁 `{input_path}` | {len(dir_files)} files | {self.config.target_lang} |"
                    )
        
        # Add individual file entries
        for source_file, output_file in zip(self.processed_files, self.output_files):
            translation_table.append(
                f"| `{source_file}` | `{output_file}` | {self.config.target_lang} |"
            )
        
        # Create the commit message with appropriate count
        if has_directories:
            # Count directories and files separately
            dir_count = sum(1 for p in input_files if os.path.exists(p) and os.path.isdir(p))
            file_count = len(self.processed_files)
            summary = f"{dir_count} director{'ies' if dir_count > 1 else 'y'} ({file_count} files)"
        else:
            # Just count files
            file_count = len(self.processed_files)
            summary = f"{file_count} file{'s' if file_count > 1 else ''}"

        # Get PR title directly from config (no modifications)
        pr_title = self.config.pr_title.strip()
        
        # Format the complete commit message (used for commit and PR body)
        commit_message = (
            f"## ✅ Translated to {self.config.target_lang} - {summary}\n\n"
            f"{''.join(f'{line}\n' for line in translation_table)}"
        )
        
        return commit_message, translation_table
    
    def handle_git_operations(self, commit_message, translation_table):
        """Handle git operations: commit, push and create PR (if applicable)"""
        # Setup git configuration
        if not self.git_ops.setup_git():
            print("⚠️ Git setup failed, but continuing with local file operations")
        
        # Commit changes and push to remote, get branch name if created
        branch_name = self.git_ops.commit_and_push(self.output_files, commit_message)
        
        # If branch was created and we have GitHub credentials, create PR
        if branch_name:
            if self.git_ops.github_token and self.git_ops.github_repository:
                print("Creating pull request...")
                # Use pr_title from config as the PR title
                pr_title = self.config.pr_title.strip()
                # Use commit_message as the PR body
                pr_body = commit_message.split('\n')
                if self.git_ops.create_pull_request(branch_name, pr_title, pr_body):
                    print("✅ Pull request created successfully")
                else:
                    print("⚠️ Failed to create pull request")
            else:
                print("ℹ️ Skipping PR creation: GitHub token or repository not available")
                print(f"ℹ️ Branch '{branch_name}' has been pushed. You can create a PR manually.")
        else:
            print("ℹ️ No branch created or no changes to commit. Skipping PR creation.")
    
    def run(self):
        """Run the complete translation workflow"""
        try:
            # Get input files
            input_files = self.file_processor.get_input_files()
            if not input_files:
                print("❌ No input files specified or found")
                return False
            
            # Process each input path
            for input_path in input_files:
                self.process_input_path(input_path)
            
            # Exit if no files were processed
            if not self.processed_files:
                print("❌ No files were processed")
                return False
            
            print(f"✅ Successfully translated {len(self.processed_files)} files")
            
            # Prepare commit message and PR title
            commit_message, translation_table = self.prepare_commit_message(input_files)
            
            # Handle git operations
            self.handle_git_operations(commit_message, translation_table)
            
            return True
            
        except Exception as e:
            print(f"❌ Error in translation workflow: {e}")
            traceback.print_exc()
            return False


def main():
    """Main entry point for the translation workflow"""
    try:
        # Initialize configuration
        config = Config()
        config.print_config()
        
        # Create and run translation workflow
        workflow = TranslationWorkflow(config)
        workflow.run()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
