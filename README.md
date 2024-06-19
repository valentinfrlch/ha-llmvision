<h1 align=center> GPT-4 Vision for Home Assistant </h1>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-0.3.9-blue>
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
    <a href="#usage">▶️ Usage</a>
    ·
    <a href="#how-to-report-a-bug-or-request-a-feature">🪲 How to report Bugs</a>
  </p>


<br>
<br>
<br>

**gpt4vision** is a Home Assistant integration that allows you to analyze images using GPT-4 Vision.  
Supported providers are OpenAI, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/).

## Features
- Multimodal, natural language conversation in Home Assistant
- Compatible with OpenAI's API, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/)
- Integrates with Frigate and other integrations that provide image entities
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
To use LocalAI you need to have a LocalAI server running. You can find the installation instructions [here](https://localai.io/basics/getting_started/).  During setup you'll need to provide the IP address of your machine and the port on which LocalAI is running (default is 8000).

### Ollama
---
To use Ollama you need to have an Ollama server running. You can download it from [here](https://ollama.com/). Once installed you need to run the following command to download the `llava` model:
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

## Usage
After restarting, the gpt4vision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get OpenAI gpt-4o's analysis of a local image, use the following service call.

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
  image_entity:
    - image.front_door_person
    - image.garage_car
  target_width: 1280
  detail: low
  temperature: 0.5
```
>[!NOTE]
>Note that for `image_file` each path must be on a new line.  
>The parameters `provider`, `message`, `max_tokens` and `temperature` are required.
>Additionally, either `image_file` or `image_entity` need to have at least one input.  
>You can send multiple images per service call as well as mix `image_file` and `image_path` inputs.

Optionally, the `model`, `target_width` and `detail` properties can be set.  
- For available **models** check these pages: [supported models for OpenAI](https://platform.openai.com/docs/models) and [LocalAI model gallery](https://localai.io/models/).
- The **target_width** is an integer between 512 and 3840 representing the image width in pixels. It is used to downscale the image before encoding it.
- The **detail** parameter can be set to `low` or `high`. If it is not set, it is set to `auto`. OpenAI will then use the image size to determine the detail level. For more information check the [OpenAI documentation](https://platform.openai.com/docs/guides/vision/low-or-high-fidelity-image-understanding).

### Debugging
To enable debugging, add the following to your `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.gpt4vision: debug
```


## How to report a bug or request a feature
> [!IMPORTANT]
> **Bugs:** If you encounter any bugs and have followed the instructions carefully, feel free to file a bug report.  
> **Feature Requests:** If you have an idea for a feature, create a feature request.
><div align = left>
>
>[<kbd> <br> Create new Issue <br> </kbd>][KBD]
>
></div>
>
>[KBD]: https://github.com/valentinfrlch/ha-gpt4vision/issues/new/choose

