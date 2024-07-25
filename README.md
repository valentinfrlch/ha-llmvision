<p align="center">
<img src="https://github.com/user-attachments/assets/bebd92b8-765e-4d63-bb3d-47e1bb8b51ad" width=500px>
</p>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-1.0.0-blue>
<a href="https://github.com/valentinfrlch/ha-gpt4vision/issues">
<img src="https://img.shields.io/maintenance/yes/2024.svg">
<img alt="Issues" src="https://img.shields.io/github/issues/valentinfrlch/ha-gpt4vision?color=0088ff"/>
    </a>
    <p align=center style="font-weight:bold">
      Image Analyzer for Home Assistant using Multimodal LLMs
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
    <a href="#model-overview">🧠 Model Overview</a>
    ·
    <a href="#roadmap">🚧 Roadmap</a>
    ·
    <a href="#how-to-report-a-bug-or-request-a-feature">🪲 How to report Bugs</a>
  </p>


<br>
<br>
<br>

**LLM Vision** is a Home Assistant integration that allows you to analyze images and camera feeds using the vision capabilities of multimodal LLMs.  
Supported providers are OpenAI, Anthropic, Google Gemini, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/).

## Features
- Compatible with OpenAI, Anthropic Claude, Google Gemini, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/)
- Takes images and camera entities as input as well as image files
- Images can be downscaled for faster processing
- Can be installed and updated through HACS and can be set up in the Home Assistant UI

