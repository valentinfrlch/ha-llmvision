# Declare variables
import base64
import requests
import io
from homeassistant.core import SupportsResponse
from PIL import Image

DOMAIN = 'gpt4vision'

# config
CONF_API = 'api'
CONF_MAXTOKENS = 'max_tokens'
CONF_TARGET_WIDTH = 'target_width'
CONF_MODEL = 'model'
CONF_MESSAGE = 'message'
CONF_IMAGE_FILE = 'image_file'
CON_RESPONSE_FILE_PATH = '/config/custom_components/gpt4vision/'


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    def image_analyzer(data_call):
        """_summary_

        Returns:
            json: response_text
        """

        # Get config from configuration.yaml
        api = str(config[DOMAIN][CONF_API])  # Your OpenAI API key

        # Get data from Service Call
        # Resolution (width only) of the image. Example: 1280 for 720p etc.
        target_width = data_call.data.get(CONF_TARGET_WIDTH)
        # Local path to your image. Example: "/config/www/images/doorbell_snapshot.jpg"
        image_path = data_call.data.get(CONF_IMAGE_FILE)
        # Maximum number of tokens used by model. Test around 300
        max_tokens = int(data_call.data.get(CONF_MAXTOKENS))
        # OpenAI model. The default model is gpt-4o
        model = str(data_call.data.get(CONF_MODEL, "gpt-4o"))

        # The input for OpenAI GPT4-Vision API will condition the analysis of the image and the respective text response. This input varies with the prompt and the maximum number of tokens.
        # This is the prompt message. It must be a request to the AI, indicating the analysis and the characteristics that you want to obtain a description of.
        message = str(data_call.data.get(CONF_MESSAGE)[0:2000])

        def encode_image(image_path):
            """_summary_

            Args:
                image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

            Returns:
                string: image encoded as base64
            """
            # Open the image file
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                # Resize the image only if it's larger than the target size
                # API call price is based on resolution. The smaller the image, the cheaper the call
                # Check https://openai.com/api/pricing/ for information on pricing
                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                # Convert the image to base64
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                base64_image = base64.b64encode(
                    img_byte_arr.getvalue()).decode('utf-8')

            return base64_image

        # Get the base64 string from the image
        base64_image = encode_image(image_path)

        # HTTP Request for AI API
        # Header Parameters
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer '+api}

        # Body Parameters
        data = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": message},
                                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}], "max_tokens": max_tokens}

        # Get response from OpenAI and read content inside message
        response = requests.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response_text = response.json().get(
            "choices")[0].get("message").get("content")

        return {"response_text": response_text}

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
