import requests

url = "http://localhost:5000/upload"

with open("test.jpg", "rb") as f:
    files = {"image": f}
    r = requests.post(url, files=files)

with open("result.mp3", "wb") as out:
    out.write(r.content)

print("Audio saved as result.mp3")
