import base64
import io
from PIL import Image

class MediaProcessor:
    def __init__(self, hass):
        self.hass = hass
    async def encode_image(self, target_width, image_path=None, image_data=None):
        """Encode image as base64

        Args:
            image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

        Returns:
            string: image encoded as base64
        """
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
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                base64_image = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

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

                img.save(img_byte_arr, format='JPEG')
                base64_image = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

        return base64_image
        
