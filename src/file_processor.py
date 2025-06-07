#!/usr/bin/env python3

import os
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
        
        # Handle the case where multiple paths are provided as a single string
        input_files_str = self.config.input_files
        
        # First check if the entire string is a single path that exists
        if os.path.exists(input_files_str):
            return [input_files_str]
        
        # Otherwise, split by spaces and process each path
        result = []
        for path in input_files_str.split():
            path = path.strip()
            if not path:
                continue
                
            # Remove leading './' if present
            normalized_path = path[2:] if path.startswith('./') else path
            
            # Check if the normalized path exists
            if os.path.exists(normalized_path):
                result.append(normalized_path)
            else:
                # If normalized path doesn't exist, try the original path
                if os.path.exists(path):
                    result.append(path)
                else:
                    print(f"Warning: Path not found: {path}")
        
        if not result:
            print(f"Error: Path not found: {input_files_str}")
            print(f"Current working directory: {os.getcwd()}")
            parent_dir = os.path.dirname(input_files_str.split()[0] if input_files_str.split() else '.')
            print(f"Parent directory does not exist: {input_files_str}")
            
        return result
    
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
                
                # Flexible path replacement based on user configuration
                input_path_str = str(input_path_obj)
                
                # Extract the wildcard pattern from the output format
                # This helps us understand what part of the path should be preserved
                wildcard_pattern = output_format.split('**', 1)[1] if '**' in output_format else ''
                
                # Determine if we're dealing with a language substitution pattern
                # by analyzing both the input path and output format
                
                # For cases like 'docs/en/...' -> 'docs/cn/...'
                # or 'content/english/...' -> 'content/spanish/...'
                if '/' in input_path_str:
                    # Get the directory structure from the base directory
                    base_dir_clean = base_dir.rstrip('/')
                    
                    # Analyze the input path to find the appropriate split point
                    # We need to determine which part of the input path to keep
                    input_parts = input_path_str.split('/')
                    
                    # If the base_dir has a specific structure (e.g., 'docs/cn/'),
                    # try to match it with the input path structure
                    if '/' in base_dir_clean:
                        base_parts = base_dir_clean.split('/')
                        
                        # Find the common structure between input and output paths
                        common_parts = []
                        for i, part in enumerate(base_parts):
                            if i < len(input_parts) and input_parts[i] == part:
                                common_parts.append(part)
                            else:
                                break
                        
                        # If we found a common structure, use it to determine where to split
                        if common_parts:
                            # The number of common path components
                            common_length = len(common_parts)
                            
                            # Skip one more component after the common prefix (typically the language code)
                            # but make sure we don't go out of bounds
                            skip_length = common_length + 1 if common_length + 1 < len(input_parts) else common_length
                            
                            # Extract the relative path after the language code
                            relative_path = '/'.join(input_parts[skip_length:])
                            output_path = Path(f"{base_dir_clean}/{relative_path}")
                        else:
                            # No common structure found, use a more generic approach
                            # Just keep the filename or the path after the first directory
                            if len(input_parts) > 2:
                                # Skip the first two components (typically 'docs/lang/')
                                relative_path = '/'.join(input_parts[2:])
                                output_path = Path(f"{base_dir_clean}/{relative_path}")
                            else:
                                # Just use the filename
                                output_path = Path(base_dir_clean) / input_path_obj.name
                    else:
                        # Simple base directory without structure
                        # Just keep everything after the first component
                        if len(input_parts) > 1:
                            relative_path = '/'.join(input_parts[1:])
                            output_path = Path(f"{base_dir_clean}/{relative_path}")
                        else:
                            output_path = Path(base_dir_clean) / input_path_obj.name
                else:
                    # Simple case - just use the filename
                    output_path = Path(base_dir) / input_path_obj.name
                
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
