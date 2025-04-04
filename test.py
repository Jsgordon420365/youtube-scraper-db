from pytube import YouTube

url = "https://www.youtube.com/watch?v=Tx0Y3qb9ZUc"
try:
    yt = YouTube(url)
    print("Title:", yt.title)
except Exception as e:
    print("Error fetching video:", e)
