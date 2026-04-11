"""Unit tests for media_handlers.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from PIL import Image
import io
import base64
from custom_components.llmvision.media_handlers import MediaProcessor


class TestMediaProcessor:
    """Test MediaProcessor class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.loop = Mock()
        hass.loop.run_in_executor = AsyncMock()
        hass.states = Mock()
        hass.states.get = Mock()
        hass.config = Mock()
        hass.config.path = Mock(return_value="/mock/path")
        return hass

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        client = Mock()
        client.add_frame = Mock()
        return client

    @pytest.fixture
    def processor(self, mock_hass, mock_client):
        """Create a MediaProcessor instance."""
        with patch('custom_components.llmvision.media_handlers.async_get_clientsession'):
            return MediaProcessor(mock_hass, mock_client)

    def test_init(self, processor, mock_hass, mock_client):
        """Test MediaProcessor initialization."""
        assert processor.hass == mock_hass
        assert processor.client == mock_client
        assert processor.base64_images == []
        assert processor.filenames == []
        assert processor.key_frame == ""
        assert processor._candidate_frames == []

    @pytest.mark.asyncio
    async def test_encode_image(self, processor):
        """Test _encode_image method."""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        
        result = await processor._encode_image(img)
        
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify it's valid base64
        base64.b64decode(result)

    def test_convert_to_rgb_rgba(self, processor):
        """Test _convert_to_rgb with RGBA image."""
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        
        result = processor._convert_to_rgb(img)
        
        assert result.mode == 'RGB'

    def test_convert_to_rgb_already_rgb(self, processor):
        """Test _convert_to_rgb with RGB image."""
        img = Image.new('RGB', (100, 100), color='red')
        
        result = processor._convert_to_rgb(img)
        
        assert result.mode == 'RGB'

    @pytest.mark.asyncio
    async def test_resize_image_with_img(self, processor):
        """Test resize_image with PIL Image object."""
        # Create a test image
        img = Image.new('RGB', (200, 100), color='blue')
        
        result = await processor.resize_image(
            target_width=100,
            img=img
        )
        
        assert isinstance(result, str)
        assert len(result) > 0

    def test_similarity_score(self, processor):
        """Test _similarity_score method."""
        # Create two similar images
        img1 = Image.new('L', (100, 100), color=128)
        img2 = Image.new('L', (100, 100), color=130)

        score = processor._similarity_score(img1, img2)

        assert isinstance(score, float)
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_expose_keyframe_by_index(self, processor):
        """Test expose_keyframe_by_index calls _expose_image with correct data."""
        processor._candidate_frames = [
            ("camera0-frame-1", "base64data1", "camera0"),
            ("camera0-frame-2", "base64data2", "camera0"),
            ("camera0-frame-3", "base64data3", "camera0"),
        ]
        processor._expose_image = AsyncMock()

        await processor.expose_keyframe_by_index(1)

        processor._expose_image.assert_called_once()
        call_kwargs = processor._expose_image.call_args
        assert call_kwargs[1]["frame_name"] == "camera0"
        assert call_kwargs[1]["image_data"] == "base64data2"
        assert "uid" in call_kwargs[1]

    @pytest.mark.asyncio
    async def test_expose_keyframe_ssim_fallback(self, processor):
        """Test expose_keyframe_ssim_fallback runs SSIM and exposes winner."""
        # Create small test images as base64
        img1 = Image.new('RGB', (10, 10), color='red')
        img2 = Image.new('RGB', (10, 10), color='blue')
        img3 = Image.new('RGB', (10, 10), color='green')
        buffers = []
        for img in [img1, img2, img3]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            buffers.append(base64.b64encode(buf.getvalue()).decode("utf-8"))

        processor._candidate_frames = [
            ("cam-frame-1", buffers[0], "cam"),
            ("cam-frame-2", buffers[1], "cam"),
            ("cam-frame-3", buffers[2], "cam"),
        ]
        processor._expose_image = AsyncMock()

        await processor.expose_keyframe_ssim_fallback()

        # Should have called _expose_image exactly once
        processor._expose_image.assert_called_once()
        call_kwargs = processor._expose_image.call_args[1]
        assert call_kwargs["frame_name"] == "cam"

    @pytest.mark.asyncio
    async def test_expose_keyframe_ssim_fallback_empty_candidates(self, processor):
        """Test expose_keyframe_ssim_fallback is no-op when candidates empty."""
        processor._candidate_frames = []
        processor._expose_image = AsyncMock()

        await processor.expose_keyframe_ssim_fallback()

        processor._expose_image.assert_not_called()
