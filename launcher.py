# launcher.py
import subprocess
from pathlib import Path
import logging
import datetime
import sys


def get_user_input(prompt, default=None, required=False):
    """Gets user input with an optional default value and validation."""
    prompt_text = f"{prompt} [default: {default}]: " if default else f"{prompt}: "
    while True:
        user_input = input(prompt_text).strip()
        if user_input:
            return user_input
        if default is not None:
            return default
        if required:
            print("❌ This field is required.")
        else:
            return None


def get_default_output_from_url(url: str) -> str:
    """Generates a default directory name from a URL."""
    from urllib.parse import urlparse
    try:
        path_parts = [part for part in urlparse(url).path.split('/') if part]
        if path_parts:
            return path_parts[-1].replace(' ', '_')
    except Exception:
        pass
    return "scraped_media"

def get_choice_from_list(prompt, options, default_index=0):
    """Gets a valid choice from a list of options."""
    for i, option in enumerate(options):
        logging.info(f"  {i + 1}) {option}")

    while True:
        try:
            choice_str = get_user_input(prompt, default=str(default_index + 1), required=True)
            choice_idx = int(choice_str) - 1
            if 0 <= choice_idx < len(options):
                return options[choice_idx]
            else:
                logging.error(f"❌ Invalid choice. Please enter a number between 1 and {len(options)}.")
        except ValueError:
            logging.error("❌ Invalid input. Please enter a number.")

def main():
    """The main function to run the interactive launcher."""
    # --- Setup Logging ---
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = logs_dir / f"run_{timestamp}.log"

    # Configure logging to write to both a file and the console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            # Explicitly set encoding to UTF-8 to handle all characters
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("--- 🚀 Interactive Scraper & Captioner Launcher 🚀 ---")

    # --- Site & Search ---
    logging.info("\n[1] Enter the URL to scrape.")
    logging.info("   (Use '{}' as a placeholder for a search query if needed)")
    scrape_url = get_user_input("URL", default="https://www.pinterest.com/search/pins/?q={}", required=True)

    # --- Search & Output ---
    logging.info("\n[2] Enter your search details:")
    search_query = None
    keyword_join_char = None
    if "{}" in scrape_url:
        search_query = get_user_input("Search query (e.g., 'chloe moretz')", required=True)
        keyword_join_char = get_user_input("Keyword join character (e.g., '+' for ?q=, '%20' for path)", default="+")
        default_output = Path("downloads") / search_query.replace(' ', '_')
    else:
        default_output = Path("downloads") / get_default_output_from_url(scrape_url)
    output_dir = get_user_input("Output directory", default=default_output)
    download_range = get_user_input("Download range (e.g., '1-50')", default="1-50")

    # --- Authentication ---
    logging.info("\n[3] Configure authentication:")
    auth_method = get_choice_from_list(
        "Choose auth method",
        options=["From Browser", "From File", "None"],
        default_index=0
    )

    cookie_path = None
    browser_name = None

    if auth_method == "From Browser":
        logging.info("\n   Note: For this to work, the selected browser must be completely closed.")
        browser_name = get_user_input(
            "Enter browser name (chrome, firefox, edge, etc.)",
            default="edge"
        )
    elif auth_method == "From File":
        cookie_path = get_user_input("Path to cookies file", required=True)

    # --- Downloader Configuration ---
    logging.info("\n[4] Configure downloader:")
    use_multithreaded_input = get_user_input("Use multi-threaded for faster downloads? (y/n)", default="y")
    video_mode = get_user_input("Optimize for video downloads? (y/n)", default="n")
    max_threads = "8"
    if use_multithreaded_input.lower() not in ['n', 'no']:
        max_threads = get_user_input("Max download threads", default="8")

    # --- AI Captioning ---
    logging.info("\n[5] Configure AI captioning:")
    enable_autocaption_input = get_user_input("Enable AI auto-captioning for missing tags? (y/n)", default="y")

    # --- Build the Command ---
    command = [
        sys.executable,
        "-m",
        "utils.scraper",
        scrape_url,
    ]
    if search_query:
        command.extend([
            "--keywords", search_query,
            "--keyword-join-char", keyword_join_char
        ])
    command.extend([
        "--output-dir",
        str(output_dir),
        "--download-range",
        download_range,
    ])

    if cookie_path:
        command.extend(["--cookies", cookie_path])
    elif browser_name:
        command.extend(["--cookies-from-browser", browser_name])

    if use_multithreaded_input.lower() in ['n', 'no'] or video_mode.lower() in ['y', 'yes']:
        command.append("--no-fast-download")
    else:
        command.extend(["--max-threads", max_threads])

    if video_mode.lower() in ['y', 'yes']:
        command.append("--videos")

    if enable_autocaption_input.lower() in ['y', 'yes']:
        command.append("--autocaption")
        command.append("--is-tagger")

    # --- Display and Execute ---
    logging.info("\n" + "="*50)
    logging.info("✅ Command built successfully. Ready to execute:")
    logging.info(f"   {' '.join(command)}")
    logging.info("="*50 + "\n")

    if browser_name:
        logging.warning(f"IMPORTANT: Please ensure '{browser_name}' is completely closed before proceeding.")

    run_command_input = get_user_input("Execute this command? (y/n)", default="y")
    if run_command_input.lower() in ['y', 'yes']:
        try:
            logging.info("--- Starting Subprocess: utils.scraper ---")
            # The project root is the directory containing launcher.py and the utils folder.
            project_root = Path(__file__).parent.resolve()
            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                command, # Pass command as a list for safety and compatibility
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Redirect stderr to stdout
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=project_root
            )
            # Read and log output line by line
            for line in iter(process.stdout.readline, ''):
                logging.info(line.strip())
            process.wait()
            if process.returncode != 0:
                logging.error(f"\n❌ Subprocess finished with error code {process.returncode}.")
            else:
                logging.info("\n✅ Script finished successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"\n❌ An error occurred during execution: {e}")
        except FileNotFoundError:
            logging.error("\n❌ Error: 'python' command not found. Is Python installed and in your PATH?")
    else:
        logging.info("Execution cancelled by user.")

if __name__ == "__main__":
    main()