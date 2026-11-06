# LLM Vision 项目中文导读

这份文档不是逐字翻译，而是帮助中文用户快速看懂 `valentinfrlch/ha-llmvision` 这个项目：它解决什么问题、怎么安装、有哪些服务、代码结构如何，以及调试和贡献时该从哪里开始。

## 这个项目是什么

LLM Vision 是一个 Home Assistant 自定义集成。它把摄像头、图片、视频和 Frigate 事件交给多模态大模型分析，然后把结果返回给 Home Assistant 自动化、通知、传感器或时间线。

你可以把它理解为：

- 给智能家居接入“看图/看视频”的 AI 能力。
- 让摄像头通知不只是“检测到移动”，而是“门口有人放下包裹”。
- 让 Home Assistant 把分析结果保存为事件时间线，后续可以回看或查询。
- 让 AI 从画面中提取结构化数据，例如车辆数量、是否有人、包裹是否到达等。

## 适合的使用场景

- 门铃或门口摄像头通知：识别访客、快递、车辆、宠物。
- Frigate 事件总结：把 Frigate 检测到的事件交给 AI 描述。
- 摄像头时间线：把关键事件存下来，在仪表盘中查看。
- 状态传感器更新：从图片中提取数据，然后更新 `number`、`input_text`、`input_boolean`、`select` 等实体。
- 本地模型实验：通过 Ollama、LocalAI、Open WebUI 使用本地视觉模型。

## 支持的 AI 提供商

代码中支持这些提供商：

- OpenAI
- Azure OpenAI
- Anthropic
- Google Gemini
- Groq
- LocalAI
- Ollama
- Custom OpenAI endpoint
- AWS Bedrock
- Open WebUI
- OpenRouter

默认模型在 `custom_components/llmvision/const.py` 中定义。比如 OpenAI 默认是 `gpt-4o-mini`，Ollama 默认是 `gemma3:4b`，AWS Bedrock 默认是 `us.amazon.nova-pro-v1:0`。实际使用时，你可以在集成配置里改成自己想用的模型。

## 安装流程

最简单的方式是通过 HACS：

1. 在 HACS 中搜索并安装 `LLM Vision`。
2. 重启 Home Assistant。
3. 打开“设置 / 设备与服务”，添加 `LLM Vision`。
4. 先提交默认 Settings 配置。
5. 确保 Home Assistant 有可用的 `/media` 目录，因为快照会保存到 `/media/llmvision/snapshots`。
6. 回到 LLM Vision 集成页面，点击 `Add Entry` 添加 AI 提供商。
7. 在自动化或脚本中调用 LLM Vision 的服务。

官方文档入口：

- 安装与提供商配置：https://llm-vision.gitbook.io/getting-started/setup/providers
- Blueprint 配置：https://llm-vision.gitbook.io/getting-started/setup/blueprint
- 示例：https://llmvision.org/gallery/

## 主要服务

服务定义在 `custom_components/llmvision/services.yaml`。

### `llmvision.image_analyzer`

分析图片或摄像头快照。

常用字段：

- `provider`：要使用的 AI 提供商配置。
- `model`：可选，不填时使用该提供商的默认模型。
- `message`：提示词，例如“描述图片中发生了什么”。
- `image_file`：本地图片路径。
- `image_entity`：Home Assistant 中的 `image` 或 `camera` 实体。
- `store_in_timeline`：是否把结果保存到时间线。
- `use_memory`：是否启用记忆上下文。
- `response_format`：`text` 返回自然语言，`json` 返回结构化数据。
- `structure`：当 `response_format` 为 `json` 时使用的 JSON Schema。

### `llmvision.video_analyzer`

分析视频文件或 Frigate 事件。

常用字段：

- `video_file`：一个或多个本地视频路径或 URL，多条用换行分隔。
- `event_id`：Frigate 事件 ID。
- `max_frames`：最多抽取多少帧分析。项目会优先选择运动最明显的帧。
- 其他字段与图片分析类似。

### `llmvision.stream_analyzer`

录制一小段实时摄像头流，再交给 AI 分析。

常用字段：

- `image_entity`：要分析的 `camera` 实体。
- `duration`：录制秒数，默认 5 秒，范围 1 到 60 秒。
- `max_frames`：最多抽取多少帧分析。
- 其他字段与图片分析类似。

### `llmvision.data_analyzer`

从图片中提取数据，并更新 Home Assistant 实体。这个服务在项目中标注为 Beta。

可更新的实体类型包括：

- `number`
- `input_number`
- `text`
- `input_text`
- `input_boolean`
- `select`
- `input_select`

示例提示词可以是：“停车位里有几辆车？”或“门口是否有包裹？”。

### `llmvision.create_event`

手动创建一条 LLM Vision 时间线事件。

常用字段：

- `title`：事件标题。
- `description`：事件描述。
- `label`：事件标签，如 Person、Car、Package。
- `image_path`：事件图片，必须位于 `/media/llmvision/snapshots/`。
- `camera_entity`：关联摄像头。
- `start_time` / `end_time`：事件起止时间。

### `llmvision.get_events`

从 LLM Vision 时间线中查询事件。

