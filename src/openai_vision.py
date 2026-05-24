#!/usr/bin/env python3
"""
OpenAI Vision Integration for Duck-Vision
Gir dyp scene-forståelse ved å sende bilder til GPT-4 Vision API
"""

import base64
import os
import logging
from typing import Optional
from pathlib import Path
import io
from PIL import Image
import requests

logger = logging.getLogger(__name__)


class OpenAIVision:
    """
    OpenAI Vision API integration.
    Tar bilder fra kamera og sender til GPT-4 Vision for dyp forståelse.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialiserer OpenAI Vision klient.
        
        Args:
            api_key: OpenAI API key (hentes fra env hvis None)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY ikke funnet i environment")
        
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"  # Bedre på gjenkjenning av objekter og detaljer
        
        logger.info(f"OpenAI Vision initialisert (model: {self.model})")
    
    def encode_image(self, image_path: Path) -> str:
        """
        Encoder bilde til base64 string.
        
        Args:
            image_path: Sti til bildefil
            
        Returns:
            Base64-encodet bilde
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def encode_pil_image(self, pil_image: Image.Image, format: str = "JPEG", quality: int = 85) -> str:
        """
        Encoder PIL Image til base64.
        
        Args:
            pil_image: PIL Image objekt
            format: Bildeformat (JPEG/PNG)
            quality: JPEG kvalitet (1-100)
            
        Returns:
            Base64-encodet bilde
        """
        # Resize hvis for stort (OpenAI Vision trenger ikke full oppløsning)
        max_size = 1024  # Større for bedre detaljer
        if max(pil_image.size) > max_size:
            ratio = max_size / max(pil_image.size)
            new_size = tuple(int(dim * ratio) for dim in pil_image.size)
            pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug(f"Resized image to {new_size} for faster processing")
        
        buffer = io.BytesIO()
        pil_image.save(buffer, format=format, quality=quality)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def analyze_image(self, 
                     image_path: Optional[Path] = None,
                     pil_image: Optional[Image.Image] = None,
                     question: Optional[str] = None,
                     max_tokens: int = 800,
                     detail: str = "auto") -> dict:
        """
        Analyser bilde med OpenAI Vision API.
        
        Args:
            image_path: Sti til bildefil (eller bruk pil_image)
            pil_image: PIL Image objekt (eller bruk image_path)
            question: Spesifikt spørsmål om bildet (valgfritt)
            max_tokens: Maks tokens i respons
            
        Returns:
            Dict med 'success', 'description', 'error'
        """
        try:
            # Encoder bilde
            if pil_image:
                # Lagre bildet som sendes for debugging
                default_debug_path = Path(__file__).resolve().parents[1] / "data" / "logs" / "openai_vision_debug.jpg"
                debug_path = Path(os.getenv("OPENAI_VISION_DEBUG_PATH", str(default_debug_path)))
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                pil_image.save(debug_path, "JPEG", quality=85)
                logger.info(f"💾 Lagret debug-bilde: {debug_path} (størrelse: {pil_image.size})")
                
                base64_image = self.encode_pil_image(pil_image)
            elif image_path:
                base64_image = self.encode_image(image_path)
            else:
                return {
                    "success": False,
                    "error": "Må ha enten image_path eller pil_image"
                }
            
            # Standard prompt hvis ingen spørsmål
            if not question:
                prompt = (
                    "Beskriv dette bildet på norsk. "
                    "Fokuser på hva du ser av personer, objekter, aktiviteter og rommet generelt. "
                    "Vær grundig og detaljert. Beskriv farger, materialer, plassering, belysning og stemning."
                )
            else:
                prompt = f"Se på bildet og svar: {question}\n\nSvar på norsk."
            
            # API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": detail  # auto | low | high
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            logger.info(f"🤖 Sender bilde til OpenAI Vision API...")
            logger.debug(f"Base64 lengde: {len(base64_image)} bytes")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            description = result['choices'][0]['message']['content'].strip()
            
            logger.info(f"✓ OpenAI Vision full respons: {description}")
            logger.info(f"  Tokens: {result.get('usage', {})}")
            
            return {
                "success": True,
                "description": description,
                "model": self.model,
                "tokens_used": result.get('usage', {})
            }
            
        except requests.exceptions.Timeout:
            logger.error("OpenAI Vision API timeout (>30s)")
            return {
                "success": False,
                "error": "API timeout - tok for lang tid"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI Vision API error: {e}")
            return {
                "success": False,
                "error": f"API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Feil ved OpenAI Vision analyse: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def quick_question(self, pil_image: Image.Image, question: str) -> Optional[str]:
        """
        Rask spørsmål om et bilde.
        
        Args:
            pil_image: PIL Image objekt
            question: Spørsmål på norsk
            
        Returns:
            Svar som string, eller None hvis feil
        """
        result = self.analyze_image(pil_image=pil_image, question=question, max_tokens=400)
        if result["success"]:
            return result["description"]
        else:
            logger.error(f"OpenAI Vision feilet: {result.get('error')}")
            return None
