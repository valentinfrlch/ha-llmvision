import requests

url = "http://10.0.1.82:8080/v1/chat/completions"

data = {}

# make a request to the server
response = requests.post(url, data=data)
print(response.status_code)