可按这些条件过滤：

- 起止时间
- 摄像头实体
- 分类，例如 Person、Vehicle、Animal、Package
- 标签，例如 Car、Dog、Door、Package
- 返回数量上限
- 是否包含标题为“无活动”的事件

## 重要配置概念

### Provider

Provider 是 AI 服务商配置。你可以配置多个 Provider，例如一个 OpenAI、一个 Ollama、一个 OpenRouter，然后在服务调用里选择要用哪一个。

### Fallback Provider

Settings 中可以设置备用提供商。如果当前提供商失败，代码会尝试用备用提供商重新请求。

### Memory

Memory 用于给模型补充人物、宠物、物体等上下文。比如你可以提供一张宠物照片和描述“这是我的狗 Cookie”，后续分析摄像头画面时模型就更容易识别它。

### Timeline

Timeline 是项目自己的事件时间线。服务可以把 AI 分析结果保存成事件，之后通过卡片展示，或通过 `get_events` 查询。

### Structured Output

如果你想让 AI 返回稳定的 JSON，而不是一段自然语言，可以设置：

- `response_format: json`
- `structure`: JSON Schema
- `title_field`：JSON 中作为事件标题的字段名
- `description_field`：JSON 中作为事件描述的字段名

这适合自动化场景，例如让模型只返回：

```json
{
  "title": "Package delivered",
  "description": "A person leaves a package near the front door.",
  "confidence": 92
}
```

## 项目结构

- `custom_components/llmvision/`：Home Assistant 集成主体代码。
- `custom_components/llmvision/__init__.py`：集成加载、服务注册和核心入口。
- `custom_components/llmvision/config_flow.py`：Home Assistant 配置向导。
- `custom_components/llmvision/providers.py`：不同 AI 提供商的请求封装。
- `custom_components/llmvision/media_handlers.py`：图片、视频、摄像头流处理。
- `custom_components/llmvision/timeline.py`：事件时间线逻辑。
- `custom_components/llmvision/calendar.py`：时间线和日历相关逻辑。
- `custom_components/llmvision/memory.py`：记忆功能。
- `custom_components/llmvision/api.py`：API 相关逻辑。
- `custom_components/llmvision/services.yaml`：暴露给 Home Assistant 的服务定义。
- `custom_components/llmvision/translations/`：集成配置界面的多语言翻译。
- `custom_components/llmvision/timeline_strings/`：时间线标签和文本的多语言内容。
- `blueprints/`：Home Assistant 自动化蓝图。
- `tests/`：单元测试和集成测试。
- `benchmark_visualization/`：模型基准测试可视化相关文件。

## 开发和测试

项目要求 Python 3.13。测试依赖写在 `requirements-test.txt`。

快速测试流程：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-test.txt
pytest tests/ -m "not integration" -v
```

Linux 或 macOS 下激活虚拟环境的命令是：

```bash
source .venv/bin/activate
```

集成测试位于 `tests/test_api.py`，需要运行中的 Home Assistant 实例，并在 `tests/.instance` 和 `tests/.token` 中配置地址和长期访问令牌。没有这些文件时，集成测试会自动跳过。

## 隐私说明简译

项目的隐私策略大意如下：

- 网站使用 Google Analytics 了解访问情况。
- Home Assistant 集成本身没有遥测或追踪机制。
- 项目作者不会收到你的使用数据、配置、Home Assistant 数据、Provider 配置或下载统计。
- 图片、视频和事件的处理发生在你的 Home Assistant 环境中，并按照你配置的 AI 提供商发送请求。
- 如果你使用云端 AI 提供商，图片或视频帧会按该提供商的 API 请求方式发送给对应服务商。

## 贡献说明简译

如果要贡献代码：

- 先查看 beta 分支和其他分支，避免重复做已经存在的修复或功能。
- Fork 仓库后新建分支开发。
- 保持改动聚焦，一个 PR 尽量只做一个功能或修复。
- 遵循现有代码风格，必要时添加注释和类型提示。
- 提交前运行测试，并最好在真实 Home Assistant 实例中验证。
- Bug 和功能请求请走 GitHub Issues。
- 项目接受使用 AI 辅助调试，但不接受完全由 AI 生成、贡献者自己没有理解的 PR。

## 阅读代码时的建议顺序

1. 先读 `README.zh-CN.md` 和这份导读，了解项目用途。
2. 再读 `services.yaml`，理解 Home Assistant 用户能调用哪些服务。
3. 看 `config_flow.py`，了解每个 Provider 如何配置。
4. 看 `providers.py`，理解请求如何发到 OpenAI、Gemini、Ollama 等服务。
5. 看 `media_handlers.py`，了解图片、视频和摄像头流如何被处理成模型输入。
6. 看 `timeline.py` 和 `memory.py`，理解时间线和记忆功能。
7. 最后看 `tests/`，用测试反推核心行为。

## 一句话总结

LLM Vision 是把“多模态大模型视觉理解”接到 Home Assistant 里的桥梁：它负责拿到摄像头或媒体输入，整理成模型能理解的请求，拿回结果，再把结果变成通知、传感器数据或时间线事件。
