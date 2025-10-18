# scraper.py
import os
import html
import argparse
import subprocess
import concurrent.futures
import requests
import sys
from tqdm import tqdm
from pathlib import Path
import urllib.parse
import logging

# Try to import the new captioning utility, but don't make it a hard requirement
try:
    from utils.caption_utils import generate_captions
except ImportError:
    generate_captions = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")

def build_gallery_dl_args(config):
    """Builds a list of command-line arguments from a config dictionary."""
    args = []
    for key, value in config.items():
        if value is None:
            continue
        # For boolean flags that are true, just add the flag itself (e.g., --get-urls)
        if isinstance(value, bool) and value:
            args.append(f"--{key}")
        # For string values, add the flag and its value as separate items in the list
        elif isinstance(value, str) and value:
            args.append(f"--{key}")
            args.append(str(value)) # Ensure value is a string
    return args

def download_worker(url, output_dir, session):
    """Worker function to download a single file."""
    try:
        # It's good practice to stream large responses
        with session.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            # Extract filename from URL
            filename = url.split('/')[-1].split('?')[0]
            if not filename:
                # Fallback if URL ends in a slash or has no clear filename
                filename = f"download_{url.split('/')[-2]}"
            
            file_path = output_dir / filename
            
            # Get total file size for the progress bar
            total_size = int(r.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f:
                # Use a dummy tqdm progress bar for the file itself (optional)
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return url, True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download {url}: {e}")
        return url, False

def pre_process_tags(directory):
    """Recursively finds and cleans tag files in a directory."""
    root_dir = Path(directory)
    try:
        # Use rglob to find all .txt files recursively
        for txt_file in root_dir.rglob("*.txt"):
            # gallery-dl sometimes creates tags as `file.ext.txt`.
            # We want to rename it to `image.txt`.
            if txt_file.stem.endswith(('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.webm', '.mkv')):
                # Correct path: image.txt
                new_path = txt_file.with_name(Path(txt_file.stem).stem + ".txt")
                try:
                    # If new_path already exists, we might be re-running. Skip rename.
                    if not new_path.exists():
                        txt_file.rename(new_path)
                    current_file = new_path
                except OSError as e:
                    print(f"  - Warning: Could not rename {txt_file.name} to {new_path.name}: {e}")
                    continue # Skip processing this file if rename fails
            else:
                current_file = txt_file
            
            with open(current_file, "r+", encoding='utf-8') as f:
                    contents = f.read()
                    # Process tags: unescape HTML, replace underscores, join lines
                    processed_contents = html.unescape(contents)
                    processed_contents = processed_contents.replace("_", " ")
                    processed_contents = ", ".join(tag for tag in processed_contents.splitlines() if tag)
                    
                    # Go back to the start of the file and overwrite
                    f.seek(0)
                    f.write(processed_contents)
                    f.truncate()
    except Exception as e:
        print(f"[ERROR] An error occurred during tag processing: {e}")


def main():
    """Main function to parse arguments and run the scraper."""
    parser = argparse.ArgumentParser(
        description="A general-purpose image scraper using gallery-dl.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # --- Argument Definitions ---
    parser.add_argument("scrape_url", help="The full URL to scrape from (e.g., a gallery or search result page).")
    
    parser.add_argument("-k", "--keywords",
                        help="Comma-separated keywords to search for. Used to format the scrape_url if it contains a '{}' placeholder.")

    parser.add_argument("--keyword-join-char", default="+",
                        help="Character to join keywords with for the URL (e.g., '+', '%%20').")

    parser.add_argument("-o", "--output-directory", default="./scraped_images",
                        help="Full path for the output directory. Will be created if it doesn't exist.")
                        
    parser.add_argument("-r", "--download-range",
                        help='Limit the number of images to download (e.g., "1-200").')
                        
    parser.add_argument("--no-tags", action="store_false", dest="write_tags",
                        help="Disable saving of metadata/tags to a .txt file.")
                        
    parser.add_argument("--no-fast-download", action="store_true",
                        help="Use the standard, single-threaded gallery-dl downloader instead of the custom multi-threaded one.")

    parser.add_argument("--additional-args", default="--filename /O --no-part",
                        help='Pass any other arguments directly to gallery-dl (e.g., --filter "...").')

    parser.add_argument("--user-agent", default="gdl/1.24.5", help="Set the User-Agent for requests.")

    parser.add_argument("-c", "--cookies", help="Path to a Netscape format cookies file to use for authentication.")

    parser.add_argument("--cookies-from-browser", help="Browser to extract cookies from (e.g., chrome, edge).")

    parser.add_argument("--autocaption", action="store_true",
                        help="Enable automatic captioning for images with missing tags.")
    
    parser.add_argument("--is-tagger", action="store_true",
                        help="Specify if the caption model is a tagger to format output correctly.")
    
    parser.add_argument("--max-threads", type=int, default=8,
                        help="Maximum number of concurrent download threads.")

    parser.add_argument("--videos", action="store_true",
                        help="Optimize for video downloads. Disables fast download and auto-captioning by default.")
    
    args = parser.parse_args()

    # Determine if fast download should be used
    fast_download = not args.no_fast_download and not args.videos

    # --- Add optional gallery-dl arguments ---
    additional_args_list = args.additional_args.split()
    if args.cookies:
        additional_args_list.extend(["--cookies", args.cookies])
    if args.cookies_from_browser:
        additional_args_list.extend(["--cookies-from-browser", args.cookies_from_browser])

    # --- Scraper Logic ---
    image_dir = Path(args.output_directory)
    image_dir.mkdir(parents=True, exist_ok=True)

    final_scrape_url = args.scrape_url
    if args.keywords and "{}" in args.scrape_url:
        # Process keywords: split by comma, strip whitespace, URL-encode, and join with '+'
        # This is a common format for many image board search queries.
        # Using '%20' for spaces is more universally compatible.
        processed_keywords = args.keyword_join_char.join([urllib.parse.quote(k.strip()) for k in args.keywords.split(',')])
        final_scrape_url = args.scrape_url.format(processed_keywords)
        print(f"[INFO] Formatted keywords into URL.")
    elif args.keywords:
        print("[WARNING] Keywords were provided, but the scrape_url does not contain a '{}' placeholder. The keywords will be ignored.")

    print(f"[INFO] Starting scrape for URL: {final_scrape_url}")
    print(f"[INFO] Saving files to: {image_dir.resolve()}")

    try:
        if fast_download:
            logging.info("[INFO] Using fast downloader (Python multi-threaded)...")
            get_url_config = {
                "get-urls": True,
                "range": args.download_range,
                "user-agent": args.user_agent
            }
            gdl_args = build_gallery_dl_args(get_url_config)
            command = [sys.executable, "-m", "gallery_dl", final_scrape_url, *gdl_args, *additional_args_list]
            
            logging.info(f"Step 1: Fetching image URLs with gallery-dl... Command: {' '.join(command)}") # For display only
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', shell=False)
            urls = [url for url in result.stdout.splitlines() if url.strip()]
            logging.info(f"Step 2: Found {len(urls)} URLs. Starting parallel download...")

            # Use a thread pool to download files concurrently
            with requests.Session() as session:
                # Use a ThreadPoolExecutor for concurrent downloads
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                    # Create a future for each download
                    future_to_url = {executor.submit(download_worker, url, image_dir, session): url for url in urls}
                    # Use tqdm for a nice progress bar
                    for future in tqdm(concurrent.futures.as_completed(future_to_url), total=len(urls), desc="Downloading"):
                        future.result() # We can check result if needed

        else:
            print("[INFO] Using standard downloader (gallery-dl)...")
            scrape_config = {
                "directory": str(image_dir.resolve()),
                "write-tags": args.write_tags,
                "range": args.download_range,
                "user-agent": args.user_agent
            }
            gdl_args = build_gallery_dl_args(scrape_config)
            command = [sys.executable, "-m", "gallery_dl", final_scrape_url, *gdl_args, *additional_args_list]
            logging.info(f"Executing command: {' '.join(command)}")
            subprocess.run(command, check=True, shell=False) # Explicitly set shell=False
        
        print("[SUCCESS] Scrape command finished.")

        if args.write_tags:
            logging.info("\n[INFO] Processing downloaded tags...")
            pre_process_tags(str(image_dir.resolve()))
            logging.info("[SUCCESS] Tag processing complete.")

        # --- Auto-Captioning Logic ---
        if args.autocaption and not args.videos:
            if generate_captions:
                logging.info(f"\n[INFO] Running auto-captioner for images with missing or empty tags...")
                generate_captions(str(image_dir.resolve()), is_tagger=args.is_tagger)
            else:
                logging.error("\n[ERROR] Could not run auto-captioning. `caption_utils.py` not found or `transformers` is not installed.")

    except FileNotFoundError:
        logging.error("[ERROR] 'gallery-dl' not found. Please ensure it is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr or "No stderr output."
        print(f"[ERROR] An error occurred while running an external command:\n--- STDERR ---\n{stderr_output}")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
