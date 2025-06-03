#!/usr/bin/env python3

import re
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Set
from contextlib import contextmanager


class FileProcessor:
    """Handles all file operations for the translation workflow using modern Python patterns"""
    
    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config
    
    def get_input_files(self) -> List[str]:
        """Parse and normalize input file paths from environment variable"""
        if not self.config.input_files:
            return []
        
        # Split by spaces and normalize paths (remove leading './')
        return [
            file_path[2:] if file_path.startswith('./') else file_path
            for file_path in self.config.input_files.split()
            if file_path.strip()
        ]
    
    def get_output_path(self, input_path: str) -> str:
        """Generate output path based on input path and output pattern"""
        # If no wildcard pattern, return output path directly
        if not self.config.output_files or '*' not in self.config.output_files:
            return self.config.output_files
        
        # Convert to Path objects for easier manipulation
        input_path_obj = Path(input_path)
        output_format = self.config.output_files
        
        # Derive language code from TARGET_LANG
        lang_code = self.config.target_lang.lower().replace(' ', '_').replace('-', '_')
        
        # Handle directory structure preservation with '**' pattern
        if '**' in output_format:
            # Extract base directory from output format
            if base_match := re.match(r'^(.*?)\*\*', output_format):
                base_dir = base_match.group(1)
                
                # Preserve directory structure
                output_path = Path(base_dir) / input_path_obj.parent / input_path_obj.name
                
                # Handle extension patterns if present
                if '{' in output_format and '}' in output_format:
                    if ext_pattern := re.search(r'\*\*\/\*\.{(.*?)}', output_format):
                        allowed_exts = ext_pattern.group(1).split(',')
                        if input_path_obj.suffix[1:] in allowed_exts:  # Remove leading dot
                            return str(output_path)
                
                return str(output_path)
        
        # Simple replacement for non-directory-preserving patterns
        filename = input_path_obj.name
        name = input_path_obj.stem
        ext = input_path_obj.suffix
        
        # Replace all placeholders
        output_path = output_format.replace('*', filename)
        output_path = output_path.replace('{name}', name)
        output_path = output_path.replace('{ext}', ext[1:] if ext.startswith('.') else ext)
        output_path = output_path.replace('{lang}', lang_code)
        
        return output_path
    
    def find_files_recursively(self, directory: str) -> List[str]:
        """Find all files in a directory recursively using pathlib"""
        return [str(path) for path in Path(directory).rglob('*') if path.is_file()]
    
    def ensure_directory_exists(self, file_path: str) -> None:
        """Ensure the directory for a file exists using pathlib"""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    
    def read_file(self, file_path: str) -> str:
        """Read content from a file using pathlib"""
        try:
            return Path(file_path).read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Write content to a file using pathlib"""
        try:
            # Ensure directory exists
            self.ensure_directory_exists(file_path)
            
            # Write content
            Path(file_path).write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Error writing to file {file_path}: {e}")
            return False
    
    @staticmethod
    def extract_yaml_and_content(text: str) -> Tuple[Optional[Dict[str, Any]], str, bool]:
        """Extract YAML frontmatter and content from Markdown text"""
        if yaml_match := re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL):
            try:
                yaml_text, content = yaml_match.groups()
                yaml_data = yaml.safe_load(yaml_text)
                return yaml_data, content, True
            except Exception as e:
                print(f"Error parsing YAML frontmatter: {e}")
        
        return None, text, False
    
    @staticmethod
    def reconstruct_markdown(yaml_data: Optional[Dict[str, Any]], content: str, has_frontmatter: bool) -> str:
        """Reconstruct Markdown with YAML frontmatter and content"""
        if not has_frontmatter or yaml_data is None:
            return content
        
        try:
            yaml_text = yaml.dump(yaml_data, allow_unicode=True, sort_keys=False)
            return f"---\n{yaml_text}---\n\n{content}"
        except Exception as e:
            print(f"Error reconstructing Markdown with YAML frontmatter: {e}")
            return content
