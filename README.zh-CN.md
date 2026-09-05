<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./logos/dark_logo@2x.png">
  <img alt="LLM Vision Logo" src="./logos/logo@2x.png" width="512">
</picture>
</p>

<h2 align="center">给你的智能家居加上视觉智能</h2>

<p align="center">
  <a href="#功能">功能</a>
  ·
  <a href="#快速开始">快速开始</a>
  ·
  <a href="#blueprint-自动化蓝图">Blueprint 自动化蓝图</a>
  ·
  <a href="#资源">资源</a>
  ·
  <a href="#如何反馈问题或请求新功能">反馈问题</a>
  ·
  <a href="#支持项目">支持项目</a>
</p>

<p align="center">
  <a href="https://llmvision.org">访问官方网站</a>
</p>

**LLM Vision** 是一个 Home Assistant 自定义集成。它使用多模态大语言模型分析图片、视频、实时摄像头画面和 Frigate 事件。它还可以把分析过的事件保存到时间线中，并可配合可选的 Timeline Card 在 Home Assistant 仪表盘上展示。

## 功能

- 支持 OpenRouter、OpenAI、Anthropic、Google Gemini、AWS Bedrock、Azure、Groq、[Ollama](https://ollama.com/)、[Open WebUI](https://github.com/open-webui/open-webui)、[LocalAI](https://github.com/mudler/LocalAI)，以及任何兼容 OpenAI 接口格式的提供商。
- 可以根据你的提示词回答问题，或描述图片、视频文件、实时摄像头画面和 Frigate 事件。
- 可以记住人物、宠物和物体，为之后的分析提供上下文。
- 可以保存摄像头事件时间线，让你在仪表盘上查看发生了什么，也可以让 Home Assistant Assist 查询这些事件。
- 可以从摄像头流、图片或视频中提取数据，并自动更新传感器。

更多最新功能和示例请查看 [官方网站](https://llmvision.org)。

## 快速开始

> 提示：LLM Vision 已包含在默认 HACS 仓库中。你可以直接通过 HACS 安装，或点击下面的按钮在 Home Assistant 中打开。

[![在 Home Assistant Community Store 中打开仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=valentinfrlch&repository=ha-llmvision&category=Integration)

1. 在 HACS 中安装 `LLM Vision`。
2. 重启 Home Assistant。
3. 在 Home Assistant 的“设置 / 设备与服务”中搜索 `LLM Vision`。
4. 点击提交，使用默认设置继续安装。
5. 设置媒体文件夹。LLM Vision 使用更安全的 `/media` 文件夹保存快照。如果你运行的是 Home Assistant Container，可能需要在容器配置中把某个文件夹挂载到 `/media`。更多细节请看官方文档。
6. 回到 LLM Vision 集成页面。
7. 点击 `Add Entry` 添加第一个 AI 提供商。

详细安装说明和文档见：[LLM Vision Documentation](https://llm-vision.gitbook.io/getting-started/setup/providers)。

## Blueprint 自动化蓝图

项目提供了易用的 Blueprint。通过它，你可以让摄像头事件通知自动由 AI 智能总结。LLM Vision 也可以把事件存入时间线，方便你在仪表盘上回看发生了什么。

学习如何安装蓝图：[Blueprint 安装说明](https://llm-vision.gitbook.io/getting-started/setup/blueprint)。

## 资源

如果你需要更详细的安装教程、各个 AI 提供商的配置方式、示例自动化，或想参与讨论，可以参考这些入口：

- 官方网站：[llmvision.org](https://llmvision.org)
- 文档：[Getting Started](https://llm-vision.gitbook.io/getting-started)
- 示例：[Gallery](https://llmvision.org/gallery/)
- Discord：[加入讨论](https://discord.gg/wuFeMfCMRB)
- Home Assistant 社区帖：[LLM Vision: Let Home Assistant See](https://community.home-assistant.io/t/llm-vision-let-home-assistant-see/729241)

技术问题建议优先查看 GitHub Discussions。

## 如何反馈问题或请求新功能

**反馈 Bug：** 如果你已经认真按照说明操作，但仍遇到问题，请提交 Bug 报告。提交前请先检查现有 Issue，并在报告中附上调试日志。调试日志可以在集成设置页面中开启。

**请求新功能：** 如果你有功能想法，可以创建 Feature Request。

提交入口：[Create new issue](https://github.com/valentinfrlch/ha-llmvision/issues/new/choose)。

## 支持项目

你可以通过给这个 GitHub 仓库点 Star 来支持项目。也可以通过 Buy Me a Coffee 支持作者：

[Buy me a coffee](https://buymeacoffee.com/llmvision)
