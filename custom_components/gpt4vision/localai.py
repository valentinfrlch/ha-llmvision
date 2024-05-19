"""Send a request to localai API '/v1/chat/completions' endpoint"""


import requests
import json
import base64


def localai_analyzer(image_path, message, model):
    """Send a request to localai API '/v1/chat/completions' endpoint

    Args:
        image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"
        message (string): message to be sent to AI model
        model (string): GPT model: Default model is gpt-4o
        max_tokens (int): Maximum number of tokens used by model. Default is 100.
        target_width (int): Resolution (width only) of the image. Example: 1280 for 720p etc.

    Returns:
        json: response_text
    """

    # Open the image file
    with open(image_path, "rb") as image_file:
        # Encode the image as base64
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    data = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": message},
                                                                      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_base64}}]}]}

    # Send a POST request to the localai API
    response = requests.post(
        "http://localhost:8080/v1/chat/completions", json=data)

    # Check if the request was successful
    if response.status_code != 200:
        raise Exception(
            f"Request failed with status code {response.status_code}")

    # Parse the response as JSON
    response_text = json.loads(response.text)

    return response_text


print(localai_analyzer("C:/Users/valen/Pictures/Screenshots/test.png", "What is in this image?", "gpt-4-vision-preview"))
