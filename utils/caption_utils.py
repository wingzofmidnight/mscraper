# caption_utils.py
import torch
from transformers import pipeline
import logging
from PIL import Image
from pathlib import Path
from tqdm import tqdm

def generate_captions(
    image_dir: str,
    batch_size: int = 8,
    is_tagger: bool = False,
):
    """
    Generates captions for images in a directory that are missing them.

    Args:
        image_dir (str): The path to the directory containing images.
        batch_size (int): The number of images to process at once.
    """
    image_dir = Path(image_dir)
    if not image_dir.is_dir():
        logging.error(f"Directory not found at '{image_dir}'")
        return

    model_id = "Salesforce/blip-image-captioning-base"

    # Determine the device to use (GPU if available, otherwise CPU)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logging.info(f"Using device: {device}")

    # For GPU, use float16 for a significant speedup
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    try:
        # Initialize the image-to-text pipeline
        captioner = pipeline(
            "image-to-text",
            model=model_id,
            device=device,
            torch_dtype=torch_dtype
        )
    except Exception as e:
        logging.error(f"Error initializing model '{model_id}': {e}")
        logging.error("Please ensure you have run 'pip install -r requirements.txt'.")
        return

    # Find images that need a caption
    images_to_caption = []
    for item in image_dir.iterdir():
        if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
            caption_file = item.with_suffix('.txt')
            if not caption_file.exists() or caption_file.stat().st_size == 0:
                images_to_caption.append(item)

    if not images_to_caption:
        logging.info("   No images needed captioning. All tags are present.")
        return

    logging.info(f"   Found {len(images_to_caption)} images to caption with model '{model_id}'.")

    # Process images in batches for efficiency
    for i in tqdm(range(0, len(images_to_caption), batch_size), desc="Captioning images"):
        batch_paths = images_to_caption[i:i + batch_size]
        batch_images = [Image.open(p).convert("RGB") for p in batch_paths]
        
        generated_outputs = captioner(batch_images)

        for path, outputs in zip(batch_paths, generated_outputs):
            # The output format can vary; we robustly handle lists of dicts
            caption_text = outputs[0]['generated_text'] if isinstance(outputs, list) else outputs['generated_text']
            
            # If it's a tagger, format the output nicely
            if is_tagger:
                caption_text = ", ".join(caption_text.split(','))

            caption_file = path.with_suffix('.txt')
            caption_file.write_text(caption_text.strip(), encoding='utf-8')
