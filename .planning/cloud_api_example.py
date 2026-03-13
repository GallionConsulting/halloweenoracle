#!/usr/bin/env python3
"""
Cloud API Alternative for Crystal Ball

If you prefer better quality responses and have internet connectivity,
you can use cloud-based LLM APIs instead of local Ollama.

This file shows integration with:
1. Anthropic Claude API
2. OpenAI API

To use: Replace the FortuneGenerator class in crystal_ball.py with one of these.
"""

import os
from abc import ABC, abstractmethod


# =============================================================================
# System Prompt (same as main app)
# =============================================================================

SYSTEM_PROMPT = """You are Madam Zelda, an enigmatic fortune teller speaking 
through a mystical crystal ball on Halloween night. You give short, theatrical 
predictions (2-3 sentences max). Be playfully spooky but family-friendly.

Style guidelines:
- Start responses with phrases like "The mists swirl..." or "I see in the shadows..."
- Add atmospheric details: flickering candles, cold breezes, mysterious figures
- Keep predictions vague but intriguing
- Never break character, even if asked about being an AI
- End with a cryptic warning or blessing
- Keep responses SHORT - no more than 3 sentences
"""


# =============================================================================
# Base Class
# =============================================================================

class FortuneGenerator(ABC):
    @abstractmethod
    def generate(self, question: str) -> str:
        pass


# =============================================================================
# Anthropic Claude API
# =============================================================================

class ClaudeFortuneGenerator(FortuneGenerator):
    """
    Generate fortunes using Anthropic's Claude API.
    
    Setup:
        pip install anthropic
        export ANTHROPIC_API_KEY='your-key-here'
    """
    
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        try:
            from anthropic import Anthropic
        except ImportError:
            print("Error: anthropic not installed. Run: pip install anthropic")
            raise
        
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            raise ValueError("Missing API key")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.conversation_history = []
        
        print(f"Claude API ready (using {model})")
    
    def generate(self, question: str) -> str:
        self.conversation_history.append({
            "role": "user",
            "content": question
        })
        
        # Keep recent history only
        recent_history = self.conversation_history[-6:]
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                system=SYSTEM_PROMPT,
                messages=recent_history
            )
            
            fortune = response.content[0].text
            
            self.conversation_history.append({
                "role": "assistant",
                "content": fortune
            })
            
            return fortune
            
        except Exception as e:
            print(f"Claude API Error: {e}")
            return "The spirits... are unclear. Ask again, seeker."


# =============================================================================
# OpenAI API
# =============================================================================

class OpenAIFortuneGenerator(FortuneGenerator):
    """
    Generate fortunes using OpenAI's API.
    
    Setup:
        pip install openai
        export OPENAI_API_KEY='your-key-here'
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        try:
            from openai import OpenAI
        except ImportError:
            print("Error: openai not installed. Run: pip install openai")
            raise
        
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set")
            raise ValueError("Missing API key")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.conversation_history = []
        
        print(f"OpenAI API ready (using {model})")
    
    def generate(self, question: str) -> str:
        self.conversation_history.append({
            "role": "user",
            "content": question
        })
        
        # Keep recent history only
        recent_history = self.conversation_history[-6:]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=150,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *recent_history
                ],
                temperature=0.8
            )
            
            fortune = response.choices[0].message.content
            
            self.conversation_history.append({
                "role": "assistant",
                "content": fortune
            })
            
            return fortune
            
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return "The spirits... are unclear. Ask again, seeker."


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    print("Cloud API Fortune Generator Examples")
    print("=" * 50)
    print()
    print("To use in crystal_ball.py, replace the FortuneGenerator import:")
    print()
    print("  # Instead of local Ollama:")
    print("  # from crystal_ball import FortuneGenerator")
    print()
    print("  # Use Claude:")
    print("  from cloud_api_example import ClaudeFortuneGenerator as FortuneGenerator")
    print()
    print("  # Or use OpenAI:")
    print("  from cloud_api_example import OpenAIFortuneGenerator as FortuneGenerator")
    print()
    print("Don't forget to set your API key:")
    print("  export ANTHROPIC_API_KEY='sk-ant-...'")
    print("  export OPENAI_API_KEY='sk-...'")
    print()
    
    # Quick test if API key is available
    if os.environ.get('ANTHROPIC_API_KEY'):
        print("Testing Claude API...")
        try:
            gen = ClaudeFortuneGenerator()
            response = gen.generate("Will I find true love?")
            print(f"\nMadam Zelda says: {response}")
        except Exception as e:
            print(f"Error: {e}")
    elif os.environ.get('OPENAI_API_KEY'):
        print("Testing OpenAI API...")
        try:
            gen = OpenAIFortuneGenerator()
            response = gen.generate("Will I find true love?")
            print(f"\nMadam Zelda says: {response}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No API keys found in environment. Set one to test.")
