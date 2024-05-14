# GPT-4 Vision for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

Image Analyzer using GPT-4 Turbo with vision and Home Assistant

**ha-gpt4vision** creates the `gpt4vision.image_analyzer` service in Home Assistant.
This service uploads an image to OpenAI using its API and returns GPT 4's response as service response so it can easily be used for automations.

Based on [ha-gpt4vision by filipecanedo](https://github.com/filipecanedo/ha-gpt4vision) with some modifications:
- Instead of directly calling tts, this service returns the response in plain text. This should make the service more accessible for automations, where tts is not needed. See examples below for usage.
- An option to downscale images for lower cost has also been added.
- The default model is the new GPT-4o, which is cheaper and faster than GPT-4-turbo.
- Lastly this repository can be added to HACS as custom repository for easier installation and updating.

## API key
**This service needs a valid API key**. You must obtain a valid OpenAI key from [here](https://platform.openai.com/api-keys).
A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).

## Installation
### Installation via HACS (recommended)
1. Add this repository's url (https://github.com/valentinfrlch/ha-gpt4vision) to HACS under custom repositories.
2. Install through HACS
3. Add the following code to your configuration.yaml:
```yaml
# gpt4vision service setup
gpt4vision:
  api: "[Your OpenAI API key]"
```
4. Restart Home Assistant

### Manual Installation
1. Download and copy folder **gpt4vision** to your **custom_components** folder.
2. Add the following code to your configuration.yaml 
```yaml
# gpt4vision service setup
gpt4vision:
  api: "[Your OpenAI API key]"
```
3. Restart Home Assistant to load the gpt4vision custom_component.

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
The parameters ```message:```, ```max_tokens:``` and ```image_file:``` are mandatory for the execution of the service.
Optionally, the model and the target image width can be set. For available models check this page: https://platform.openai.com/docs/models.

## Usage Examples
### Example 1: Announcement for package delivery
If your camera doesn't support built in announcements for delivery, this is probably the easiest way to get them without running an object detection model.

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
An automation could be triggered when a person is detected around the house when no one is home. GPT-4 vision can determine if a person is doing something suspicious. The automation could then trigger an alarm.
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
