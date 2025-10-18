# MScraper

MScraper is a powerful and versatile media scraper designed to download images and videos from various websites. It features an interactive launcher for easy configuration, a high-speed multi-threaded downloader, and an optional AI-powered auto-captioning system for images.

## Features

-   **Interactive Launcher**: An easy-to-use command-line interface (`launcher.py`) to configure and run scraping tasks without manually writing complex commands.
-   **Versatile Scraping**: Leverages the power of `gallery-dl` to support a wide range of websites.
-   **High-Speed Downloader**: Includes a custom multi-threaded downloader for significantly faster downloads compared to standard methods.
-   **AI Auto-Captioning**: Automatically generates descriptive tags for downloaded images that lack metadata, using a pre-trained model from Hugging Face.
-   **Flexible Authentication**: Supports using cookies from your web browser (Edge, Chrome, Firefox, etc.) or from a local cookies file to access sites that require a login.
-   **Tag Processing**: Cleans and formats metadata tags from downloaded files for better organization.
-   **Customizable**: Offers numerous command-line arguments to tailor scraping behavior, including download ranges, video optimization, and more.

## Installation

To get started with MScraper, follow these steps:

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/wingzofmidnight/mscraper.git
    cd MScraper
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # For Windows
    python -m venv .venv
    .venv\Scripts\Activate

    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

## Usage

The easiest way to use MScraper is through the interactive launcher.

```sh
python launcher.py
```

The launcher will guide you through the following steps:
1.  **URL and Search**: Enter the URL to scrape. If the URL is for a search, use `{}` as a placeholder for your query.
2.  **Authentication**: Choose how to authenticate (e.g., by using cookies from a closed browser).
3.  **Downloader**: Select between the fast multi-threaded downloader or the standard one.
4.  **AI Captioning**: Enable or disable automatic tagging for images.

After configuration, it will display the final command and ask for confirmation before executing the scrape.

### Direct Script Usage

For advanced users or for use in automated scripts, you can call `utils/scraper.py` directly with command-line arguments.

```sh
python -m utils.scraper [URL] [OPTIONS]
```

**Example:**

```sh
python -m utils.scraper "https://www.pinterest.com/search/pins/?q={}" --keywords "Ada Wong" --output-dir "downloads/Ada_Wong" --cookies-from-browser edge --autocaption
```

Run `python -m utils.scraper --help` to see all available options.

## Dependencies

This project relies on several key libraries:

-   `gallery-dl`: For the core website scraping logic.
-   `requests`: For making HTTP requests.
-   `transformers`, `torch`, `Pillow`, `timm`: For the AI auto-captioning feature.
-   `tqdm`: For progress bars.

## License

This project is currently unlicensed. You are free to add a license of your choice.
