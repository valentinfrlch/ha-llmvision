<p align="center">
<img src="https://github.com/user-attachments/assets/bebd92b8-765e-4d63-bb3d-47e1bb8b51ad" width=500px>
</p>
<p align=center>
<img src=https://img.shields.io/badge/HACS-Default-orange.svg>
<img src="https://img.shields.io/maintenance/yes/2025.svg">
<img src=https://img.shields.io/badge/version-1.4.2-blue>
<img alt="Issues" src="https://img.shields.io/github/issues/valentinfrlch/ha-llmvision?color=0088ff">
<img alt="Static Badge" src="https://img.shields.io/badge/support-buymeacoffee?logo=buymeacoffee&logoColor=black&color=%23FFDD00&link=https%3A%2F%2Fbuymeacoffee.com%2Fvalentinfrlch">
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
    <a href="#how-to-report-a-bug-or-request-a-feature">🪲 How to report Bugs</a>
    ·
    <a href="#support">☕ Support</a>    
  </p>
<p align="center">
  <a href="https://llmvision.org"> Visit Website →</a>
    </p>
<br>
<br>
<p align="center">
    <strong>LLM Vision</strong> is a Home Assistant integration that uses multimodal large language models to analyze images, videos, live camera feeds, and Frigate events. It can also keep track of analyzed events in a timeline, with an optional Timeline Card for your dashboard.
</p>

## Features
- Compatible with OpenAI, Anthropic Claude, Google Gemini, AWS Bedrock, Groq, [LocalAI](https://github.com/mudler/LocalAI), [Ollama](https://ollama.com/), [Open WebUI](https://github.com/open-webui/open-webui) and providers with OpenAI compatible enpoints.
- Analyzes images and video files, live camera feeds and Frigate events
- Can remembers people, pets and objects
- Maintains a timeline of camera events, so you can display them on your dashboard as well as ask about them later
- Seamlessly updates sensors based on image input

<br>

See the [website](https://llmvision.org) for the latest features as well as examples.
![features](https://github.com/user-attachments/assets/5edd11d6-79b9-4736-9387-8d22405c53b8)

<br>

## Blueprint
With the easy to use blueprint, you'll get camera event notifications intelligently summarized by AI. LLM Vision can also store events in a timeline, so you can see what happened on your dashboard.
<br>
<p float="left">
    <img src="https://github.com/user-attachments/assets/621dacc0-7f9b-4c7a-b490-94286dd19e86" width="400" />
    <img src="https://github.com/user-attachments/assets/8174c3cd-6314-4bfd-9fbe-d66316f93923" width="400" />
</p>

[Learn how to install the blueprint](https://llm-vision.gitbook.io/getting-started/setup/blueprint)

## Resources
Check the docs for detailed instructions on how to set up LLM Vision and each of the supported providers, get inspiration from examples or join the discussion on the Home Assistant Community.

<a href="https://llmvision.org"><img alt="Static Badge" src="https://img.shields.io/badge/website-teal?style=for-the-badge&&logoColor=white&link=https%3A%2F%2Fvalentinfrlch.github.io%2Fllmvision%2F"></a>
<a href="https://llm-vision.gitbook.io/getting-started"><img src="https://img.shields.io/badge/Documentation-blue?style=for-the-badge&logo=gitbook&logoColor=white&color=18bcf2"/> </a><a href="https://llmvision.org/gallery/"><img src="https://img.shields.io/badge/Examples-blue?style=for-the-badge&logo=gitbook&logoColor=black&color=39ffc2"/></a> </a><a href="https://community.home-assistant.io/t/llm-vision-let-home-assistant-see/729241"><img src="https://img.shields.io/badge/Community-blue?style=for-the-badge&logo=homeassistant&logoColor=white&color=03a9f4"/></a>

For technical questions see the discussions tab.


## Installation
>[!TIP]
>LLM Vision is available in the default HACS repository. You can install it directly through HACS or click the button below to open it there.

[![Open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=valentinfrlch&repository=ha-llmvision&category=Integration)
1. Install `LLM Vision` from HACS
2. Search for `LLM Vision` in Home Assistant Settings/Devices & services
3. Select your provider
4. Follow the instructions to add your AI providers.

Continue with setup here: https://llm-vision.gitbook.io/getting-started/setup/providers

## How to report a bug or request a feature
> [!IMPORTANT]
> **Bugs:** If you encounter any bugs and have followed the instructions carefully, file a bug report. Please check open issues first and include debug logs in your report. Debugging can be enabled on the integration's settings page.
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
