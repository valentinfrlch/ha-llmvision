# GPT-4 Turbo with vision Service for Home Assistant
Image Analyzer using GPT-4 Turbo with vision and Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

**ha-gpt4vision** creates the gpt4vision.image_analyzer service in Home Assistant.
This service uploads an image to OpenAI using its API and return analysis from AI directly to selected TTS service and speaker devices inside Home Assistant.

Based on [ha-gpt4vision by filipecanedo](https://github.com/filipecanedo/ha-gpt4vision) with some small modifications:
- Instead of directly calling tts, this service returns the response in plain text. This should make the service more accessible for automations, where tts is not needed. See examples below for usage.
- An option to downscale images for lower cost has also been added.
- Lastly the default model is the new GPT-4o, which is cheaper and faster than GPT-4-turbo.

## Note about API key
**This service needs a valid API key**. You must obtain a valid OpenAI key from [here](https://platform.openai.com/api-keys).
A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).

## Installation
### Installation with HACS (recommeded)
1. Add this repository's url (https://github.com/valentinfrlch/ha-gpt4vision) to HACS under custom repositories.
2. Install through HACS
3. Add the following code to your configuration.yaml:
```ruby
# gpt4vision service setup
gpt4vision:
  api: "[Your OpenAI API key]"
```
4. Restart Home Assistant

### Manual Installation
1. Download and copy folder **gpt4vision** to your **custom_components** folder.
2. Add the following code to your configuration.yaml 
```ruby
# gpt4vision service setup
gpt4vision:
  api: "[Your OpenAI API key]"
```
3. Restart Home Assistant to load the gpt4vision custom_component.

## Service call and usage
After restart, the gpt4vision.image_analyzer service will be available.
To get GPT's analysis of a local image, use the following service call.

```ruby
service: gpt4vision.image_analyzer
data:
  message: '[Prompt message for AI]'
  max_tokens: [maximum number of tokens]
  entity_id: [media device]
  image_file: '[path for image file]'
```
The parameters ```message:```, ```max_tokens:```, ```entity_id:``` and ```image_file:``` are mandatory for the execution of the service.
Optionally, the AI model and the TTS cache [true/false] can be set.
```
data:
  model: gpt-4-vision-preview
  cache: true
```

### Example 1: Announcement for package delivery
If your camera doesn't support built in announcements for delivery, this is probably the easiest way to get them without running an object detection model.

```yaml
service: gpt4vision.image_analyzer
data:
  max_tokens: 100
  model: gpt-4o
  target_width: 1280
  image_file: /config/www/tmp/front_porch.jpg
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
  image_file: /config/www/tmp/garage.jpg
  message: >-
    What is the person doing? Does anything look suspicious? Answer only with
    "yes" or "no".
```

If you have any questions or suggestions, feel free to open an issue or a pull request.