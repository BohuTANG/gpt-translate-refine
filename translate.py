#!/usr/bin/env python3

import os
import sys
import traceback
import time
import datetime
import uuid
from typing import List, Dict, Tuple
from pathlib import Path

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
    
    def prepare_commit_message(self) -> Tuple[str, List[str], str]:
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
        
        # PR title
        directory_name = os.path.basename(os.path.dirname(self.processed_files[0])) if self.processed_files else "files"
        
        if self.current_file_index < self.total_files:
            pr_title = f"[DRAFT] AI Translate {directory_name} to {self.config.target_lang} ({self.current_file_index}/{self.total_files})"
        else:
            pr_title = f"AI Translate {directory_name} to {self.config.target_lang} ({self.current_file_index}/{self.total_files})"
        
        return commit_message, commit_lines, pr_title
    
    def handle_git_operations(self, commit_message: str, pr_title: str) -> bool:
        """Handle git operations: commit, push and create/update PR"""
        print(f"\n📊 Git Operations - File {self.current_file_index}/{self.total_files}")
        print(f"  📁 Files to commit: {len(self.output_files)}")
        print(f"  🔄 Using branch: {self.pr_branch_name}")
        
        # Commit and push
        print("📝 Committing translated file...")
        branch_name = self.git_ops.commit_and_push(self.output_files, commit_message, self.pr_branch_name)
        
        if not branch_name:
            print("❌ Failed to commit changes")
            return False
        
        # Handle PR operations
        if self.git_ops.github_token and self.git_ops.github_repository:
            if self.current_file_index >= 1 or not self.pr_number:
                # Create PR
                is_draft = self.total_files > 1
                print(f"🔄 Creating {'draft ' if is_draft else ''}pull request...")
                
                self.pr_number = self.git_ops.create_pull_request(
                    branch_name, pr_title, commit_message.split('\n'), draft=is_draft
                )
                
                if self.pr_number:
                    print(f"✅ {'Draft p' if is_draft else 'P'}ull request #{self.pr_number} created")
                    print(f"🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
                else:
                    print("⚠️ Failed to create pull request")
            
            elif self.pr_number:
                # Update existing PR
                print(f"🔄 Updating pull request #{self.pr_number}...")
                if self.git_ops.update_pull_request(self.pr_number, title=pr_title, body=commit_message):
                    print(f"✅ Pull request #{self.pr_number} updated")
                else:
                    print(f"⚠️ Failed to update pull request #{self.pr_number}")
            
            # Mark as ready for review if final file
            if self.current_file_index == self.total_files and self.pr_number:
                print(f"\n🏁 Final file completed! Finalizing pull request #{self.pr_number}...")
                if self.git_ops.mark_pr_ready_for_review(self.pr_number):
                    print(f"✅ Pull request #{self.pr_number} marked as ready for review")
                else:
                    print(f"⚠️ Failed to mark pull request #{self.pr_number} as ready for review")
        
        return True
    
    def run(self) -> bool:
        """Run the complete translation workflow"""
        try:
            # Initialize
            start_time_str = self.workflow_start_datetime.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🆔 Translation session ID: {self.session_id}")
            print(f"🕒 Started at: {start_time_str}")
            
            # Process input files
            all_files_to_translate = []
            if self.config.input_files:
                input_paths = [p.strip() for p in self.config.input_files.split(',') if p.strip()]
                for input_path in input_paths:
                    files = self.process_input_path(input_path)
                    if files:
                        all_files_to_translate.extend(files)
            
            # Remove duplicates
            all_files_to_translate = list(dict.fromkeys(all_files_to_translate))
            
            if not all_files_to_translate:
                print("\n❌ No files found to translate. Exiting.")
                return False
            
            print(f"\n📋 Found {len(all_files_to_translate)} unique file(s) to translate after processing all input paths.")
            for idx, f_path in enumerate(all_files_to_translate, 1):
                print(f"    {idx}. {f_path}")
            self.total_files = len(all_files_to_translate)
            
            # Setup branch
            self.pr_branch_name = f"translation-{self.session_id}"
            print(f"\n🌱 Creating branch: {self.pr_branch_name}")
            self.git_ops.setup_git()
            
            # Process each file
            for i, file_path in enumerate(all_files_to_translate, 1):
                self.current_file_index = i
                self.processed_files = []
                self.output_files = []
                
                print(f"\n📄 Processing file {i}/{self.total_files} ({i/self.total_files*100:.1f}%)")
                print(f"  🔄 File: {file_path}")
                print(f"  ⏱️ Started at: {datetime.datetime.now().strftime('%H:%M:%S')}")
                
                # Show progress estimates
                if i > 1:
                    elapsed_seconds = time.time() - self.workflow_start_time
                    avg_time_per_file = elapsed_seconds / (i - 1)
                    remaining_files = self.total_files - (i - 1)
                    estimated_remaining = avg_time_per_file * remaining_files
                    print(f"  ⏱️ Elapsed: {format_time(elapsed_seconds)}, Estimated remaining: {format_time(estimated_remaining)}")
                
                # Translate file
                if self.translate_file(file_path):
                    # Prepare commit message and handle git operations
                    commit_message, _, pr_title = self.prepare_commit_message()
                    self.handle_git_operations(commit_message, pr_title)
                
                print(f"\n✅ File {i}/{self.total_files} completed")
                print("=" * 60)
            
            # Final summary
            total_elapsed_time = time.time() - self.workflow_start_time
            print(f"\n🎉 Translation workflow completed!")
            print(f"  ⏱️ Total time: {format_time(total_elapsed_time)}")
            print(f"  📊 Files processed: {self.total_files}")
            print(f"  📊 Files successfully translated: {len(self.all_processed_files)}")
            
            if self.pr_number:
                print(f"  🔗 PR URL: {self.git_ops.github_server_url}/{self.git_ops.github_repository}/pull/{self.pr_number}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in translation workflow: {e}")
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
