# GPT-4 Vision for Home Assistant
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-0.3.0-blue>
<a href="https://github.com/valentinfrlch/ha-gpt4vision/issues">
      <img alt="Issues" src="https://img.shields.io/github/issues/valentinfrlch/ha-gpt4vision?color=0088ff" />
    </a>
    <p align=center style="font-weight:bold">
      Image Analyzer for Home Assistant using GPT Vision
    </p>
</p>

  <p align="center">
    <a href="#features">🌟 Features </a>
    ·
    <a href="#resources">📖 Resources</a>
    ·
    <a href="#installation">⬇️ Installation</a>
    ·
    <a href="#service-call-and-usage">▶️ Usage</a>
    ·
    <a href="#how-to-report-a-bug-or-request-a-feature">🪲 How to report Bugs</a>
    
  </p>

**ha-gpt4vision** creates the `gpt4vision.image_analyzer` service in Home Assistant.
This service sends an image to an AI provider and returns the output as a response variable for easy use in automations.
Supported providers are OpenAI and [LocalAI](https://github.com/mudler/LocalAI).

## Features
- Multimodal conversation with AI models
- Compatible with both OpenAI's API and [LocalAI](https://github.com/mudler/LocalAI)
- Images can be downscaled for faster processing
- Can be installed and updated through HACS and can be set up in the Home Assistant UI

## Resources
Check the [wiki](https://github.com/valentinfrlch/ha-gpt4vision/wiki/Usage-Examples) for examples on how you can integrate gpt4vision into your Home Assistant or join the [discussion](https://community.home-assistant.io/t/gpt-4o-vision-capabilities-in-home-assistant/729241) in the Home Assistant Community.

## API key
> [!IMPORTANT]  
> If you're planning on using **OpenAI's API** you'll **need an API key**. You must obtain a valid OpenAI key from [here](https://platform.openai.com/api-keys).

A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).


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
1. Download and copy the **gpt4vision** folder into your **custom_components** folder.
2. Add integration in Home Assistant Settings/Devices & services
3. Provide your API key or IP address and port of your LocalAI server

## Service call and usage
After restarting, the gpt4vision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get GPT's analysis of a local image, use the following service call.

```yaml
service: gpt4vision.image_analyzer
data:
  max_tokens: 100
  message: Describe what you see
  image_file: |-
    /config/www/tmp/example.jpg
    /config/www/tmp/example2.jpg
  provider: LocalAI
  model: gpt-4-vision-preview
  target_width: 1280
```
The parameters `message`, `max_tokens`, `image_file` and `provider` are required. You can send multiple images per service call. Note that each path must be on a new line and that sending multiple images may require higher `max_tokens` values for accurate results.

Optionally, the `model` and `target_width` properties can be set. For available models check these pages: [OpenAI](https://platform.openai.com/docs/models) and [LocalAI](https://localai.io/models/).

## How to report a bug or request a feature
> [!NOTE]
> **Bugs:** If you encounter any bugs and have followed the instructions carefully, feel free to file a bug report.  
> **Feature Requests:** If you have an idea for a feature, create a feature request.
