<h1 align=center> GPT-4 Vision for Home Assistant </h1>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-0.3.6-blue>
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
Supported providers are OpenAI, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/).

## Features
- Multimodal conversation with AI models
- Compatible with OpenAI's API, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/)
- Images can be downscaled for faster processing
- Can be installed and updated through HACS and can be set up in the Home Assistant UI

## Resources
Check the [📖 wiki](https://github.com/valentinfrlch/ha-gpt4vision/wiki) for examples on how you can integrate gpt4vision into your Home Assistant or join the [🗨️ discussion](https://community.home-assistant.io/t/gpt-4o-vision-capabilities-in-home-assistant/729241) in the Home Assistant Community.

# Installation
### Installation via HACS (recommended)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=valentinfrlch&repository=ha-gpt4vision&category=Integration)
1. Search for `GPT-4 Vision` in Home Assistant Settings/Devices & services
2. Select your provider
3. Follow the instructions to complete setup

### Manual Installation
1. Download and copy the **gpt4vision** folder into your **custom_components** folder.
2. Add integration in Home Assistant Settings/Devices & services
3. Provide your API key or IP address and port of your LocalAI server


## Provider specific setup
### OpenAI
Simply obtain an API key from [OpenAI](https://platform.openai.com/api-keys) and enter it in the Home Assistant UI during setup.  
A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).


### LocalAI
To use LocalAI, you need to have a LocalAI server running. You can find the installation instructions [here](https://localai.io/basics/getting_started/).  During setup you'll need to provide the IP address of your machine and the port on which LocalAI is running (default is 8000).

### Ollama
---
To use Ollama you first need to install Ollama on your machine. You can download it from [here](https://ollama.com/). Once installed you need to run the following command to download the `llava` model:
```bash
ollama run llava
```
If your Home Assistant is **not** running on the same computer as Ollama, you need to set the `OLLAMA_HOST` environment variable.

**On Linux:**
1. Edit the systemd service by calling `systemctl edit ollama.service`. This will open an editor.
2. For each environment variable, add a line Environment under section [Service]:

```
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```
3. Save and close the editor.
4. Reload systemd and restart Ollama
```bash
systemctl daemon-reload
systemctl restart ollama
```

**On Windows:**
1. Quit Ollama from the system tray
2. Open File Explorer
3. Right click on This PC and select Properties
4. Click on Advanced system settings
5. Select Environment Variables
6. Under User variables click New
7. For variable name enter `OLLAMA_HOST` and for value enter 0.0.0.0
8. Click OK and start Ollama again from the Start Menu

**On macOS:**
1. Open Terminal
2. Run the following command
```bash
launchctl setenv OLLAMA_HOST "0.0.0.0"
```
3. Restart Ollama

<br>

## Service call and usage
After restarting, the gpt4vision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get GPT's analysis of a local image, use the following service call.

```yaml
service: gpt4vision.image_analyzer
data:
  provider: OpenAI
  message: Describe what you see?
  max_tokens: 100
  model: gpt-4o
  image_file: |-
    /config/www/tmp/example.jpg
    /config/www/tmp/example2.jpg
  target_width: 1280
  detail: low
  temperature: 0.5
```
The parameters `provider`, `message`, `max_tokens`, `image_file` and `temperature` are required. You can send multiple images per service call. Note that each path must be on a new line.

Optionally, the `model`, `target_width` and `detail` properties can be set.  
- For available **models** check these pages: [supported models for OpenAI](https://platform.openai.com/docs/models) and [LocalAI model gallery](https://localai.io/models/).
- The **target_width** is an integer between 640 and 3840 representing the image width in pixels. It is used to downscale the image before encoding it.
- The **detail** parameter can be set to `low` or `high`. If it is not set, it is set to 'auto'. OpenAI will then use the image size to determine the detail level. For more information check the [OpenAI documentation](https://platform.openai.com/docs/guides/vision/low-or-high-fidelity-image-understanding).
## How to report a bug or request a feature
> [!NOTE]
> **Bugs:** If you encounter any bugs and have followed the instructions carefully, feel free to file a bug report.  
> **Feature Requests:** If you have an idea for a feature, create a feature request.
><div align = left>
>
>[<kbd> <br> Create new Issue <br> </kbd>][KBD]
>
></div>
>
>[KBD]: https://github.com/valentinfrlch/ha-gpt4vision/issues/new/choose

