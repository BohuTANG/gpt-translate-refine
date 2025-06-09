#!/usr/bin/env python3

import os
import re
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


class FileProcessor:
    """Handles file operations for translation workflow"""
    
    def __init__(self, config):
        self.config = config
    
    def get_input_files(self) -> List[str]:
        """Parse and normalize input file paths"""
        if not self.config.input_files:
            return []
        
        input_str = self.config.input_files
        
        # Skip single path check to always process as a list of paths
        # This ensures space-separated paths are always handled properly
        
        # Multiple paths processing
        result = []
        # Debug information
        print(f"Debug: Processing input files: '{input_str}'")
        print(f"Debug: Current working directory: {os.getcwd()}")
        
        # List directory contents to help diagnose issues
        print("Debug: Directory contents:")
        try:
            print("\n".join(f"  - {f}" for f in os.listdir(os.getcwd())))
        except Exception as e:
            print(f"  Error listing directory: {e}")
            
        for path in input_str.split():
            if not (path := path.strip()):
                continue
                
            # Normalize path by removing leading './' if present
            normalized = path[2:] if path.startswith('./') else path
            
            print(f"Debug: Checking path: '{path}' (normalized: '{normalized}')")
            
            # Try both original and normalized paths
            if os.path.exists(normalized):
                print(f"Debug: Found normalized path: {normalized}")
                result.append(normalized)
            elif os.path.exists(path):
                print(f"Debug: Found original path: {path}")
                result.append(path)
            else:
                # Try listing parent directory contents to help diagnose
                parent_dir = os.path.dirname(normalized) or '.'
                print(f"Warning: Path not found: {path}")
                print(f"Debug: Contents of parent directory '{parent_dir}':")
                try:
                    if os.path.exists(parent_dir):
                        print("\n".join(f"  - {f}" for f in os.listdir(parent_dir)))
                    else:
                        print(f"  Parent directory does not exist")
                except Exception as e:
                    print(f"  Error listing parent directory: {e}")
        
        if not result:
            print(f"Error: No valid paths found in: {input_str}")
            print(f"Current working directory: {os.getcwd()}")
            
        return result
    
    def get_output_path(self, input_path: str) -> str:
        """Generate output path based on input and pattern"""
        if not self.config.output_files or '*' not in self.config.output_files:
            return self.config.output_files
        
        input_path_obj = Path(input_path)
        output_format = self.config.output_files
        lang_code = self.config.target_lang.lower().replace(' ', '_').replace('-', '_')
        
        # Handle directory structure preservation
        if '**' in output_format:
            if base_match := re.match(r'^(.*?)\*\*', output_format):
                base_dir = base_match.group(1).rstrip('/')
                return self._handle_directory_structure(input_path_obj, base_dir, output_format)
        
        # Simple replacement
        return self._simple_replacement(input_path_obj, output_format, lang_code)
    
    def _handle_directory_structure(self, input_path: Path, base_dir: str, output_format: str) -> str:
        """Handle complex directory structure preservation"""
        input_parts = str(input_path).split('/')
        
        if '/' in base_dir:
            base_parts = base_dir.split('/')
            common_parts = []
            
            for i, part in enumerate(base_parts):
                if i < len(input_parts) and input_parts[i] == part:
                    common_parts.append(part)
                else:
                    break
            
            if common_parts:
                skip_length = min(len(common_parts) + 1, len(input_parts) - 1)
                relative_path = '/'.join(input_parts[skip_length:])
                return f"{base_dir}/{relative_path}"
        
        # Fallback: skip first directory component
        if len(input_parts) > 1:
            relative_path = '/'.join(input_parts[1:])
            return f"{base_dir}/{relative_path}"
        
        return str(Path(base_dir) / input_path.name)
    
    def _simple_replacement(self, input_path: Path, output_format: str, lang_code: str) -> str:
        """Handle simple pattern replacement"""
        replacements = {
            '*': input_path.name,
            '{name}': input_path.stem,
            '{ext}': input_path.suffix[1:] if input_path.suffix.startswith('.') else input_path.suffix,
            '{lang}': lang_code
        }
        
        result = output_format
        for pattern, replacement in replacements.items():
            result = result.replace(pattern, replacement)
        
        return result
    
    def find_files_recursively(self, directory: str) -> List[str]:
        """Find all files in directory recursively"""
        return [str(path) for path in Path(directory).rglob('*') if path.is_file()]
    
    def read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            return Path(file_path).read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Write content to file"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Error writing to file {file_path}: {e}")
            return False
    
    @staticmethod
    def extract_yaml_and_content(text: str) -> Tuple[Optional[Dict[str, Any]], str, bool]:
        """Extract YAML frontmatter and content"""
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
        """Reconstruct Markdown with YAML frontmatter"""
        if not has_frontmatter or yaml_data is None:
            return content
        
        try:
            yaml_text = yaml.dump(yaml_data, allow_unicode=True, sort_keys=False)
            return f"---\n{yaml_text}---\n\n{content}"
        except Exception as e:
            print(f"Error reconstructing Markdown: {e}")
            return content
