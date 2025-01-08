# YouTube Content Scraper and Interactive Database

This repository contains Python scripts and functions, as well as web site data, for an interactive database composed of scraped YouTube content. The purpose of this project is to scrape YouTube content, store it in a database, and provide a web interface to interact with the data.

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/githubnext/workspace-blank.git
   cd workspace-blank
   ```

2. Create a virtual environment and activate it:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Running the Scraper

1. Run the scraper to scrape YouTube content and store it in the database:
   ```
   python scraper.py
   ```

2. The scraped data will be stored in a SQLite database file named `youtube_data.db`.

## Interacting with the Database

1. Run the web application to interact with the database:
   ```
   python web_app.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000` to access the web interface.

3. Use the web interface to view and interact with the scraped YouTube content.
