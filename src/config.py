#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class Config:
    """Configuration management for translation workflow"""
    # Required settings with default None for type hinting
    api_key: str = field(default_factory=lambda: Config._get_required_env('API_KEY'))
    input_files: str = field(default_factory=lambda: Config._get_required_env('INPUT_FILES'))
    output_files: str = field(default_factory=lambda: Config._get_required_env('OUTPUT_FILES'))
    
    # Optional settings with defaults
    base_url: str = field(default_factory=lambda: os.getenv('BASE_URL', 'https://openrouter.ai/api/v1'))
    ai_model: str = field(default_factory=lambda: os.getenv('AI_MODEL', 'gpt-4'))
    target_lang: str = field(default_factory=lambda: os.getenv('TARGET_LANG', 'Simplified-Chinese'))
    temperature: float = field(default_factory=lambda: float(os.getenv('TEMPERATURE', '0.3')))
    pr_title: str = field(default_factory=lambda: os.getenv('PR_TITLE', 'Add LLM Translations V3'))
    
    # Refinement settings
    refine_enabled: bool = field(default_factory=lambda: os.getenv('REFINE_ENABLED', 'true').lower() == 'true')
    refine_ai_model: str = field(init=False)
    refine_temperature: float = field(init=False)
    
    # Prompts
    system_prompt: str = field(default_factory=lambda: Config._read_prompt('SYSTEM_PROMPT'))
    prompt: str = field(default_factory=lambda: Config._read_prompt('PROMPT'))
    refine_system_prompt: str = field(default_factory=lambda: Config._read_prompt('REFINE_SYSTEM_PROMPT'))
    refine_prompt: str = field(default_factory=lambda: Config._read_prompt('REFINE_PROMPT'))
    
    def __post_init__(self):
        """Initialize fields that depend on other fields"""
        self.refine_ai_model = os.getenv('REFINE_AI_MODEL', self.ai_model)
        self.refine_temperature = float(os.getenv('REFINE_TEMPERATURE', str(self.temperature)))
    
    @staticmethod
    def _get_required_env(name: str) -> str:
        """Get a required environment variable or exit if not found"""
        if not (value := os.getenv(name, '')):
            print(f'ERROR: {name} environment variable is required')
            sys.exit(1)
        return value
    
    @staticmethod
    def _read_prompt(env_name: str) -> str:
        """Read prompt from environment variable or file"""
        prompt_text = os.getenv(env_name, '')
        prompt_path = Path(prompt_text)
        
        # If the prompt text is a valid file path, read from file
        if prompt_path.is_file():
            try:
                return prompt_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not read prompt from file {prompt_text}: {e}")
                return prompt_text
        return prompt_text
    

    
    def print_config(self) -> None:
        """Print current configuration"""
        print("\n=== Configuration ===")
        print(f"API Key: {'*' * 8}{self.api_key[-4:] if len(self.api_key) > 4 else ''}")
        print(f"Base URL: {self.base_url}")
        print(f"AI Model: {self.ai_model}")
        print(f"Target Language: {self.target_lang}")
        print(f"Temperature: {self.temperature}")
        print(f"Input Files: {self.input_files}")
        print(f"Output Files: {self.output_files}")
        print(f"PR Title: {self.pr_title}")
        print(f"Refinement Enabled: {self.refine_enabled}")
        
        if self.refine_enabled:
            print(f"Refinement AI Model: {self.refine_ai_model}")
            print(f"Refinement Temperature: {self.refine_temperature}")
        
        print("====================\n")
