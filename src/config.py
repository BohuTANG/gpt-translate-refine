#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Configuration management for translation workflow"""
    
    # Core settings
    api_key: str = field(default_factory=lambda: Config._env_required('API_KEY'))
    input_files: str = field(default_factory=lambda: Config._env_optional('INPUT_FILES', ''))
    output_files: str = field(default_factory=lambda: Config._env_required('OUTPUT_FILES'))
    
    # API settings
    base_url: str = field(default_factory=lambda: os.getenv('BASE_URL', 'https://openrouter.ai/api/v1').strip())
    ai_model: str = field(default_factory=lambda: os.getenv('AI_MODEL', 'gpt-4').strip())
    target_lang: str = field(default_factory=lambda: os.getenv('TARGET_LANG', 'Simplified-Chinese').strip())
    temperature: float = field(default_factory=lambda: float(os.getenv('TEMPERATURE', '0.3').strip()))
    pr_title: str = field(default_factory=lambda: os.getenv('PR_TITLE', 'Add LLM Translations V3').strip())
    
    # Refinement settings
    refine_enabled: bool = field(default_factory=lambda: os.getenv('REFINE_ENABLED', 'true').strip().lower() == 'true')
    refine_ai_model: str = field(init=False)
    refine_temperature: float = field(init=False)
    
    # Prompts
    system_prompt: str = field(default_factory=lambda: Config._read_prompt('SYSTEM_PROMPT'))
    prompt: str = field(default_factory=lambda: Config._read_prompt('PROMPT'))
    refine_system_prompt: str = field(default_factory=lambda: Config._read_prompt('REFINE_SYSTEM_PROMPT'))
    refine_prompt: str = field(default_factory=lambda: Config._read_prompt('REFINE_PROMPT'))
    
    def __post_init__(self):
        self.refine_ai_model = os.getenv('REFINE_AI_MODEL', self.ai_model).strip()
        self.refine_temperature = float(os.getenv('REFINE_TEMPERATURE', str(self.temperature)).strip())
    
    @staticmethod
    def _env_required(name: str) -> str:
        if not (value := os.getenv(name, '')):
            print(f'ERROR: {name} environment variable is required')
            sys.exit(1)
        return value.strip()
        
    @staticmethod
    def _env_optional(name: str, default: str = '') -> str:
        return os.getenv(name, default).strip()
    
    @staticmethod
    def _read_prompt(env_name: str) -> str:
        prompt_text = os.getenv(env_name, '').strip()
        if Path(prompt_text).is_file():
            try:
                return Path(prompt_text).read_text(encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not read prompt from file {prompt_text}: {e}")
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
