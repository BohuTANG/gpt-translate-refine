#!/usr/bin/env python3

import difflib
from functools import lru_cache
from typing import Optional, List, Dict, Any
from openai import OpenAI


class Translator:
    """Handles interactions with AI translation services using OpenAI API"""
    
    def __init__(self, config):
        """Initialize translator with configuration"""
        self.config = config
        self.client = self._create_openai_client()
        
        # Statistics tracking
        self.input_tokens = 0
        self.output_tokens = 0
        self.api_calls = 0
    
    def _create_openai_client(self) -> OpenAI:
        """Create and configure OpenAI client"""
        return OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url if self.config.base_url else None
        )
    
    def call_openai(self, 
                    model: str, 
                    user_prompt: str, 
                    system_prompt: Optional[str] = None, 
                    temperature: Optional[float] = None) -> str:
        """Call OpenAI API with the specified model and prompts"""
        try:
            # Use default temperature if none provided
            temperature = temperature or self.config.temperature
            
            # Build messages list
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            
            # Make API call
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            
            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.input_tokens += response.usage.prompt_tokens
                self.output_tokens += response.usage.completion_tokens
            
            # Increment API call counter
            self.api_calls += 1
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return ""
    
    def translate(self, text: str) -> str:
        """Translate text using OpenAI"""
        # Prepare prompts
        system_prompt = self.config.system_prompt or None
        user_prompt = f"{self.config.prompt}\n\n{text}" if self.config.prompt else text
        
        print(f"Translating with model: {self.config.ai_model}...")
        result = self.call_openai(
            model=self.config.ai_model, 
            user_prompt=user_prompt, 
            system_prompt=system_prompt, 
            temperature=self.config.temperature
        )
        
        return result
    
    def refine(self, translated_text: str, original_text: Optional[str] = None) -> str:
        """Refine the translated text using OpenAI"""
        if not self.config.refine_enabled:
            return translated_text
        
        # Prepare prompts
        system_prompt = self.config.refine_system_prompt or None
        
        # Build user prompt based on available inputs
        if self.config.refine_prompt:
            user_prompt = f"{self.config.refine_prompt}\n\n"
            if original_text:
                user_prompt += f"Original text:\n{original_text}\n\nTranslated text to refine:\n{translated_text}"
            else:
                user_prompt += translated_text
        elif original_text:
            user_prompt = f"Original text:\n{original_text}\n\nTranslated text to refine:\n{translated_text}"
        else:
            user_prompt = translated_text
        
        print(f"Refining translation with model: {self.config.refine_ai_model}...")
        result = self.call_openai(
            model=self.config.refine_ai_model, 
            user_prompt=user_prompt, 
            system_prompt=system_prompt, 
            temperature=self.config.refine_temperature
        )
        
        return result


    def get_statistics(self) -> dict:
        """Get token usage statistics"""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "api_calls": self.api_calls
        }


class TextUtils:
    """Utility functions for text processing"""
    
    @staticmethod
    def show_diff(text1: str, text2: str) -> None:
        """Show differences between two texts using colored diff output"""
        # Split texts into lines
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            lines1, 
            lines2,
            fromfile='Original Translation',
            tofile='Refined Translation',
            lineterm=''
        ))
        
        # Print diff if there are differences
        if diff_lines:
            print("\n=== Translation Differences ===\n")
            for line in diff_lines:
                print(line)
            print("\n=============================\n")
        else:
            print("No differences found between original and refined translations.")
