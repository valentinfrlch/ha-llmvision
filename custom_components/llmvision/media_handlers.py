import base64
import io
import os
import shutil
import logging
from homeassistant.helpers.network import get_url
from PIL import Image
from homeassistant.exceptions import ServiceValidationError

_LOGGER = logging.getLogger(__name__)


class MediaProcessor:
    def __init__(self, hass, client):
        self.hass = hass
        self.client = client
        self.base64_images = []
        self.filenames = []

    async def resize_image(self, target_width, image_path=None, image_data=None, img=None):
        """Resize image to target_width"""
        loop = self.hass.loop
        if image_path:
            # Open the image file
            img = await loop.run_in_executor(None, Image.open, image_path)
            with img:
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                # Resize the image only if it's larger than the target size
                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                # Convert the image to base64
                base64_image = await self._encode_image(img)

        elif image_data:
            # Convert the image to base64
            img_byte_arr = io.BytesIO()
            img_byte_arr.write(image_data)
            img = await loop.run_in_executor(None, Image.open, img_byte_arr)
            with img:
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                base64_image = await self._encode_image(img)
        elif img:
            with img:
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                base64_image = await self._encode_image(img)

        return base64_image

    async def _encode_image(self, img):
        """Encode image as base64"""
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        base64_image = base64.b64encode(
            img_byte_arr.getvalue()).decode('utf-8')
        return base64_image

    async def add_images(self, image_entities, image_paths, target_width, include_filename):
        """Wrapper for client.add_image"""
        if image_entities:
            for image_entity in image_entities:
                try:
                    base_url = get_url(self.hass)
                    image_url = base_url + \
                        self.hass.states.get(image_entity).attributes.get(
                            'entity_picture')
                    image_data = await self.client._fetch(image_url)

                    # If entity snapshot requested, use entity name as 'filename'
                    if include_filename:
                        entity_name = self.hass.states.get(
                            image_entity).attributes.get('friendly_name')

                        self.client.add_image(
                            base64_image=await self.resize_image(target_width=target_width, image_data=image_data),
                            filename=entity_name
                        )
                    else:
                        self.client.add_image(
                            base64_image=await self.resize_image(target_width=target_width, image_data=image_data),
                            filename=""
                        )
                except AttributeError as e:
                    raise ServiceValidationError(
                        f"Entity {image_entity} does not exist")
        if image_paths:
            for image_path in image_paths:
                try:
                    image_path = image_path.strip()
                    if include_filename and os.path.exists(image_path):
                        self.client.add_image(
                            base64_image=await self.resize_image(target_width=target_width, image_path=image_path),
                            filename=image_path.split('/')[-1].split('.')[-2]
                        )
                    elif os.path.exists(image_path):
                        self.client.add_image(
                            base64_image=await self.resize_image(target_width=target_width, image_path=image_path),
                            filename=""
                        )
                    if not os.path.exists(image_path):
                        raise ServiceValidationError(
                            f"File {image_path} does not exist")
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")
        return self.client

    async def add_videos(self, video_paths, interval, target_width, include_filename):
        """Wrapper for client.add_image for videos"""
        if video_paths:
            _LOGGER.debug(f"Processing videos: {video_paths}")
            for video_path in video_paths:
                try:
                    video_path = video_path.strip()
                    if os.path.exists(video_path):
                        # extract frames from video every 'interval' seconds using ffmpeg
                        tmp_dir = "tmp_frames"
                        os.makedirs(tmp_dir, exist_ok=True)
                        _LOGGER.debug(
                            f"Created {tmp_dir} {os.path.exists(tmp_dir)}")
                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-i", video_path,
                            "-vf", f"fps=1/{interval},select='eq(n\,0)+not(mod(n\,{interval}))'",
                            os.path.join(tmp_dir, "frame%04d.png")
                        ]
                        # Run ffmpeg command
                        loop = self.hass.loop
                        await loop.run_in_executor(None, os.system, " ".join(ffmpeg_cmd))

                        frame_counter = 0
                        for frame_file in await loop.run_in_executor(None, os.listdir, tmp_dir):
                            _LOGGER.debug(f"Adding frame {frame_file}")
                            frame_counter = 0
                            frame_path = os.path.join(tmp_dir, frame_file)
                            self.client.add_image(
                                base64_image=await self.resize_image(image_path=frame_path, target_width=target_width),
                                filename=video_path.split(
                                    '/')[-1].split('.')[-2] + " (frame " + str(frame_counter) + ")" if include_filename else "Video frame " + str(frame_counter)
                            )
                            frame_counter += 1

                    if not os.path.exists(video_path):
                        raise ServiceValidationError(
                            f"File {video_path} does not exist")
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")

                # Clean up tmp dir
                await loop.run_in_executor(None, shutil.rmtree, tmp_dir)
            return self.client
