# GPT-4 Turbo with vision Service for Home Assistant
Image Analyzer using GPT-4 Turbo with vision and Home Assistant

**ha-gpt4vision** creates the gpt4vision.image_analyzer service in Home Assistant.
This service uploads an image to OpenAI using its API and return analysis from AI directly to selected TTS service and speaker devices inside Home Assistant.

Based on the **HA-chatgtp** code ( https://github.com/MiguelQueiroz/HA-chatgtp ) with the necessary adaptations to work with GPT-4 Turbo with vision API and with the inclusion of the image file reading and conversion to base64.

## Note about API key
**This service needs a valid API key**. You must obtain a valid OpenAI key capable of using the GPT-4 Turbo model.
Currently, the gpt-4-vision-preview model that is available with image analysis capabilities has costs that can be high. Please check your usage limits and take this into consideration when testing this service.

## Install and setup
1. Download and copy folder **gpt4vision** to your **custom_components** folder.
2. Add the following code to your configuration.yaml 
```ruby
# gpt4vision service setup
gpt4vision:
  api: "[Your OpenAI API key]"
  tts: "[The HA TTS service you want to use for text-to-speech]"
# Example tts: "cloud_say"
```
3. Restart Home Assistant to load the gpt4vision custom_component.

## Service call and usage
After restart, the gpt4vision.image_analyzer service will be available.
To get AI analysis of a local image, use the following service call.

```ruby
service: gpt4vision.image_analyzer
data:
  message: '[Prompt message for AI]'
  max_tokens: [maximum number of tokens]
  entity_id: [media device]
  image_file: '[path for image file]'
```
The parameters ```message:```, ```max_tokens:```, ```entity_id:``` and ```image_file:``` are mandatory for the execution of the service.
Optionally, the AI model and the TTS cache [true/false] can be set.
```
data:
  model: gpt-4-vision-preview
  cache: true
```

### Example 1
Image analysis of a paint, with jpeg file saved in the HA folder /config/www/images/, using OpenAI GPT-4 Turbo with vision model with 50 tokens, Home Assistant tts.cloud_say without cache. Answer will be sent to a group of speakers.
```
service: gpt4vision.image_analyzer
data:
  message: 'describe the painting'
  image_file: '/config/www/images/art.jpg'
  entity_id: media_player.speakers_cast_group
  model: gpt-4-vision-preview
  max_tokens: 50
  cache: false  
```
### Example 2
Image analysis of a surveillance video frame when someone ring the doorbell.
The automation is triggered by the doorbell binary sensor. Then, a snapshot is taken from a surveillance camera and the file is saved locally as /config/www/images/doorbell_snapshot.jpg
The response text will be converted to speech (TTS) and listen in the kitchen's google nest mini speaker.
```
service: camera.snapshot
data:
  filename: /config/www/images/doorbell_snapshot.jpg
target:
  entity_id:
    - camera.outdoor_front
```
With the snapshot ready and file saved, it's time to call image_analyzer service.
```
service: gpt4vision.image_analyzer
data:
  message: >-
    This photo was obtained from a home surveillance camera.
    Write a succinct description of the person in the photo.
  max_tokens: 300
  entity_id: media_player.google_nest_mini_kitchen
  image_file: '/config/www/images/doorbell_snapshot.jpg'
```

## Other uses
After successful processing, the content of the AI ​​analysis response is saved as text in response.txt file. This file is stored inside the /custom_components/gpt4vision/ folder.
This functionality can be useful for debugging and testing, or for passing content to other services.
