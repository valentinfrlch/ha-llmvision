<p align="center">
<img src="https://github.com/user-attachments/assets/bebd92b8-765e-4d63-bb3d-47e1bb8b51ad" width=500px>
</p>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badg>
<img src=https://img.shields.io/badge/version-1.3.5-blue>
<a href="https://github.com/valentinfrlch/ha-llmvision/issues">
<img src="https://img.shields.io/maintenance/yes/2025.svg">
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
    ·
    <a href="#support">☕ Support</a>    
  </p>

<br>
<div 
        style="
            display: flex; 
            justify-content: center; 
            align-items: center; 
        "
    >
        <div 
            style="
                display: inline-block; 
                padding: 7px 20px; 
                border: 1px solid rgba(255, 255, 255, 0.2); 
                border-radius: 20px; 
                color: #fff; 
                font-family: Arial, sans-serif; 
                font-size: 14px; 
                text-align: center; 
                cursor: pointer; 
                transition: background 0.3s ease, color 0.3s ease;
            " 
            onmouseover="this.style.border='2px solid rgba(255, 255, 255, 0.4)'" 
            onmouseout="this.style.border='1px solid rgba(255, 255, 255, 0.2)'"
        >
            See all Features
            <a 
                href="#" 
                style="
                    text-decoration: none; 
                    color: #8ab3ff; 
                    margin-left: 5px;
                " 
                onmouseover="this.style.textDecoration='underline'" 
                onmouseout="this.style.textDecoration='none'"
            >
                Visit Website →
            </a>
        </div>
    </div>

<br>
<br>
<p align="center">
  <strong>LLM Vision</strong> is a Home Assistant integration that can analyze images, videos,  
  live camera feeds and frigate events using the vision capabilities of multimodal LLMs.  
  Supported providers are OpenAI, Anthropic, Google Gemini, Groq, 
  <a href="https://github.com/mudler/LocalAI">LocalAI</a>, 
  <a href="https://ollama.com/">Ollama</a> and any OpenAI compatible API.
</p>

## Features
- Compatible with OpenAI, Anthropic Claude, Google Gemini, Groq, [LocalAI](https://github.com/mudler/LocalAI), [Ollama](https://ollama.com/) and custom OpenAI compatible APIs
- Analyzes images and video files, live camera feeds and Frigate events
- Remembers Frigate events and camera motion events so you can ask about them later
- Seamlessly updates sensors based on image input

## Blueprint
With the easy to use blueprint, you'll get important notifications intelligently summarized by AI from either Frigate or cameras in Home Assistant. LLM Vision can also remember events, so you can ask about them later. LLM Vision needs to be installed to use the blueprint.
<br>
<p float="left">
    <img src="https://github.com/user-attachments/assets/621dacc0-7f9b-4c7a-b490-94286dd19e86" width="400" />
    <img src="https://github.com/user-attachments/assets/8174c3cd-6314-4bfd-9fbe-d66316f93923" width="400" />
</p>

[Learn how to install the blueprint](https://llm-vision.gitbook.io/examples/examples/automations#ai-event-notifications)

## Resources
Check the docs for detailed instructions on how to set up LLM Vision and each of the supported providers, get inspiration from examples or join the discussion on the Home Assistant Community.

<a href="https://valentinfrlch.github.io/llmvision/"><img alt="Static Badge" src="https://img.shields.io/badge/website-teal?style=for-the-badge&&logoColor=white&link=https%3A%2F%2Fvalentinfrlch.github.io%2Fllmvision%2F"></a>
<a href="https://llm-vision.gitbook.io/getting-started"><img src="https://img.shields.io/badge/Documentation-blue?style=for-the-badge&logo=gitbook&logoColor=white&color=18bcf2"/> </a><a href="https://llm-vision.gitbook.io/examples/"><img src="https://img.shields.io/badge/Examples-blue?style=for-the-badge&logo=gitbook&logoColor=black&color=39ffc2"/></a> </a><a href="https://community.home-assistant.io/t/llm-vision-let-home-assistant-see/729241"><img src="https://img.shields.io/badge/Community-blue?style=for-the-badge&logo=homeassistant&logoColor=white&color=03a9f4"/></a>


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

1. **HACS**: Include in HACS default repository
2. **Providers**: Support for Azure

For features added in previous versions, check the changelogs in the release notes.


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
<a href="https://www.buymeacoffee.com/valentinfrlch"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=☕&slug=valentinfrlch&button_colour=FFDD00&font_colour=000000&font_family=Inter&outline_colour=000000&coffee_colour=ffffff" /></a>