## Resources
Check the [📖 wiki](https://github.com/valentinfrlch/ha-gpt4vision/wiki) for examples on how you can integrate llmvision into your Home Assistant setup or join the [🗨️ discussion](https://community.home-assistant.io/t/gpt-4o-vision-capabilities-in-home-assistant/729241) in the Home Assistant Community.

# Installation
### Installation via HACS (recommended)
[![Open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=valentinfrlch&repository=ha-gpt4vision&category=Integration)
1. Search for `LLM Vision` in Home Assistant Settings/Devices & services
2. Select your provider
3. Follow the instructions to add your AI providers.

### Manual Installation
1. Download and copy the **llmvision** folder into your **custom_components** folder.
2. Add integration in Home Assistant Settings/Devices & services
3. Follow the instructions to add your AI providers.


## Provider specific setup
### OpenAI
Simply obtain an API key from [OpenAI](https://platform.openai.com/api-keys) and enter it in the Home Assistant UI during setup.  
A pricing calculator is available here: [https://openai.com/api/pricing/](https://openai.com/api/pricing/).

### Anthropic
Obtain an API key from [Anthropic](https://claude.ai/) and enter it in the Home Assistant UI during setup.
Pricing is available here: [Anthropic image cost](https://docs.anthropic.com/en/docs/build-with-claude/vision#calculate-image-costs). Images can be downscaled with the built-in downscaler.

### Google
To use Google Gemini you need to have a Google account and obtain an API key from the [AI Studio](https://aistudio.google.com/app/apikey). Depending on your region, you may need to enable billing. Pricing is available here: [Gemini Pricing](https://ai.google.dev/pricing)

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
After restarting, the llmvision.image_analyzer service will be available. You can test it in the developer tools section in home assistant.
To get OpenAI gpt-4o's analysis of a local image, use the following service call.

```yaml
service: llmvision.image_analyzer
data:
  provider: OpenAI
  message: Describe what you see?
  max_tokens: 100
  model: gpt-4o
  image_file: |-
    /config/www/tmp/example.jpg
    /config/www/tmp/example2.jpg
  image_entity:
    - camera.garage
    - image.front_door_person
  target_width: 1280
  detail: low
  temperature: 0.5
  include_filename: true
```
| Parameter        | Optional |                     Description        | Default | Valid Values                   |
|------------------|----------|--------------------------------------|---------------------|----------------------|
| `provider`       | No      | The AI provider call.     |         `OpenAI`                      |`OpenAI`, `Anthropic`, `Google`, `Ollama`, `LocalAI`|
| `model`          | Yes       | Model used for processing the image(s).            |      |  See table below |
| `message`        | No      | The prompt to send along with the image(s).     |                 |  String  |
| `image_file`     | Yes*      | The path to the image file(s). Each path must be on a new line.| |Valid path to an image file|
| `image_entity`   | Yes*      | An alternative to `image_file` for providing image input.|       |any `image` or `camera` entity|
| `include_filename` | Yes     | Whether to include the filename in the request.        | `false` | `true`, `false`|
| `target_width`   | Yes       | Width to downscale the image to before encoding. |  1280  | Integer between 512 and 3840|
| `detail`         | Yes       | Level of detail to use for image understanding.  | `auto` | `auto`, `low`, `high` |
| `max_tokens`     | No      | The maximum number of response tokens to generate.     | 100      |Integer between 10 and 1000|
| `temperature`    | No      | Randomness of the output.       |       0.5                        |Float between 0.0 and 1.0|


### Additional information
>[!NOTE]
> If you set `include_filename` to `false` (the default) requests will look roughly like the following:
> Images will be numbered sequentially starting from 1. You can refer to the images by their number in the prompt.
```
Image 1:
<base64 encoded image>
Image 2:
<base64 encoded image>
...
<Your prompt>
```

>[!NOTE]
> If you set `include_filename` to `true` requests will look roughly like the following
> - If the input is an image entity, the filename will be the entity's `friendly_name` attribute.
> - If the input is an image file, the filename will be the file's name without the extension.
> - Your prompt will be appended to the end of the request.
```
Front Door:
<base64 encoded image>
front_door_2024-12-31_23:59:59:
<base64 encoded image>
...
<Your prompt>
```


## Model Overview

| Model Name     |       Hosting Options     | Description          |   MMMU<sup>1</sup> Score   |
|----------------|---------------------------|----------------------|----------------|
| GPT-4o         | Cloud (OpenAI API key required)       | Best all-round model| 69.1 |
| Claude 3.5 Sonnet | Cloud (Anthropic API key required)      | Balance between performance and speed | 68.3
| Claude 3 Haiku   | Cloud (Anthropic API key required)       | Fast model optimized for speed | 50.2| 
| Claude 3 Sonnet  | Cloud (Anthropic API key required)       | Balance between performance and speed | 53.1
| Claude 3 Opus | Cloud (Anthropic API key required)       | High-performance model for more accuracy | 59.4
| Gemini 1.5 Flash | Cloud (Google API key required)      | Fast model optimized for speed | 56.1
| Gemini 1.5 Pro | Cloud (Google API key required)      | High-performance model for more accuracy | 62.2
| LLaVA-1.6 | Self-hosted (LocalAI or Ollama)       | Open-Source alternative | 43.8
<p align="right">Data is based on the MMMU Leaderboard<sup>2</sup></p>

### Choosing the right model for you
>[!NOTE]
> **Claude 3.5 Sonnet** achieves strong performance - comparable to GPT-4o - in the Massive Multi-discipline Multimodal Understanding and Reasoning Benchmark MMMU<sup>1</sup>, while being 40% less expensive. This makes it the go-to model for most use cases.


LLM Vision is compatible with multiple providers, each of which has different models available. Some providers run in the cloud, while others are self-hosted.  
To see which model is best for your use case, check the figure below. It visualizes the averaged MMMU<sup>1</sup> scores of available cloud-based models. The higher the score, the better the model performs.

<img src="benchmark_visualization\benchmark_visualization.jpg" alt="MMMU Benchmark visualization">
<p align="right">Benchmark will be updated regularly to include new models.</p>

<sup>1</sup> MMMU stands for "Massive Multi-discipline Multimodal Understanding and Reasoning Benchmark". It assesses multimodal capabilities including image understanding.  
<sup>2</sup> The data is based on the [MMMU Leaderboard](https://mmmu-benchmark.github.io/#leaderboard)


### Debugging
To enable debugging, add the following to your `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.llmvision: debug
```


## Roadmap
> [!NOTE]
> These are planned features and ideas. They are subject to change and may not be implemented in the order listed or at all.

1. **Feature**: HTTPS support for LocalAI and Ollama
2. **New Provider**: NVIDIA ChatRTX 
3. **Feature**: Support for video files  
  Extract images in variable intervals and analyze them
4. **HACS**: Submit PR to include in HACS default repository



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

