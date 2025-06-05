#!/usr/bin/env python3

import os
import sys
import traceback
import math
import uuid
import time
import datetime
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
        try:
            start_time = time.time()
            print(f"\n📄 Translating file: {file_path}")
            
            # Skip if file doesn't exist
            if not os.path.exists(file_path):
                print(f"\n❌ File not found: {file_path}")
                return
            
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
                
                # Track the processed file
                self.processed_files.append(file_path)
                self.output_files.append(output_path)
                
                # Add to directory map if this file is part of a directory being processed
                for dir_path in self.directory_files_map:
                    if file_path.startswith(dir_path):
                        self.directory_files_map[dir_path].append(file_path)
                
                # Log completion time
                elapsed_time = time.time() - start_time
                print(f"  ✅ Completed in {elapsed_time:.2f} seconds")
            
        except Exception as e:
            print(f"\n❌ Error translating file {file_path}: {e}")
            traceback.print_exc()
    
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
    
    def _group_files_by_directory(self, input_files):
        """Group files by their last-level directory structure"""
        dir_groups = {}
        
        for file_path in input_files:
            # Get the parent directory path
            parent_dir = os.path.dirname(file_path)
            # Get the last directory name
            last_dir = os.path.basename(parent_dir)
            
            # If parent directory is empty (file is in root), use a special key
            if not last_dir:
                last_dir = "_root_"
                
            # Add file to its directory group
            if last_dir not in dir_groups:
                dir_groups[last_dir] = []
            dir_groups[last_dir].append(file_path)
        
        return dir_groups
    
    def _create_batches_by_directory(self, dir_groups):
        """Create batches based on directory groups, trying to keep directories together"""
        batches = []
        current_batch = []
        current_batch_size = 0
        
        # Sort directories by size (number of files) in descending order
        # This helps process larger directories first
        sorted_dirs = sorted(dir_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        for dir_name, files in sorted_dirs:
            dir_size = len(files)
            
            # If this directory alone exceeds batch_size but current batch is empty,
            # make this directory its own batch (keep directory together)
            if dir_size > self.config.batch_size and current_batch_size == 0:
                batches.append(files)
                print(f"  📂 Directory '{dir_name}' with {dir_size} files will be its own batch")
                continue
                
            # If adding this directory would exceed batch_size and we already have files,
            # finalize current batch and start a new one
            if current_batch_size + dir_size > self.config.batch_size and current_batch_size > 0:
                batches.append(current_batch)
                current_batch = []
                current_batch_size = 0
            
            # Add all files from this directory to the current batch
            current_batch.extend(files)
            current_batch_size += dir_size
            print(f"  📂 Added directory '{dir_name}' with {dir_size} files to batch")
        
        # Add any remaining files in the current batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def run(self):
        """Run the complete translation workflow with batch processing"""
        try:
            # Record start time
            workflow_start_time = time.time()
            start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Display session ID and start time
            print(f"🆔 Translation session ID: {self.session_id}")
            print(f"🕒 Started at: {start_time_str}")
            
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
            
            # Group files by directory
            print("\n📁 Grouping files by directory structure...")
            dir_groups = self._group_files_by_directory(all_files_to_translate)
            
            # Create batches based on directory groups
            print("\n📂 Creating batches based on directory structure...")
            batches = self._create_batches_by_directory(dir_groups)
            
            # Set total number of batches
            self.total_batches = len(batches)
            print(f"\n📃 Created {self.total_batches} batch(es) from {len(all_files_to_translate)} files")
            
            # Process each batch
            for batch_index, batch_files in enumerate(batches):
                # Reset tracking for this batch
                self.current_batch = batch_index + 1  # 1-based index for display
                self.processed_files = []
                self.output_files = []
                self.directory_files_map = {}
                
                batch_start_time = time.time()
                batch_start_str = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"\n✨ Processing batch {self.current_batch}/{self.total_batches} with {len(batch_files)} files")
                print(f"  🕒 Batch started at: {batch_start_str}")
                
                # Process each file in this batch
                for file_path in batch_files:
                    self._translate_file(file_path)
                
                # Calculate batch statistics
                batch_files_count = len(self.processed_files)
                batch_elapsed_time = time.time() - batch_start_time
                avg_time_per_file = batch_elapsed_time / batch_files_count if batch_files_count > 0 else 0
                
                # If files were processed in this batch, handle git operations
                if self.processed_files:
                    # Log batch completion statistics
                    print(f"  📊 Batch {self.current_batch} statistics:")
                    print(f"    - Files processed: {batch_files_count}")
                    print(f"    - Total time: {batch_elapsed_time:.2f} seconds")
                    print(f"    - Average time per file: {avg_time_per_file:.2f} seconds")
                    
                    # Prepare commit message and PR title
                    commit_message, translation_table, pr_title = self.prepare_commit_message(batch_files)
                    
                    # Handle git operations for this batch
                    self.handle_git_operations(commit_message, translation_table, pr_title)
                else:
                    print(f"\n⚠️ No files were processed in batch {self.current_batch}")
            
            # Calculate and display overall workflow statistics
            workflow_elapsed_time = time.time() - workflow_start_time
            total_files_processed = sum(len(batch) for batch in batches)
            
            # Format time in a readable way
            hours, remainder = divmod(workflow_elapsed_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_format = f"{int(hours)}h {int(minutes)}m {seconds:.2f}s" if hours > 0 else \
                         f"{int(minutes)}m {seconds:.2f}s" if minutes > 0 else \
                         f"{seconds:.2f}s"
            
            print(f"\n🌟 Translation workflow completed!")
            print(f"  📊 Overall statistics:")
            print(f"    - Total files processed: {total_files_processed}")
            print(f"    - Total batches: {self.total_batches}")
            print(f"    - Total time: {time_format}")
            print(f"    - Average time per file: {workflow_elapsed_time / total_files_processed:.2f} seconds")
            print(f"    - Average time per batch: {workflow_elapsed_time / self.total_batches:.2f} seconds")
            
            end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  🕒 Finished at: {end_time_str}")
            
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
