import subprocess

result = subprocess.run(
    ["python", "scrape_playlist_id.py", "--playlist", "PLrq7heytJY0nhwqTBIm86YthIxiXaQqQV"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print("STDOUT:\n", result.stdout)
print("STDERR:\n", result.stderr)
print("Exit Code:", result.returncode)
