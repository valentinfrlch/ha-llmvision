# Declare variables
import json
import base64
import requests
import os

DOMAIN = 'gpt4vision'

# config
CONF_API = 'api'
CONF_TTS = 'tts'
CONF_MAXTOKENS = 'max_tokens'
CONF_MODEL = 'model'
CONF_MESSAGE = 'message'
CONF_PLAYER_ID = 'entity_id'
CONF_IMAGE_FILE = 'image_file'
CONF_CACHE = 'cache'
CON_RESPONSE_FILE_PATH = '/config/custom_components/gpt4vision/'

def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    def image_analyzer(data_call):
        """Handle the service call."""

        # Get config from configuration.yaml
        api = str(config[DOMAIN][CONF_API]) # Your OpenAI API key
        tts = str(config[DOMAIN][CONF_TTS]) # Choose HA TTS Service. Example: cloud_say
        
        # Get data from Service Call
        media_id = data_call.data.get(CONF_PLAYER_ID) # Entity ID of media device. Can be a single device or a group.
        image_path = data_call.data.get(CONF_IMAGE_FILE) # Local path to your image. Example: "/config/www/images/doorbell_snapshot.jpg"
        cache_opt = bool(data_call.data.get(CONF_CACHE)) # TTS cache, can be true or false
        max_tokens = int(data_call.data.get(CONF_MAXTOKENS)) # Maximum number of tokens used by model. Test around 300
        model = str(data_call.data.get(CONF_MODEL, "gpt-4-vision-preview")) # OpenAI model. The default model is gpt-4-vision-preview
        
        # Set text file where response will be stored
        response_file=CON_RESPONSE_FILE_PATH + "response.txt"

        # The input for OpenAI GPT4-Vision API will condition the analysis of the image and the respective text response. This input varies with the prompt and the maximum number of tokens.    
        message = str(data_call.data.get(CONF_MESSAGE)[0:2000]) # This is the prompt message. It must be a request to the AI, indicating the analysis and the characteristics that you want to obtain a description of.

        # Function to read and convert image to base64 format 
        def encode_image(image_path):
          with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

        # Get the base64 string from the image
        base64_image = encode_image(image_path)

        # HTTP Request for AI API
        # Header Parameters
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer '+api}

        # Body Parameters
        data = {"model": model, "messages": [{"role": "user","content": [{"type": "text","text": message },
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}" } } ] } ], "max_tokens": max_tokens }
        
        # Get response from OpenAI and read content inside message
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response_text = response.json().get("choices")[0].get("message").get("content")

        # Save response to text file
        with open(response_file, "w") as file:
           file.write(response_text) # Write the response to a text file for logging and optional use with other services
            
        hass.bus.async_fire("gpt4vision", {"result": response_text})
        
        # Call TTS service from Home Assistant with the content of the AI response message
        service_data = {"entity_id": media_id, "cache": cache_opt, "message": response_text}
        hass.services.call('tts', tts, service_data)
    hass.services.register(DOMAIN, "image_analyzer", image_analyzer)
    return True
