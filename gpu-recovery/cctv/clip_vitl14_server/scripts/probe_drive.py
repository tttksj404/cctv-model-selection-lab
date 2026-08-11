import requests


url = "https://drive.google.com/uc?export=download&id=1Y-RFAYdT56vnMjwxH1Ym3DVhZzZuMQZs"
response = requests.get(url, stream=True, timeout=30)
print(response.status_code)
print(response.headers.get("content-length"))
print(response.headers.get("content-type"))
print(response.url)
print(response.text[:4000])
