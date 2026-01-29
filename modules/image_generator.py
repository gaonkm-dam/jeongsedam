import os
import base64
from io import BytesIO
from typing import List, Tuple, Optional
from PIL import Image
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_images(
    prompt: str,
    size: str = "1024x1024",
    n: int = 1,
    quality: str = "standard"
) -> List[Tuple[Image.Image, bytes]]:
    """
    이미지 생성 함수
    
    Returns:
        List[Tuple[Image.Image, bytes]]: (PIL Image 객체, raw bytes) 튜플의 리스트
    """
    try:
        response = client.images.generate(
            model="dall-e-3" if n == 1 else "dall-e-2",
            prompt=prompt,
            size=size,
            n=n,
            quality=quality,
            response_format="b64_json"
        )
        
        results = []
        for img_data in response.data:
            img_bytes = base64.b64decode(img_data.b64_json)
            img = Image.open(BytesIO(img_bytes)).convert("RGB")
            results.append((img, img_bytes))
        
        return results
        
    except Exception as e:
        print(f"Image generation error: {str(e)}")
        return []

def generate_policy_image(
    brief: dict,
    size: str = "1024x1024",
    quality: str = "standard"
) -> Optional[Tuple[Image.Image, bytes]]:
    """
    정책 이미지 생성 (brief 기반)
    """
    concept = brief.get("concept", "")
    scene = brief.get("scene_description", "")
    style = brief.get("visual_style", "")
    message = brief.get("key_message", "")
    
    prompt = f"""
Professional documentary photography style.

Concept: {concept}

Scene: {scene}

Visual Style: {style}

This image conveys: {message}

Requirements:
- Ultra-realistic, authentic South Korean setting
- Natural lighting, professional composition
- Real people in genuine situations
- No text, logos, or artificial elements
- Clean, modern aesthetic
- Natural color palette
"""
    
    results = generate_images(prompt, size=size, n=1, quality=quality)
    if results:
        return results[0]
    return None

def batch_generate_images(
    prompts: List[str],
    size: str = "1024x1024",
    quality: str = "standard"
) -> List[Tuple[Image.Image, bytes]]:
    """
    여러 이미지를 순차적으로 생성
    """
    all_results = []
    for prompt in prompts:
        results = generate_images(prompt, size=size, n=1, quality=quality)
        all_results.extend(results)
    return all_results

def create_thumbnail(image: Image.Image, max_size: Tuple[int, int] = (300, 300)) -> Image.Image:
    """
    썸네일 생성
    """
    img_copy = image.copy()
    img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img_copy

def images_to_bytes(images: List[Image.Image], format: str = "PNG") -> List[bytes]:
    """
    PIL Image를 bytes로 변환
    """
    results = []
    for img in images:
        buffer = BytesIO()
        img.save(buffer, format=format)
        results.append(buffer.getvalue())
    return results
