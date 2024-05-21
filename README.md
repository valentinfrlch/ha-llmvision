# GPT-4 Vision for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

Image Analyzer for Home Assistant using GPT-4o.

**ha-gpt4vision** creates the `gpt4vision.image_analyzer` service in Home Assistant.
This service sends an image to an AI provider and returns the output as a response variable for easy use in automations.
Supported providers are OpenAI and [LocalAI](https://github.com/mudler/LocalAI).

## Features
- Compatible with both OpenAI's API and [LocalAI](https://github.com/mudler/LocalAI).
- Images can be downscaled for faster processing.
- Can be installed through HACS and can be set up in the Home Assistant UI.

### Examples
Check the [wiki](https://github.com/valentinfrlch/ha-gpt4vision/wiki/Usage-Examples) for examples on how you could use gpt4vision.

## API key
> [!IMPORTANT]  
> If you're planning on using **OpenAI's API** you'll **need an API key**. You must obtain a valid OpenAI key from [here](https://platform.openai.com/api-keys).
> A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).


# Installation
### Installation via HACS (recommended)
1. Add this repository's url (https://github.com/valentinfrlch/ha-gpt4vision) to HACS under custom repositories.
2. Install through HACS
3. Restart Home Assistant
4. Search for `GPT-4 Vision` in Home Assistant Settings/Devices & services
5. Select wheter you want to use OpenAI or your own LocalAI server for processesing
   - For OpenAI's API provide your API key
   - For LocalAI enter your IP address and port of your LocalAI server

### Manual Installation
1. Download and copy folder **gpt4vision** to your **custom_components** folder.
2. Add integration in Home Assistant Settings/Devices & services
3. Provide your API key or IP address and port of your LocalAI server

## Service call and usage
After restarting, the gpt4vision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get GPT's analysis of a local image, use the following service call.

```yaml
service: gpt4vision.image_analyzer
data:
  max_tokens: 100
  message: Describe what you see in this image
  image_file: /config/www/tmp/example.jpg
  provider: LocalAI
  model: gpt-4o
  target_width: 1280
```
The parameters `message`, `max_tokens`m `image_file` and `provider` are required.
Optionally, the `model` and `target_width` properties can be set. For available models check these pages: [OpenAI](https://platform.openai.com/docs/models) and [LocalAI](https://localai.io/models/).

## Issues
> [!NOTE]
> **Bugs:** If you encounter any bugs and have read the docs carefully, feel free to file a bug report.  
> **Feature Requests:** If you have an idea for a feature, file a feature request.
