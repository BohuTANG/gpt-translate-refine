#!/usr/bin/env python3

import os
import sys
import traceback
import time
import datetime
import uuid
from typing import List, Dict, Tuple
from pathlib import Path

# Version identifier - Update this when code changes
VERSION = "1.4.5"
BUILD_DATE = "2025-06-07"

from src.config import Config
from src.translator import Translator
from src.file_processor import FileProcessor
from src.git_operations import GitOperations


def format_time(seconds: float) -> str:
    """Format time in seconds to human-readable string"""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{seconds:.1f}s"


class TranslationWorkflow:
    """Main translation workflow orchestrator"""
    
    def __init__(self, config: Config):
        self.config = config
        self.file_processor = FileProcessor(config)
        self.translator = Translator(config)
        self.git_ops = GitOperations(config)
        
        # Session tracking
        self.session_id = self._generate_session_id()
        self.workflow_start_time = time.time()
        self.workflow_start_datetime = datetime.datetime.now()
        
        # File tracking
        self.processed_files = []
        self.output_files = []
        self.all_processed_files = []
        self.current_file_index = 0
        self.total_files = 0
        
        # PR tracking
        self.pr_number = None
        self.pr_branch_name = None
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = int(time.time()) % 10000
        random_part = uuid.uuid4().hex[:3]
        return f"{timestamp}{random_part}"
    
    def process_input_path(self, input_path: str) -> List[str]:
        """Process input path and return files to translate"""
        print(f"  🔍 Processing input path: {input_path}")
        if not os.path.exists(input_path):
            self._handle_missing_path(input_path)
            return []
        
        if os.path.isdir(input_path):
            print(f"  📁 Path is a directory. Searching for files recursively...")
            files = self.file_processor.find_files_recursively(input_path)
            if not files:
                print(f"  🟡 No files to translate in directory: {input_path}")
            else:
                print(f"  📂 Found {len(files)} file(s) in directory: {input_path}")
            return files
        
        print(f"  📄 Path is a single file: {input_path}")
        
        return [input_path]
    
    def _handle_missing_path(self, input_path: str) -> None:
        """Handle missing input path"""
        print(f"Error: Path not found: {input_path}")
        print(f"Current working directory: {os.getcwd()}")
        
        parent_dir = os.path.dirname(input_path) or '.'
        if os.path.exists(parent_dir):
            print(f"Contents of parent directory ({parent_dir}):")
            for item in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item)
                item_type = 'dir' if os.path.isdir(item_path) else 'file'
                print(f"  - {item} ({item_type})")
    
    def translate_file(self, file_path: str) -> bool:
        """Translate a single file"""
        try:
            start_time = time.time()
            print(f"\n📄 Translating file: {file_path}")
            
            if not os.path.exists(file_path):
                print(f"  ❌ Error: Source file not found: {file_path}")
                return False
            print(f"  ✅ Source file exists: {file_path}")
            
            # Read and translate
            print(f"  📖 Reading content from: {file_path}...")
            content = self.file_processor.read_file(file_path)
            if not content:
                print(f"  ❌ Error: Could not read file or file is empty: {file_path}")
                return False
            print(f"  📑 Successfully read {len(content)} characters from: {file_path}")
            
            print(f"  🛤️ Determining output path for: {file_path}...")
            output_path = self.file_processor.get_output_path(file_path)
            if not output_path:
                print(f"  ❌ Error: Could not determine output path for: {file_path}")
                return False
            
            print(f"  🎯 Determined output path: {output_path}")
            print(f"Translating with model: {self.config.ai_model}...")
            
            translated_content = self.translator.translate(content)
            if not translated_content:
                print(f"Error: Translation failed for: {file_path}")
                return False
            
            # Apply refinement if enabled
            if self.config.refine_enabled:
                print("Refining translation...")
                refined_content = self.translator.refine(translated_content, content)
                if refined_content:
                    translated_content = refined_content
                    print("✅ Refinement applied successfully")
                else:
                    print("⚠️ Refinement failed, using original translation")
            
            # Write output
            print(f"  💾 Writing translated content to: {output_path}...")
            if self.file_processor.write_file(output_path, translated_content):
                print(f"  ✅ Translation successfully saved to: {output_path}")
                
                # Track processed files
                self.processed_files.append(file_path)
                self.output_files.append(output_path)
                self.all_processed_files.append(file_path)
                
                elapsed_time = time.time() - start_time
                print(f"  ✅ Completed in {elapsed_time:.2f} seconds")
                return True
            
            return False
            
        except Exception as e:
            print(f"\n❌ Error translating file {file_path}: {e}")
            traceback.print_exc()
            return False
    
    def prepare_commit_message(self) -> Tuple[str, str, str]:
        """Prepare commit message and PR title"""
        # File info
        file_name = "unknown"
        if self.processed_files:
            file_name = os.path.basename(self.processed_files[0])
        
        # Statistics
        token_stats = self.translator.get_statistics()
        total_elapsed_time = time.time() - self.workflow_start_time
        progress_percent = (self.current_file_index / self.total_files * 100) if self.total_files > 0 else 0
        
        # Build commit message
        commit_lines = [
            f"🌐 Translate {file_name} to {self.config.target_lang}",
            "",
            f"Translated using {self.config.ai_model}",
            "",
            "### 📊 Translation Statistics",
            f"- Session ID: {self.session_id}",
            f"- File {self.current_file_index}/{self.total_files} ({progress_percent:.1f}%)",
            f"- Total Time: {format_time(total_elapsed_time)}",
            f"- Input Tokens: {token_stats['input_tokens']:,}",
            f"- Output Tokens: {token_stats['output_tokens']:,}",
            f"- API Calls: {token_stats['api_calls']}",
            f"- Start Time: {self.workflow_start_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- End Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "### 📄 Translated Files",
            "| **Source** | **Output** | **Language** |",
            "| :--- | :--- | :--- |"
        ]
        
        # Add file entries
        for source_file in self.all_processed_files:
            output_file = self.file_processor.get_output_path(source_file)
            commit_lines.append(f"| `{source_file}` | `{output_file}` | {self.config.target_lang} |")
        
        commit_message = "\n".join(commit_lines)
        
        # PR titles
        directory_name = os.path.basename(os.path.dirname(self.processed_files[0])) if self.processed_files else "files"
        base_pr_title = f"AI Translate {directory_name} to {self.config.target_lang}"
        
        # Always include progress in title for multi-file translations
        if self.total_files > 1:
            api_pr_title = f"[DRAFT] {base_pr_title} ({self.current_file_index}/{self.total_files})"
        else:
            api_pr_title = base_pr_title

        # Note: commit_lines is not used by callers anymore, returning base_pr_title instead.
        return commit_message, base_pr_title, api_pr_title
    
    def handle_git_operations(self, git_commit_subject: str, pr_body_content: str, base_pr_title: str, api_pr_title: str) -> bool:
        """Handle git operations: commit, push and create/update PR"""
        print(f"\n📊 Git Operations - File {self.current_file_index}/{self.total_files}")
        print(f"  📁 Files to commit: {len(self.output_files)}")
        print(f"  🔄 Using branch: {self.pr_branch_name}")
        
        # Commit and push
        print(f"📝 Committing translated file with subject: '{git_commit_subject}'...")
        branch_name = self.git_ops.commit_and_push(self.output_files, git_commit_subject, self.pr_branch_name)
        
        if not branch_name:
            print("❌ Failed to commit changes or no changes found for this file.") # Clarified log
            return False # No commit, so no PR update for this file's processing.
        
        # Handle PR operations
        if self.git_ops.github_token and self.git_ops.github_repository:
            # We should already have a PR number from the initial PR creation
            # Just update the existing PR with new title and body
            if self.pr_number:
                print(f"🔄 Updating pull request #{self.pr_number} with new title and body...")
                if self.git_ops.update_pull_request(self.pr_number, title=api_pr_title, body=pr_body_content):
                    print(f"✅ Pull request #{self.pr_number} updated successfully")
                else:
                    print(f"⚠️ Failed to update pull request #{self.pr_number}")
            else:
                # Fallback: If for some reason we don't have a PR number yet, create one
                print(f"🔄 Creating draft pull request with title: '{api_pr_title}'...")
                
                self.pr_number = self.git_ops.create_pull_request(
                    branch_name, 
                    api_pr_title,
                    pr_body_content,
                    draft=True
                )
                
                if self.pr_number:
                    print(f"✅ Draft pull request #{self.pr_number} created successfully")
                    print(f"🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                else:
                    print("⚠️ Failed to create draft pull request")
        
        return True
    
    def run(self) -> bool:
        """Run the complete translation workflow"""
        try:
            self.workflow_start_time = time.time()
            self.workflow_start_datetime = datetime.datetime.now()
            
            # Display version information at the very beginning
            print(f"\n🔎 Version: {VERSION} (Build: {BUILD_DATE})")
            print(f"\n🚀 Starting translation workflow at {self.workflow_start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Session ID: {self.session_id}")
            print(f"   Input path(s): {self.config.input_files}")
            print(f"   Output path pattern: {self.config.output_files}")
            print(f"   Target language: {self.config.target_lang}")
            print("-" * 60)

            all_files_to_translate = []
            # Process input files from comma-separated list
            input_paths = [p.strip() for p in self.config.input_files.split(',') if p.strip()]
            for input_path_item in input_paths:
                processed_paths = self.process_input_path(input_path_item)
                if processed_paths: # Ensure it's not None or empty
                    all_files_to_translate.extend(processed_paths)
            
            if not all_files_to_translate:
                print("🤷 No files found to translate. Exiting.")
                return True

            self.total_files = len(all_files_to_translate)
            print(f"🔍 Found {self.total_files} file(s) to process.")
            for idx, f_path in enumerate(all_files_to_translate, 1):
                print(f"    {idx}. {f_path}")

            # Always prepare branch for PR creation
            # PR creation is always enabled by default
            self.git_ops.setup_git() # Ensure git user is configured
            self.pr_branch_name = self.git_ops.prepare_git_branch() # prepare_git_branch should handle session_id
            if not self.pr_branch_name:
                print("❌ Failed to prepare Git branch. Aborting PR-related operations.")
                # If branch preparation fails, we stop.
                return False
                
            # Create an initial empty commit and push the branch before creating PR
            print("\n📣 Preparing branch for PR creation...")
            initial_commit_message = f"[INIT] Start translation to {self.config.target_lang}"
            
            # Create an empty commit to initialize the branch
            try:
                # Create .gitkeep file to ensure we have something to commit
                gitkeep_path = os.path.join(os.getcwd(), ".translation-init")
                with open(gitkeep_path, "w") as f:
                    f.write(f"Translation initialization: {datetime.datetime.now().isoformat()}\n")
                
                # Add and commit the file
                self.git_ops.run_command(["git", "add", ".translation-init"])
                code, _, stderr = self.git_ops.run_command(["git", "commit", "-m", initial_commit_message])
                if code != 0:
                    print(f"⚠️ Initial commit failed: {stderr}")
                
                # Push the branch
                print(f"🚀 Pushing branch '{self.pr_branch_name}' to remote...")
                code, _, stderr = self.git_ops.run_command(["git", "push", "-u", "origin", self.pr_branch_name])
                if code != 0:
                    print(f"⚠️ Failed to push branch: {stderr}")
                    # Continue anyway, as we'll try to create PR
                else:
                    print(f"✅ Branch '{self.pr_branch_name}' pushed successfully")
            except Exception as e:
                print(f"⚠️ Error preparing branch: {e}")
                # Continue anyway as we'll try to create PR
            
            # Now create the initial draft PR
            print("\n📣 Creating initial draft PR...")
            initial_pr_title = f"[DRAFT] AI Translate to {self.config.target_lang} (0/{self.total_files})"
            initial_pr_body = f"# Translation in Progress\n\n* **Target Language:** {self.config.target_lang}\n* **Total Files:** {self.total_files}\n* **Status:** Starting translation...\n\n> This PR will be updated as files are processed."
            
            self.pr_number = self.git_ops.create_pull_request(self.pr_branch_name, initial_pr_title, initial_pr_body, draft=True)
            if self.pr_number:
                print(f"✅ Created draft pull request #{self.pr_number} successfully")
                print(f"🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
            else:
                print("⚠️ Could not create initial draft PR. Will attempt to create it after the first file is processed.")
            print("-" * 60)
            
            for i, file_path in enumerate(all_files_to_translate, 1):
                self.current_file_index = i
                
                print(f"\n📄 Processing file {i}/{self.total_files} ({i/self.total_files*100:.1f}%)")
                print(f"  🔄 File: {file_path}")
                file_start_time = time.time()
                print(f"  ⏱️ Started at: {datetime.datetime.now().strftime('%H:%M:%S')}")
                
                if i > 1:
                    elapsed_workflow_time = time.time() - self.workflow_start_time
                    avg_time_per_file = elapsed_workflow_time / (i - 1)
                    remaining_files_count = self.total_files - i 
                    estimated_remaining_time = avg_time_per_file * remaining_files_count
                    if estimated_remaining_time < 0: estimated_remaining_time = 0
                    print(f"  ⏱️ Workflow elapsed: {format_time(elapsed_workflow_time)}, Approx. remaining: {format_time(estimated_remaining_time)}")
                
                if self.translate_file(file_path): # This method logs its own success/failure
                    if self.pr_branch_name: # Only do git ops if branch is ready
                        # Add information about next file or completion status
                        next_file_info = ""
                        if i < self.total_files:
                            next_file = all_files_to_translate[i]  # i is already incremented for next iteration
                            next_file_info = f"\n\n### 🔜 Next File\nProcessing: `{next_file}` ({i+1}/{self.total_files})"
                        else:
                            next_file_info = "\n\n### ✅ All Files Processed\nFinalizing PR and marking as ready for review..."
                        
                        commit_message_full_body, base_pr_title, api_pr_title = self.prepare_commit_message()
                        # Add next file info to PR body
                        commit_message_full_body += next_file_info
                        
                        git_commit_subject = commit_message_full_body.splitlines()[0] if commit_message_full_body else f"Translate {os.path.basename(file_path)}"
                        
                        self.handle_git_operations(
                            git_commit_subject,
                            commit_message_full_body,
                            base_pr_title,
                            api_pr_title
                        )
                    elif not self.pr_branch_name:
                        print("  ℹ️ Git branch was not properly prepared. Skipping Git operations for this file.")
                    # PR creation is always enabled by default
                else:
                    print(f"  ⚠️ Translation failed or was skipped for {file_path}. See logs above.")
                
                file_processing_time = time.time() - file_start_time
                print(f"  ⏱️ Time for this file: {format_time(file_processing_time)}")
                print(f"✅ File {i}/{self.total_files} processing completed for ({file_path})")
                print("=" * 60)
            # End of the for loop

            total_workflow_time = time.time() - self.workflow_start_time
            print(f"\n🎉 Translation workflow processing loop completed!")
            print(f"  ⏱️ Total time for workflow: {format_time(total_workflow_time)}")
            print(f"  📊 Files attempted: {self.total_files}")
            # Consider adding a counter for successfully processed files if self.all_processed_files is used
            # print(f"  📊 Files successfully resulting in output: {len(self.all_processed_files)}")

            if self.pr_number: # Finalize PR if one exists
                # First update PR with final title (without DRAFT prefix)
                print(f"\n🏁 Finalizing Pull Request #{self.pr_number} after all files processed...")
                
                # Get the final PR title and body
                final_commit_message, final_pr_title, _ = self.prepare_commit_message()
                # Remove [DRAFT] prefix from title for final update
                if "[DRAFT]" in final_pr_title:
                    final_pr_title = final_pr_title.replace("[DRAFT] ", "")
                
                print(f"  🔄 Updating PR #{self.pr_number} with final title: '{final_pr_title}'...")
                if self.git_ops.update_pull_request(self.pr_number, title=final_pr_title, body=final_commit_message):
                    print(f"  ✅ Pull request #{self.pr_number} title and summary updated with final version.")
                else:
                    print(f"  ⚠️ Failed to update pull request #{self.pr_number} with final title and summary.")
                
                # Now mark PR as ready for review
                print(f"  🔄 Marking PR #{self.pr_number} as ready for review...")
                if self.git_ops.mark_pr_ready_for_review(self.pr_number):
                    print(f"  ✅ Pull request #{self.pr_number} successfully marked as ready for review.")
                else:
                    print(f"  ⚠️ Failed to mark pull request #{self.pr_number} as ready for review.")
                print(f"  🔗 Final PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
            elif self.total_files > 0 and not self.pr_number:
                print("ℹ️ No pull request was created or updated (perhaps no files had changes or an early error occurred, or branch setup failed).")
            
            print("\nWorkflow finished.")
            return True
            
        except Exception as e:
            print(f"❌ An unexpected error occurred in the translation workflow: {e}")
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    try:
        config = Config()
        config.print_config()
        
        workflow = TranslationWorkflow(config)
        success = workflow.run()
        
        if not success:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
