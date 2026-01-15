import requests

url = "http://127.0.0.1:5001/ocr_upload"
files = {'image': open('kk.jpg', 'rb')}

try:
    response = requests.post(url, files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")