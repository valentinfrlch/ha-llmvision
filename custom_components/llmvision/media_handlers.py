import base64
import io
import os
import shutil
import logging
from homeassistant.helpers.network import get_url
from PIL import Image
from homeassistant.exceptions import ServiceValidationError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MediaProcessor:
    def __init__(self, hass, client):
        self.hass = hass
        self.client = client
        self.base64_images = []
        self.filenames = []

    async def _encode_image(self, img):
        """Encode image as base64"""
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        base64_image = base64.b64encode(
            img_byte_arr.getvalue()).decode('utf-8')
        return base64_image

    def _save_clip(self, clip_data, clip_path):
        with open(clip_path, "wb") as f:
            f.write(clip_data)

    def _convert_to_rgb(self, img):
        if img.mode == 'RGBA' or img.format == 'GIF':
            img = img.convert('RGB')
        return img

    async def resize_image(self, target_width, image_path=None, image_data=None, img=None):
        """Resize image to target_width"""
        if image_path:
            # Open the image file
            img = await self.hass.loop.run_in_executor(None, Image.open, image_path)
            with img:
                # Check if the image is a GIF and convert if necessary
                _LOGGER.debug(f"Image format: {img.format}")
                img = self._convert_to_rgb(img)
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                # Resize the image only if it's larger than the target size
                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                # Encode the image to base64
                base64_image = await self._encode_image(img)

        elif image_data:
            # Convert the image to base64
            img_byte_arr = io.BytesIO()
            img_byte_arr.write(image_data)
            img = await self.hass.loop.run_in_executor(None, Image.open, img_byte_arr)
            with img:
                _LOGGER.debug(f"Image format: {img.format}")
                img = self._convert_to_rgb(img)
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                base64_image = await self._encode_image(img)
        elif img:
            with img:
                img = self._convert_to_rgb(img)
                # calculate new height based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                base64_image = await self._encode_image(img)

        return base64_image

    async def record(self, image_entities, duration, interval, target_width, include_filename):
        """Wrapper for client.add_frame with integrated recorder

        Args:
            image_entities (list[string]): List of camera entities to record
            duration (float): Duration in seconds to record
            target_width (int): Target width for the images in pixels
        """
        import time
        import asyncio

        camera_frames = {}

        # Record on a separate thread for each camera
        async def record_camera(image_entity, camera_number):
            start = time.time()
            frame_counter = 0
            frames = {}
            while time.time() - start < duration:
                base_url = get_url(self.hass)
                frame_url = base_url + \
                    self.hass.states.get(image_entity).attributes.get(
                        'entity_picture')
                frame_data = await self.client._fetch(frame_url)

                # use either entity name or assign number to each camera
                frames.update({image_entity.replace(
                    "camera.", "") + " frame " + str(frame_counter) if include_filename else "camera " + str(camera_number) + " frame " + str(frame_counter): frame_data})

                frame_counter += 1

                await asyncio.sleep(interval)
            camera_frames.update({image_entity: frames})

        _LOGGER.info(f"Recording {', '.join([entity.replace(
            'camera.', '') for entity in image_entities])} for {duration} seconds")

        # start threads for each camera
        await asyncio.gather(*(record_camera(image_entity, image_entities.index(image_entity)) for image_entity in image_entities))

        # add frames to client
        for frame in camera_frames:
            for frame_name in camera_frames[frame]:
                self.client.add_frame(
                    base64_image=await self.resize_image(target_width=target_width, image_data=camera_frames[frame][frame_name]),
                    filename=frame_name
                )

    async def add_images(self, image_entities, image_paths, target_width, include_filename):
        """Wrapper for client.add_frame for images"""
        if image_entities:
            for image_entity in image_entities:
                try:
                    base_url = get_url(self.hass)
                    image_url = base_url + \
                        self.hass.states.get(image_entity).attributes.get(
                            'entity_picture')
                    image_data = await self.client._fetch(image_url)

                    # If entity snapshot requested, use entity name as 'filename'
                    self.client.add_frame(
                        base64_image=await self.resize_image(target_width=target_width, image_data=image_data),
                        filename=self.hass.states.get(
                            image_entity).attributes.get('friendly_name') if include_filename else ""
                    )

                except AttributeError as e:
                    raise ServiceValidationError(
                        f"Entity {image_entity} does not exist")
        if image_paths:
            for image_path in image_paths:
                try:
                    image_path = image_path.strip()
                    if include_filename and os.path.exists(image_path):
                        self.client.add_frame(
                            base64_image=await self.resize_image(target_width=target_width, image_path=image_path),
                            filename=image_path.split('/')[-1].split('.')[-2]
                        )
                    elif os.path.exists(image_path):
                        self.client.add_frame(
                            base64_image=await self.resize_image(target_width=target_width, image_path=image_path),
                            filename=""
                        )
                    if not os.path.exists(image_path):
                        raise ServiceValidationError(
                            f"File {image_path} does not exist")
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")
        return self.client

    async def add_videos(self, video_paths, event_ids, interval, target_width, include_filename):
        """Wrapper for client.add_frame for videos"""
        tmp_clips_dir = f"/config/custom_components/{DOMAIN}/tmp_clips"
        tmp_frames_dir = f"/config/custom_components/{DOMAIN}/tmp_frames"
        if not video_paths:
            video_paths = []
        if event_ids:
            for event_id in event_ids:
                try:
                    base_url = get_url(self.hass)
                    frigate_url = base_url + "/api/frigate/notifications/" + event_id + "/clip.mp4"
                    clip_data = await self.client._fetch(frigate_url)
                    # create tmp dir to store video clips
                    os.makedirs(tmp_clips_dir, exist_ok=True)
                    _LOGGER.info(f"Created {tmp_clips_dir}")
                    # save clip to file with event_id as filename
                    clip_path = os.path.join(
                        tmp_clips_dir, event_id.split("-")[-1] + ".mp4")
                    await self.hass.loop.run_in_executor(None, self._save_clip, clip_data, clip_path)
                    _LOGGER.info(
                        f"Saved frigate clip to {clip_path} (temporarily)")
                    # append to video_paths
                    video_paths.append(clip_path)

                except AttributeError as e:
                    raise ServiceValidationError(
                        f"Failed to fetch frigate clip {event_id}: {e}")
        if video_paths:
            _LOGGER.debug(f"Processing videos: {video_paths}")
            for video_path in video_paths:
                try:
                    video_path = video_path.strip()
                    if os.path.exists(video_path):
                        # create tmp dir to store extracted frames
                        os.makedirs(tmp_frames_dir, exist_ok=True)
                        if os.path.exists(tmp_frames_dir):
                            _LOGGER.debug(f"Created {tmp_frames_dir}")
                        else:
                            _LOGGER.error(
                                f"Failed to create temp directory {tmp_frames_dir}")

                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-i", video_path,
                            "-vf", f"fps=1/{interval},select='eq(n\\,0)+not(mod(n\\,{interval}))'", os.path.join(
                                tmp_frames_dir, "frame%04d.jpg")
                        ]
                        # Run ffmpeg command
                        await self.hass.loop.run_in_executor(None, os.system, " ".join(ffmpeg_cmd))

                        frame_counter = 0
                        for frame_file in await self.hass.loop.run_in_executor(None, os.listdir, tmp_frames_dir):
                            _LOGGER.debug(f"Adding frame {frame_file}")
                            frame_counter = 0
                            frame_path = os.path.join(
                                tmp_frames_dir, frame_file)

                            # Remove transparency for compatibility
                            with Image.open(frame_path) as img:
                                if img.mode == 'RGBA':
                                    img = img.convert('RGB')
                                    img.save(frame_path)

                            self.client.add_frame(
                                base64_image=await self.resize_image(image_path=frame_path, target_width=target_width),
                                filename=video_path.split(
                                    '/')[-1].split('.')[-2] + " (frame " + str(frame_counter) + ")" if include_filename else "Video frame " + str(frame_counter)
                            )
                            frame_counter += 1
                    else:
                        raise ServiceValidationError(
                            f"File {video_path} does not exist")
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")

        # Clean up tmp dirs
        try:
            await self.hass.loop.run_in_executor(None, shutil.rmtree, tmp_clips_dir)
            _LOGGER.info(
                f"Deleted tmp folder: {tmp_clips_dir}")
        except FileNotFoundError as e:
            _LOGGER.error(f"Failed to delete tmp folder: {e}")
        try:
            await self.hass.loop.run_in_executor(None, shutil.rmtree, tmp_frames_dir)
            _LOGGER.info(
                f"Deleted tmp folder: {tmp_frames_dir}")
        except FileNotFoundError as e:
            _LOGGER.error(f"Failed to delete tmp folders: {e}")
        return self.client

    async def add_streams(self, image_entities, duration, interval, target_width, include_filename):
        if image_entities:
            await self.record(image_entities, duration, interval, target_width, include_filename)
        return self.client
