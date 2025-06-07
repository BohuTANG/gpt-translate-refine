#!/usr/bin/env python3

import difflib
from typing import Optional, Dict
from openai import OpenAI


class Translator:
    """Handles AI translation services using OpenAI API"""
    
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url if config.base_url else None
        )
        
        # Statistics
        self.input_tokens = 0
        self.output_tokens = 0
        self.api_calls = 0
    
    def call_openai(self, model: str, user_prompt: str, 
                   system_prompt: Optional[str] = None, 
                   temperature: Optional[float] = None) -> str:
        """Call OpenAI API"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature or self.config.temperature
            )
            
            # Track usage
            if hasattr(response, 'usage') and response.usage:
                self.input_tokens += response.usage.prompt_tokens
                self.output_tokens += response.usage.completion_tokens
            
            self.api_calls += 1
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return ""
    
    def translate(self, text: str) -> str:
        """Translate text using OpenAI"""
        system_prompt = self.config.system_prompt or None
        user_prompt = f"{self.config.prompt}\n\n{text}" if self.config.prompt else text
        
        print(f"Translating with model: {self.config.ai_model}...")
        return self.call_openai(
            model=self.config.ai_model,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=self.config.temperature
        )
    
    def refine(self, translated_text: str, original_text: Optional[str] = None) -> str:
        """Refine translated text"""
        if not self.config.refine_enabled:
            return translated_text
        
        system_prompt = self.config.refine_system_prompt or None
        
        # Build user prompt
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
        
        return result if result else translated_text
    
    def get_statistics(self) -> Dict[str, int]:
        """Get token usage statistics"""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "api_calls": self.api_calls
        }


class TextUtils:
    """Text processing utilities"""
    
    @staticmethod
    def show_diff(text1: str, text2: str) -> None:
        """Show differences between two texts"""
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        diff_lines = list(difflib.unified_diff(
            lines1, lines2,
            fromfile='Original Translation',
            tofile='Refined Translation',
            lineterm=''
        ))
        
        if diff_lines:
            print("\n=== Translation Differences ===")
            for line in diff_lines:
                print(line)
            print("===============================\n")
        else:
            print("No differences found between translations.")
