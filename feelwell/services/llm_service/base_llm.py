"""Base LLM interface and implementations.

Provides abstract base class and concrete implementations for different
LLM providers (HuggingFace, OpenAI, AWS Bedrock, etc.).
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    AWS_BEDROCK = "aws_bedrock"
    AWS_SAGEMAKER = "aws_sagemaker"
    LOCAL = "local"


@dataclass
class LLMConfig:
    """Configuration for LLM inference."""
    provider: LLMProvider
    model_name: str
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    timeout_seconds: int = 30


@dataclass
class LLMResponse:
    """Response from LLM inference."""
    text: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    metadata: Optional[Dict] = None


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""
    
    def __init__(self, config: LLMConfig):
        """Initialize LLM with configuration.
        
        Args:
            config: LLM configuration
        """
        self.config = config
        logger.info(
            "LLM initialized",
            extra={
                "provider": config.provider.value,
                "model": config.model_name
            }
        )
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response from LLM.
        
        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object
            
        Raises:
            TimeoutError: If inference exceeds timeout
            ValueError: If prompt is invalid
        """
        pass
    
    @abstractmethod
    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> List[LLMResponse]:
        """Generate responses for multiple prompts (batched).
        
        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of LLMResponse objects
        """
        pass
    
    def validate_prompt(self, prompt: str) -> bool:
        """Validate prompt before sending to LLM.
        
        Args:
            prompt: The prompt to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not prompt or not prompt.strip():
            logger.warning("Empty prompt provided")
            return False
        
        if len(prompt) > 10000:  # Reasonable limit
            logger.warning(
                "Prompt exceeds maximum length",
                extra={"length": len(prompt)}
            )
            return False
        
        return True


class HuggingFaceLLM(BaseLLM):
    """HuggingFace model implementation."""
    
    def __init__(self, config: LLMConfig):
        """Initialize HuggingFace LLM.
        
        Args:
            config: LLM configuration with HuggingFace endpoint
        """
        super().__init__(config)
        
        if not config.endpoint:
            raise ValueError("HuggingFace endpoint required")
        
        self.endpoint = config.endpoint
        self.headers = {}
        
        if config.api_key:
            self.headers["Authorization"] = f"Bearer {config.api_key}"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using HuggingFace Inference API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse object
        """
        import aiohttp
        import time
        
        if not self.validate_prompt(prompt):
            raise ValueError("Invalid prompt")
        
        # Format prompt with system context
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "return_full_text": False
            }
        }
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract generated text
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get("generated_text", "")
            else:
                generated_text = result.get("generated_text", "")
            
            logger.info(
                "LLM generation successful",
                extra={
                    "model": self.config.model_name,
                    "latency_ms": latency_ms
                }
            )
            
            return LLMResponse(
                text=generated_text,
                model=self.config.model_name,
                provider=self.config.provider.value,
                latency_ms=latency_ms,
                metadata={"endpoint": self.endpoint}
            )
            
        except Exception as e:
            logger.error(
                "LLM generation failed",
                extra={
                    "model": self.config.model_name,
                    "error": str(e)
                }
            )
            raise
    
    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> List[LLMResponse]:
        """Generate responses for multiple prompts.
        
        Args:
            prompts: List of prompts
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
            
        Returns:
            List of LLMResponse objects
        """
        import asyncio
        
        tasks = [
            self.generate(prompt, system_prompt, **kwargs)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)


class OpenAILLM(BaseLLM):
    """OpenAI API implementation (GPT-4, etc.)."""
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI LLM.
        
        Args:
            config: LLM configuration with API key
        """
        super().__init__(config)
        
        if not config.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=config.api_key)
        except ImportError:
            raise ImportError("openai package required: pip install openai")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using OpenAI API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse object
        """
        import time
        
        if not self.validate_prompt(prompt):
            raise ValueError("Invalid prompt")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        start_time = time.time()
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                timeout=self.config.timeout_seconds
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            generated_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            logger.info(
                "OpenAI generation successful",
                extra={
                    "model": self.config.model_name,
                    "latency_ms": latency_ms,
                    "tokens_used": tokens_used
                }
            )
            
            return LLMResponse(
                text=generated_text,
                model=self.config.model_name,
                provider=self.config.provider.value,
                tokens_used=tokens_used,
                latency_ms=latency_ms
            )
            
        except Exception as e:
            logger.error(
                "OpenAI generation failed",
                extra={
                    "model": self.config.model_name,
                    "error": str(e)
                }
            )
            raise
    
    async def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> List[LLMResponse]:
        """Generate responses for multiple prompts.
        
        Args:
            prompts: List of prompts
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
            
        Returns:
            List of LLMResponse objects
        """
        import asyncio
        
        tasks = [
            self.generate(prompt, system_prompt, **kwargs)
            for prompt in prompts
        ]
        
        return await asyncio.gather(*tasks)


def create_llm(config: LLMConfig) -> BaseLLM:
    """Factory function to create LLM instance.
    
    Args:
        config: LLM configuration
        
    Returns:
        BaseLLM instance
        
    Raises:
        ValueError: If provider not supported
    """
    if config.provider == LLMProvider.HUGGINGFACE:
        return HuggingFaceLLM(config)
    elif config.provider == LLMProvider.OPENAI:
        return OpenAILLM(config)
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")
