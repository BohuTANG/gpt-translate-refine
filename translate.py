#!/usr/bin/env python3

import os
import sys
import traceback
import math
import uuid
import time
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
        
        # Batch processing tracking
        self.current_batch = 0
        self.total_batches = 0
        
        # Generate a unique session ID for this translation run
        self.session_id = self._generate_session_id()
    
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
        
        # Translate the entire content (including any YAML frontmatter)
        print(f"Translating with model: {self.config.ai_model}...")
        translated_content = self.translator.translate(content)
        
        if not translated_content:
            print(f"Error: Translation failed for: {file_path}")
            return
        
        # Print the first translation result
        print("\n=== First Translation Result ===\n")
        print(translated_content)
        print("\n==============================\n")
        
        # Apply refinement if enabled
        if self.config.refine_enabled:
            translated_content = self._refine_translation(translated_content, content)
        
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

        # Add batch information and unique ID to PR title
        base_pr_title = self.config.pr_title.strip()
        if self.total_batches > 1:
            pr_title = f"{base_pr_title} [ID:{self.session_id}] (Part {self.current_batch}/{self.total_batches})"
        else:
            pr_title = f"{base_pr_title} [ID:{self.session_id}]"
        
        # Format the complete commit message (used for commit and PR body)
        commit_message = (
            f"## ✅ Translated to {self.config.target_lang} - {summary} (Batch {self.current_batch}/{self.total_batches})\n\n"
            f"Session ID: {self.session_id}\n\n"
            f"{''.join(f'{line}\n' for line in translation_table)}"
        )
        
        return commit_message, translation_table, pr_title
    
    def handle_git_operations(self, commit_message, translation_table, pr_title=None):
        """Handle git operations: commit, push and create PR (if applicable)"""
        # Setup git configuration
        if not self.git_ops.setup_git():
            print("⚠️ Git setup failed, but continuing with local file operations")
        
        # Commit changes and push to remote, get branch name if created
        # Use batch number in branch name for uniqueness
        batch_suffix = f"-batch-{self.current_batch}" if self.total_batches > 1 else ""
        branch_name = self.git_ops.commit_and_push(self.output_files, commit_message, batch_suffix)
        
        # If branch was created and we have GitHub credentials, create PR
        if branch_name:
            if self.git_ops.github_token and self.git_ops.github_repository:
                print("Creating pull request...")
                # Use provided PR title or default from config
                if pr_title is None:
                    pr_title = self.config.pr_title.strip()
                    if self.total_batches > 1:
                        pr_title = f"{pr_title} (Part {self.current_batch}/{self.total_batches})"
                
                # Use commit_message as the PR body
                pr_body = commit_message.split('\n')
                if self.git_ops.create_pull_request(branch_name, pr_title, pr_body):
                    print(f"✅ Pull request created successfully for batch {self.current_batch}/{self.total_batches}")
                else:
                    print(f"⚠️ Failed to create pull request for batch {self.current_batch}/{self.total_batches}")
            else:
                print("ℹ️ Skipping PR creation: GitHub token or repository not available")
                print(f"ℹ️ Branch '{branch_name}' has been pushed. You can create a PR manually.")
        else:
            print("ℹ️ No branch created or no changes to commit. Skipping PR creation.")
    
    def _generate_session_id(self) -> str:
        """Generate a short unique session ID for this translation run"""
        # Use timestamp and random component to create a short but unique ID
        timestamp = int(time.time()) % 10000  # Last 4 digits of timestamp
        random_part = uuid.uuid4().hex[:3]    # 3 characters from UUID
        return f"{timestamp}{random_part}"  # Format: 1234abc
    
    def run(self):
        """Run the complete translation workflow with batch processing"""
        try:
            # Display session ID at the start
            print(f"🆔 Translation session ID: {self.session_id}")
            
            # Get input files
            input_files = self.file_processor.get_input_files()
            if not input_files:
                print("❌ No input files specified or found")
                return False
            
            # Collect all files to translate first
            all_files_to_translate = []
            for input_path in input_files:
                if not os.path.exists(input_path):
                    self._handle_missing_path(input_path)
                    continue
                    
                if os.path.isdir(input_path):
                    files = self._process_directory(input_path)
                    all_files_to_translate.extend(files)
                else:
                    all_files_to_translate.append(input_path)
            
            if not all_files_to_translate:
                print("❌ No valid files found to translate")
                return False
                
            # Calculate batches
            batch_size = self.config.batch_size
            self.total_batches = math.ceil(len(all_files_to_translate) / batch_size)
            print(f"📦 Processing {len(all_files_to_translate)} files in {self.total_batches} batches (batch size: {batch_size})")
            
            # Process files in batches
            for batch_index in range(self.total_batches):
                self.current_batch = batch_index + 1  # 1-based indexing for display
                
                # Reset tracking for this batch
                self.processed_files = []
                self.output_files = []
                
                # Get files for this batch
                start_idx = batch_index * batch_size
                end_idx = min(start_idx + batch_size, len(all_files_to_translate))
                batch_files = all_files_to_translate[start_idx:end_idx]
                
                print(f"\n📋 Processing batch {self.current_batch}/{self.total_batches} with {len(batch_files)} files")
                
                # Process each file in this batch
                for file_path in batch_files:
                    self._translate_file(file_path)
                
                # Exit if no files were processed in this batch
                if not self.processed_files:
                    print(f"⚠️ No files were processed in batch {self.current_batch}")
                    continue
                
                print(f"✅ Successfully translated {len(self.processed_files)} files in batch {self.current_batch}/{self.total_batches}")
                
                # Prepare commit message and PR title for this batch
                commit_message, translation_table, pr_title = self.prepare_commit_message(input_files)
                
                # Handle git operations for this batch
                self.handle_git_operations(commit_message, translation_table, pr_title)
            
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
