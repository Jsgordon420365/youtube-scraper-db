import yt_dlp

url = "https://www.youtube.com/watch?v=Tx0Y3qb9ZUc"
ydl_opts = {}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    print("Title:", info['title'])
    print("Uploader:", info['uploader'])
    print("Upload date:", info['upload_date'])
    print("Description:", info['description'][:100] + "...")
