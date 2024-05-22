import requests

url = 'http://localhost:8080/readyz'
response = requests.get(url)
print(response)