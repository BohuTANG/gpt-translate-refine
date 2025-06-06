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


def format_time(seconds):
    """Format time in seconds to a human-readable string"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{seconds:.1f}s"


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
        self.all_processed_files = []  # Track all processed files
        self.directory_files_map = {}
        
        # File processing tracking
        self.current_file_index = 0
        self.total_files = 0
        
        # Generate a unique session ID for this translation run
        self.session_id = self._generate_session_id()
        
        # Statistics tracking
        self.workflow_start_time = time.time()
        self.workflow_start_datetime = datetime.datetime.now()
        
        # PR tracking
        self.pr_number = None
        self.pr_branch_name = None
    
    def process_input_path(self, input_path):
        """Process a single input path (file or directory) and return list of files to translate"""
        
        # Check if path exists
        if not os.path.exists(input_path):
            self._handle_missing_path(input_path)
            return []
        
        # Process directory or file
        if os.path.isdir(input_path):
            files = self._process_directory(input_path)
            if not files:
                print(f"No files to translate in directory: {input_path}")
            return files
        else:
            # For single file, just return it
            return [input_path]
    
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
            # Use file start time from the run method
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
                self.all_processed_files.append(file_path)  # 添加到所有已处理文件列表
                
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
        # TextUtils.show_diff(translated_content, refined_content)
        print("✅ Refinement applied successfully")
        
        return refined_content
    
    def prepare_commit_message(self, input_files):
        """Prepare commit message and PR title with translation details for a single file"""
        # Create a table for all translated files
        files_table = [
            "### 📄 Translated Files",
            "| **Source** | **Output** | **Language** |",
            "| :--- | :--- | :--- |"
        ]
        
        # Get the directory path of the processed file
        dir_path = ""
        if self.processed_files:
            dir_path = os.path.dirname(self.processed_files[0])
        
        # Add current file entry
        if self.processed_files and self.output_files:  # Ensure we have both source and output files
            source_file = self.processed_files[0]
            output_file = self.output_files[0]
            
            # Add to all_processed_files if not already there
            if source_file not in self.all_processed_files:
                self.all_processed_files.append(source_file)
        
        # Add all processed files to the table
        processed_pairs = []
        for source_file in self.all_processed_files:
            # Generate the corresponding output file path
            if self.config.output_files:
                # If explicit output mapping is provided
                output_idx = next((i for i, f in enumerate(self.config.input_files) if f == source_file), None)
                if output_idx is not None and output_idx < len(self.config.output_files):
                    output_file = self.config.output_files[output_idx]
                else:
                    output_file = source_file.replace(os.path.dirname(source_file), dir_path)
            else:
                # Default behavior - replace input directory with output directory
                output_file = source_file.replace(os.path.dirname(source_file), dir_path)
            
            processed_pairs.append((source_file, output_file))
        
        # Add all processed files to the table
        for source_file, output_file in processed_pairs:
            files_table.append(
                f"| `{source_file}` | `{output_file}` | {self.config.target_lang} |"
            )
        
        # Get file name for PR title and commit message
        file_name = "unknown"
        if self.processed_files:
            file_name = os.path.basename(self.processed_files[0])
        
        # Create the commit message
        commit_message = [
            f"🌐 Translate {file_name} to {self.config.target_lang}",
            "",
            f"Translated using {self.config.ai_model}"
        ]
        
        # Add directory information if available
        if dir_path:
            commit_message.append(f"\nDirectory: `{dir_path}`")
        
        # Get token statistics from translator
        token_stats = self.translator.get_statistics()
        input_tokens = token_stats['input_tokens']
        output_tokens = token_stats['output_tokens']
        api_calls = token_stats['api_calls']
        
        # Calculate elapsed time
        total_elapsed_time = time.time() - self.workflow_start_time
        
        # Format times
        def format_time(seconds):
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                return f"{int(hours)}h {int(minutes)}m"
            elif minutes > 0:
                return f"{int(minutes)}m {int(seconds)}s"
            else:
                return f"{int(seconds)}s"
        
        total_time_formatted = format_time(total_elapsed_time)
        
        # Format start and end times
        start_time_str = self.workflow_start_datetime.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate progress percentage
        progress_percent = (self.current_file_index / self.total_files * 100) if self.total_files > 0 else 0
        
        # Add statistics section first
        commit_message.extend([
            "\n### 📊 Translation Statistics",
            f"- Session ID: {self.session_id}",
            f"- File {self.current_file_index}/{self.total_files} ({progress_percent:.1f}%)",
            f"- Total Time: {total_time_formatted}",
            f"- Input Tokens: {input_tokens:,}",
            f"- Output Tokens: {output_tokens:,}",
            f"- API Calls: {api_calls}",
            f"- Start Time: {start_time_str}",
            f"- End Time: {end_time_str}"
        ])
        
        # Add file table after statistics
        commit_message.extend(["", *files_table])
        
        # Join all lines with newlines
        commit_message = "\n".join(commit_message)
        
        # Create PR title with directory information
        # Extract directory name for PR title
        if dir_path:
            # Get the last directory name from the path
            directory_name = os.path.basename(dir_path)
        
        # Add DRAFT prefix to PR title only if not the last file
        if self.current_file_index < self.total_files:
            pr_title = f"[DRAFT] AI Translate {directory_name} to {self.config.target_lang} ({self.current_file_index}/{self.total_files})"
        else:
            # For the last file, don't add DRAFT prefix
            pr_title = f"AI Translate {directory_name} to {self.config.target_lang} ({self.current_file_index}/{self.total_files})"
        
        return commit_message, files_table, pr_title
    
    def handle_git_operations(self, commit_message, translation_table, pr_title=None):
        """Handle git operations: commit, push and create/update PR
        
        For the first file, creates a draft PR.
        For subsequent files, updates the existing PR.
        For the final file, marks the PR as ready for review.
        
        Returns:
            bool: True if file was committed successfully, False otherwise
        """
        print(f"\n📊 Git Operations - File {self.current_file_index}/{self.total_files}")
        print(f"  📁 Files to commit: {len(self.output_files)}")
        
        # We already setup git at the beginning of the run, but we'll check branch status
        print(f"  🔄 Using branch: {self.pr_branch_name}")
        
        # Print detailed commit message information
        print(f"  📝 Commit details:")
        print(f"    - File: {os.path.basename(self.processed_files[0]) if self.processed_files else 'Unknown'}")
        print(f"    - Progress: File {self.current_file_index} of {self.total_files} ({(self.current_file_index/self.total_files*100):.1f}%)")
        
        # Print commit message preview
        print(f"    - Commit message preview:")
        commit_lines = commit_message.split('\n')
        for i, line in enumerate(commit_lines[:5]):
            if line.strip():
                print(f"      {line[:70]}{'...' if len(line) > 70 else ''}")
        if len(commit_lines) > 5:
            print(f"      ... ({len(commit_lines) - 5} more lines)")
            
        # Commit changes and push to remote
        print(f"  📝 Committing translated file...")
        branch_name = self.git_ops.commit_and_push(self.output_files, commit_message, self.pr_branch_name)
        
        # If branch was created/updated and we have GitHub credentials
        if self.git_ops.github_token and self.git_ops.github_repository:
            # If branch_name is None but we're not on the first file, try to use the existing branch name
            if not branch_name and self.current_file_index > 1 and self.pr_branch_name:
                print(f"  ⚠️ Commit failed but continuing with existing branch: {self.pr_branch_name}")
                branch_name = self.pr_branch_name
                
            if branch_name:
                # Use provided PR title or default from config
                if pr_title is None:
                    pr_title = self.config.pr_title.strip()
                    print(f"  📋 Using default PR title: {pr_title}")
                else:
                    print(f"  📋 Using file-specific PR title: {pr_title}")
                
                # Use commit_message as the PR body
                pr_body = commit_message.split('\n')
                print(f"  📄 PR body contains {len(pr_body)} lines with translation details")
                
                # First file or no PR created yet: create PR (draft if more than one file)
                if self.current_file_index == 1 or not self.pr_number:
                    # If this is the only file (current=1, total=1), create a regular PR
                    # Otherwise create a draft PR with [DRAFT] prefix
                    is_draft = self.total_files > 1
                    
                    if is_draft:
                        print("  🔄 Creating draft pull request...")
                        # Ensure PR title has [DRAFT] prefix for draft PRs
                        if not pr_title.startswith("[DRAFT] "):
                            pr_title = f"[DRAFT] {pr_title}"
                        print(f"  📋 Draft PR title: {pr_title}")
                    else:
                        print("  🔄 Creating pull request...")
                        # Ensure PR title doesn't have [DRAFT] prefix for non-draft PRs
                        if pr_title.startswith("[DRAFT] "):
                            pr_title = pr_title.replace("[DRAFT] ", "")
                        print(f"  📋 PR title: {pr_title}")
                    
                    self.pr_number = self.git_ops.create_pull_request(branch_name, pr_title, pr_body, draft=is_draft)
                    if self.pr_number:
                        if is_draft:
                            print(f"  ✅ Draft pull request #{self.pr_number} created successfully")
                        else:
                            print(f"  ✅ Pull request #{self.pr_number} created successfully")
                        print(f"  🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                    else:
                        if is_draft:
                            print("  ⚠️ Failed to create draft pull request")
                        else:
                            print("  ⚠️ Failed to create pull request")
            
                # Subsequent files: update existing PR (keep [DRAFT] prefix until final file)
                elif self.pr_number:
                    print(f"  🔄 Updating pull request #{self.pr_number} with new translation...")
                    print(f"  📋 Current PR title: {pr_title}")
                    if self.git_ops.update_pull_request(self.pr_number, title=pr_title, body=commit_message):
                        print(f"  ✅ Pull request #{self.pr_number} updated successfully with file {self.current_file_index}/{self.total_files} translation")
                    else:
                        print(f"  ⚠️ Failed to update pull request #{self.pr_number}")
                
                # Final file: mark PR as ready for review
                if self.current_file_index == self.total_files and self.pr_number:
                    print(f"\n🏁 Final file completed! Finalizing pull request #{self.pr_number}...")
                    
                    # PR title should already be without [DRAFT] prefix from prepare_commit_message
                    print(f"  📋 Final PR title: {pr_title}")
                    
                    # Mark PR as ready for review using GitHub CLI
                    print(f"  🔄 Marking PR as ready for review...")
                    if self.git_ops.mark_pr_ready_for_review(self.pr_number):
                        print(f"  ✅ Pull request #{self.pr_number} marked as ready for review")
                        print(f"  🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                    else:
                        print(f"  ⚠️ Failed to mark pull request #{self.pr_number} as ready for review")
                        print(f"  ℹ️ You may need to manually mark the PR as ready for review at:")
                        print(f"    {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                        
                    print(f"  📝 Translation PR summary:")
                    print(f"    - Total files: {self.total_files}")
                    print(f"    - Successfully translated: {len(self.all_processed_files)}")
                    print(f"    - PR title: {pr_title}")
                    print(f"    - PR status: Ready for review")
            else:
                print("  ℹ️ Skipping PR operations: GitHub token or repository not available")
                print(f"  ℹ️ Branch '{branch_name}' has been pushed. You can create/update a PR manually.")
        else:
            print("  ℹ️ No branch created or no changes to commit. Skipping PR operations.")
            
        # Print file completion message
        if self.current_file_index < self.total_files:
            print(f"\n✅ File {self.current_file_index}/{self.total_files} completed. Moving to next file...")
        else:
            print(f"\n🎉 All {self.total_files} files completed successfully!")
            print(f"   Total files translated: {len(self.all_processed_files)}")
            if self.pr_number:
                print(f"   PR #{self.pr_number} contains all translations")
                print(f"   PR is now ready for review")
            else:
                print(f"   All files translated locally (no PR created)")
        print("="*60)
        
        # Return True if branch_name is not None (indicating successful commit)
        return branch_name is not None
    
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
    
    # Removed batch-related methods as we're now processing files individually
    
    def run(self):
        """Run the complete translation workflow with file-by-file processing"""
        try:
            # Record start time
            workflow_start_time = time.time()
            self.workflow_start_time = workflow_start_time
            self.workflow_start_datetime = datetime.datetime.now()
            start_time_str = self.workflow_start_datetime.strftime("%Y-%m-%d %H:%M:%S")
            
            # Initialize tracking variables
            self.all_processed_files = []
            
            # Display session ID and start time
            print(f"\n🆔 Translation session ID: {self.session_id}")
            print(f"🕒 Started at: {start_time_str}")
            
            # Process input files from config
            all_files_to_translate = []
            if self.config.input_files:
                # Split input paths by comma if multiple paths are provided
                input_paths = [p.strip() for p in self.config.input_files.split(',') if p.strip()]
                for input_path in input_paths:
                    files = self.process_input_path(input_path)
                    if files:
                        all_files_to_translate.extend(files)
            
            # Remove duplicates while preserving order
            all_files_to_translate = list(dict.fromkeys(all_files_to_translate))
            
            if not all_files_to_translate:
                print("\n\u274c No files found to translate. Exiting.")
                return False
                
            print(f"\n📋 Found {len(all_files_to_translate)} files to translate")
            
            # Group files by directory for better organization
            self.directory_files_map = self._group_files_by_directory(all_files_to_translate)
            
            # Set total files count
            self.total_files = len(all_files_to_translate)
            
            # Create a branch for all files in this session
            print(f"\n🔄 Using file-by-file workflow: Will create one draft PR and update it with each file")
            
            # Create a branch for this translation session
            self.pr_branch_name = f"translation-{self.session_id}"
            print(f"\n🌱 Creating branch: {self.pr_branch_name}")
            self.git_ops.setup_git()
            
            # Track if any files were actually committed
            any_files_committed = False
            
            # Process each file
            for i, file_path in enumerate(all_files_to_translate, 1):
                self.current_file_index = i
                self.processed_files = []
                self.output_files = []
                
                # Print progress information
                print(f"\n📄 Processing file {i}/{self.total_files} ({i/self.total_files*100:.1f}%)")
                print(f"  🔄 File: {file_path}")
                print(f"  \u23f1\ufe0f Started at: {datetime.datetime.now().strftime('%H:%M:%S')}")
                
                # Calculate and display elapsed time and estimated remaining time
                if i > 1:
                    elapsed_seconds = time.time() - self.workflow_start_time
                    avg_time_per_file = elapsed_seconds / (i - 1)
                    remaining_files = self.total_files - (i - 1)
                    estimated_remaining = avg_time_per_file * remaining_files
                    
                    print(f"  \u23f1\ufe0f Elapsed: {format_time(elapsed_seconds)}, Estimated remaining: {format_time(estimated_remaining)}")
                
                # Translate the file
                self._translate_file(file_path)
                
                # Add to all processed files list
                if self.processed_files:
                    self.all_processed_files.extend(self.processed_files)
                
                # Prepare commit message and PR title
                commit_message, translation_table, pr_title = self.prepare_commit_message(self.processed_files)
                
                # Handle git operations for this file
                commit_result = self.handle_git_operations(commit_message, translation_table, pr_title)
                if commit_result:
                    any_files_committed = True
                
                print(f"\n\u2705 File {i}/{self.total_files} completed. {'Moving to next file...' if i < self.total_files else 'All files processed!'}")
                print("============================================================")
            
            # If this is the last file and we have a PR but no files were committed,
            # still mark the PR as ready for review
            if self.pr_number and not any_files_committed and self.current_file_index == self.total_files:
                print(f"\n🏁 All files processed! Finalizing pull request #{self.pr_number}...")
                
                # Create a final PR title without [DRAFT] prefix
                final_pr_title = self.config.pr_title
                if final_pr_title.startswith("[DRAFT] "):
                    final_pr_title = final_pr_title.replace("[DRAFT] ", "")
                print(f"  📋 Final PR title: {final_pr_title}")
                
                # Mark PR as ready for review
                print(f"  🔄 Marking PR as ready for review...")
                if self.git_ops.mark_pr_ready_for_review(self.pr_number):
                    print(f"  \u2705 Pull request #{self.pr_number} marked as ready for review")
                    print(f"  🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                else:
                    print(f"  \u26a0\ufe0f Failed to mark pull request #{self.pr_number} as ready for review")
                    print(f"  \u2139\ufe0f You may need to manually mark the PR as ready for review at:")
                    print(f"    {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
            
            # Print final summary
            total_elapsed_time = time.time() - self.workflow_start_time
            print(f"\n🎉 Translation workflow completed!")
            print(f"  \u23f1\ufe0f Total time: {format_time(total_elapsed_time)}")
            print(f"  📊 Files processed: {self.total_files}")
            print(f"  📊 Files successfully translated: {len(self.all_processed_files)}")
            
            if self.pr_number:
                print(f"  🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
            else:
                print(f"  \u2139\ufe0f No PR was created. This could be because no files needed translation or there was an issue with the Git operations.")
                
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
