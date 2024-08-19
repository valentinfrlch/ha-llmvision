<p align="center">
<img src="https://github.com/user-attachments/assets/bebd92b8-765e-4d63-bb3d-47e1bb8b51ad" width=500px>
</p>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-1.0.3-blue>
<a href="https://github.com/valentinfrlch/ha-llmvision/issues">
<img src="https://img.shields.io/maintenance/yes/2024.svg">
<img alt="Issues" src="https://img.shields.io/github/issues/valentinfrlch/ha-llmvision?color=0088ff"/>
    </a>
    <p align=center style="font-weight:bold">
      Image and video analyzer for Home Assistant using multimodal LLMs
    </p>
</p>

  <p align="center">
    <a href="#features">🌟 Features </a>
    ·
    <a href="#resources">📖 Resources</a>
    ·
    <a href="#installation">⬇️ Installation</a>
    ·
    <a href="#roadmap">🚧 Roadmap</a>
    ·
    <a href="#how-to-report-a-bug-or-request-a-feature">🪲 How to report Bugs</a>
  </p>


<br>
<br>
<br>

**LLM Vision** is a Home Assistant integration to analyze images, videos and camera feeds using the vision capabilities of multimodal LLMs.  
Supported providers are OpenAI, Anthropic, Google Gemini, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/).

## Features
- Compatible with OpenAI, Anthropic Claude, Google Gemini, [LocalAI](https://github.com/mudler/LocalAI) and [Ollama](https://ollama.com/)
- Takes images and video from camera entities as input
- Takes local image and video files as input
- Images can be downscaled for faster processing

## Resources
Check the docs for detailed instructions on how to set up LLM Vision and each of the supported providers as well as usage examples and service call parameters:

<a href="https://llm-vision.gitbook.io/getting-started"><img src="https://img.shields.io/badge/Documentation-blue?style=for-the-badge&logo=gitbook&logoColor=white&color=18bcf2"/></a>

Check [📖 Examples](https://llm-vision.gitbook.io/examples/) on how you can integrate llmvision into your Home Assistant setup or join the [🗨️ discussion](https://community.home-assistant.io/t/gpt-4o-vision-capabilities-in-home-assistant/729241) on the Home Assistant Community.

## Installation
[![Open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=valentinfrlch&repository=ha-llmvision&category=Integration)
1. Search for `LLM Vision` in Home Assistant Settings/Devices & services
2. Select your provider
3. Follow the instructions to add your AI providers.

Detailed instruction on how to set up LLM Vision and each of the supported providers are available here: https://llm-vision.gitbook.io/getting-started/


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

1. **New Provider**: NVIDIA ChatRTX 
2. **New Provider**: Custom (OpenAI API compatible) Providers
3. **Animation Support**: Support for animated GIFs
4. **HACS**: Include in HACS default
5. [x] ~~**Feature**: HTTPS support for LocalAI and Ollama~~
6. [x] ~~**Feature**: Support for video files~~  
7. [x] ~~**Feature**: Analyze Frigate Recordings using frigate's `event_id`~~


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
>[KBD]: https://github.com/valentinfrlch/ha-llmvision/issues/new/choose


## Support
You can support this project by starring this GitHub repository. If you want, you can also buy me a coffee here:  
<br>
<a href="https://www.buymeacoffee.com/valentinfrlch"><img width="15%" src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=☕&slug=valentinfrlch&button_colour=FFDD00&font_colour=000000&font_family=Inter&outline_colour=000000&coffee_colour=ffffff" /></a>
