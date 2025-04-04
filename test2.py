import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('axiomatic-genre-455219-i8-02643c013f6e.json', scope)
client = gspread.authorize(creds)
try:
    sheet = client.open('YouTube Playlist Scraper').get_worksheet(0)
    print("Successfully opened worksheet:", sheet.title)
except Exception as e:
    print("Error opening sheet:", e)
