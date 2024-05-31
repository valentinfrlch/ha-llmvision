from homeassistant.exceptions import ServiceValidationError
import logging

_LOGGER = logging.getLogger(__name__)


async def handle_localai_request(session, model, message, base64_images, ip_address, port, max_tokens, temperature):
    data = {"model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": message}
            ]}],
            "max_tokens": max_tokens,
            "temperature": temperature
            }
    for image in base64_images:
        data["messages"][0]["content"].append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})

    try:
        response = await session.post(
            f"http://{ip_address}:{port}/v1/chat/completions", json=data)
    except Exception as e:
        _LOGGER.error(f"Request failed: {e}")
        raise ServiceValidationError(f"Request failed: {e}")

    if response.status != 200:
        raise ServiceValidationError(
            f"Request failed with status code {response.status}")
    response_text = (await response.json()).get("choices")[0].get(
        "message").get("content")
    return response_text


async def handle_openai_request(session, model, message, base64_images, api_key, max_tokens, temperature, detail):
    headers = {'Content-type': 'application/json',
               'Authorization': 'Bearer ' + api_key}
    data = {"model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": message}
            ]}],
            "max_tokens": max_tokens,
            "temperature": temperature
            }

    # Add the images to the request
    for image in base64_images:
        data["messages"][0]["content"].append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}", "detail": detail}})

    try:
        response = await session.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    except Exception as e:
        _LOGGER.error(f"Request failed: {e}")
        raise ServiceValidationError(f"Request failed: {e}")

    if response.status != 200:
        raise ServiceValidationError(
            (await response.json()).get('error').get('message'))
    response_text = (await response.json()).get(
        "choices")[0].get("message").get("content")
    return response_text


async def handle_ollama_request(session, model, message, base64_images, ip_address, port, max_tokens, temperature):
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": message,
                "images": []
            }
        ],
        "stream": False,
        "options": {
            "max_tokens": max_tokens,
            "temperature": temperature
        }
    }
    
    for image in base64_images:
        data["messages"][0]["images"].append(image)

    try:
        response = await session.post(
            f"http://{ip_address}:{port}/api/chat", json=data)
    except Exception as e:
        _LOGGER.error(f"Request failed: {e}")
        raise ServiceValidationError(f"Request failed: {e}")

    if response.status != 200:
        raise ServiceValidationError(
            f"Request failed with status code {response.status}")
    response_text = (await response.json()).get(
        "message").get("content")
    return response_text