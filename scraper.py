import requests
from bs4 import BeautifulSoup
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

def scrape_youtube_content():
    try:
        url = "https://www.youtube.com/feed/trending"
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        videos = soup.find_all('div', class_='yt-lockup-content')

        conn = sqlite3.connect('youtube_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY,
                title TEXT,
                url TEXT,
                views TEXT,
                upload_date TEXT
            )
        ''')

        for video in videos:
            title = video.find('a', class_='yt-uix-tile-link').text
            url = "https://www.youtube.com" + video.find('a', class_='yt-uix-tile-link')['href']
            views = video.find('ul', class_='yt-lockup-meta-info').find_all('li')[0].text
            upload_date = video.find('ul', class_='yt-lockup-meta-info').find_all('li')[1].text

            cursor.execute('''
                INSERT INTO videos (title, url, views, upload_date)
                VALUES (?, ?, ?, ?)
            ''', (title, url, views, upload_date))

        conn.commit()
        conn.close()

        logging.info("Scraping and storing YouTube content completed successfully.")

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    scrape_youtube_content()
