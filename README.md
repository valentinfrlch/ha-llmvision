# GPT-4 Vision for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

Image Analyzer for Home Assistant using GPT-4o.

**ha-gpt4vision** creates the `gpt4vision.image_analyzer` service in Home Assistant.
This service sends an image to OpenAI using its API and returns the model's output as a response variable, making it easy to use in automations.

## Features
- Service returns the model's output as response variable. This makes the service more accessible for automations. See examples below for usage.
- To reduce the cost of the API call, images can be downscaled to a target width.
- The default model, GPT-4o, is cheaper and faster than GPT-4-turbo..
  - Any model capable of vision can be used. For available models check this page: [https://platform.openai.com/docs/models](https://platform.openai.com/docs/models).
- This custom component can be installed through HACS and can be set up in the Home Assistant UI.
## API key
**This service needs a valid API key**. You must obtain a valid OpenAI key from [here](https://platform.openai.com/api-keys).
A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).

# Installation
### Installation via HACS (recommended)
1. Add this repository's url (https://github.com/valentinfrlch/ha-gpt4vision) to HACS under custom repositories.
2. Install through HACS
3. Restart Home Assistant
4. Add integration in Home Assistant Settings/Devices & services
5. Provide your API key

### Manual Installation
1. Download and copy folder **gpt4vision** to your **custom_components** folder.
2. Add integration in Home Assistant Settings/Devices & services
3. Provide your API key

## Service call and usage
After restarting, the gpt4vision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get GPT's analysis of a local image, use the following service call.

```yaml
service: gpt4vision.image_analyzer
data:
  message: '[Prompt message for AI]'
  model: '[model]'
  image_file: '[path for image file]'
  target_width: [Target width for image downscaling]
  max_tokens: [maximum number of tokens]'
```
The parameters `message`, `max_tokens` and `image_file` are mandatory for the execution of the service.
Optionally, the `model` and the `target_width` can be set. For available models check this page: https://platform.openai.com/docs/models.

## Automation Example
In automations, if your response variable name is `response`, you can access the response as `{{response.response_text}}`.:
```yaml
sequence:
  - service: gpt4vision.image_analyzer
    metadata: {}
    data:
      message: Describe the person in the image
      image_file: /config/www/tmp/test.jpg
      max_tokens: 100
    response_variable: response
  - service: tts.speak
    metadata: {}
    data:
      cache: true
      media_player_entity_id: media_player.entity_id
      message: "{{response.response_text}}"
    target:
      entity_id: tts.tts_entity
```

## Usage Examples
### Example 1: Announcement for package delivery
If your camera doesn't support built-in delivery announcements, this is likely the easiest way to get them without running an object detection model.

```yaml
service: gpt4vision.image_analyzer
data:
  max_tokens: 100
  model: gpt-4o
  target_width: 1280
  image_file: '/config/www/tmp/front_porch.jpg'
  message: >-
    Does it look like the person is delivering a package? Answer with only "yes"
    or "no".
    # Answer: yes
```
<img alt="man delivering package" src="https://github.com/valentinfrlch/ha-gpt4vision/assets/85313672/ab615fd5-25b5-4e07-9c44-b10ec7a678c0">

### Example 2: Suspicious behaviour
An automation could be triggered if a person is detected around the house when no one is home.
![suspicious behaviour](https://github.com/valentinfrlch/ha-gpt4vision/assets/85313672/411678c4-f344-4eeb-9eb2-b78484a4d872)

```
service: gpt4vision.image_analyzer
data:
  max_tokens: 100
  model: gpt-4o
  target_width: 1280
  image_file: '/config/www/tmp/garage.jpg'
  message: >-
    What is the person doing? Does anything look suspicious? Answer only with
    "yes" or "no".
```

If you have any questions or suggestions, feel free to open an issue or a pull request.
