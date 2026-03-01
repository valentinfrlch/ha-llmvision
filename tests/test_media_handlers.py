"""Unit tests for media_handlers.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from PIL import Image
import numpy as np
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
    async def test_record_selects_frames_in_chronological_order(self, mock_hass, mock_client):
        """Verify that stream frames are sent to the LLM in chronological order.

        The SSIM-based selection picks frames with the most visual change,
        but the result must still be ordered by capture time so the LLM
        can understand the temporal sequence of events.
        """
        async def run_in_executor(_, fn, *args):
            return fn(*args)
        mock_hass.loop.run_in_executor = run_in_executor

        with patch('custom_components.llmvision.media_handlers.async_get_clientsession'):
            processor = MediaProcessor(mock_hass, mock_client)

        # 5 frames with brightness chosen so consecutive-SSIM sort ≠ chronological:
        #   frame1(126 vs 128): SSIM ≈ 0.999  (nearly identical)
        #   frame2(0   vs 126): SSIM ≈ 0.0001 (huge jump)
        #   frame3(255 vs 0  ): SSIM ≈ 0.00003
        #   frame4(64  vs 255): SSIM ≈ 0.47
        # SSIM ascending → frame3, frame2, frame4, frame1 (not chronological)
        brightness_levels = [128, 126, 0, 255, 64]
        jpeg_frames = []
        for lvl in brightness_levels:
            img = Image.new('L', (64, 64), color=lvl)
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            jpeg_frames.append(buf.getvalue())

        state = Mock()
        state.attributes = {'entity_picture': '/api/camera/test'}
        mock_hass.states.get.return_value = state

        fetch_idx = {'n': 0}

        async def mock_fetch(url, **kwargs):
            i = fetch_idx['n']
            fetch_idx['n'] += 1
            return jpeg_frames[i] if i < len(jpeg_frames) else None
        processor._fetch = mock_fetch

        async def mock_resize(target_width, image_data=None, **kwargs):
            return base64.b64encode(image_data).decode() if image_data else ""
        processor.resize_image = mock_resize

        processor._select_keyframe_index = AsyncMock(return_value=0)
        processor._expose_image = AsyncMock()

        # 28 time.time() calls for 5 loop iterations (duration=4, interval=2)
        # start(1) + iter0(6, includes iteration_time) + iter1-4(5 each) + exit(1)
        time_values = [
            0.0,                            # start
            0.0, 0.0, 0.1, 0.1, 0.2, 0.2,  # iter 0 (first frame) + iteration_time
            1.0, 1.0, 1.1, 1.1, 1.2,       # iter 1
            2.0, 2.0, 2.1, 2.1, 2.2,       # iter 2
            3.0, 3.0, 3.1, 3.1, 3.2,       # iter 3
            4.0, 4.0, 4.1, 4.1, 4.2,       # iter 4
            5.0,                            # exit check
        ]

        with patch('custom_components.llmvision.media_handlers.time') as mock_time, \
             patch('custom_components.llmvision.media_handlers.get_url', return_value='http://fake'), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            mock_time.time = Mock(side_effect=time_values)

            await processor.record(
                image_entities=['camera.test'],
                duration=4,
                max_frames=5,
                target_width=640,
                include_filename=False,
                expose_images=False,
            )

        calls = mock_client.add_frame.call_args_list
        filenames = [c.kwargs['filename'] for c in calls]
        frame_numbers = [int(name.rsplit('-', 1)[-1]) for name in filenames]

        assert frame_numbers == [0, 1, 2, 3, 4], \
            f"Frames must be in chronological order, got: {filenames}"

    @pytest.mark.asyncio
    async def test_record_keyframe_uses_first_frame_as_reference(self, mock_hass, mock_client):
        """Keyframe selection must compare candidates against the first frame.

        The first frame is the closest to "before the event" since recording
        starts on the motion trigger. The frame most different from this
        baseline is the best notification snapshot.
        """
        async def run_in_executor(_, fn, *args):
            return fn(*args)
        mock_hass.loop.run_in_executor = run_in_executor

        with patch('custom_components.llmvision.media_handlers.async_get_clientsession'):
            processor = MediaProcessor(mock_hass, mock_client)

        # Frame 0 (brightness 128) = baseline before motion
        # Frame 4 (brightness 64)  = last frame
        # If reference is first frame → mean ≈ 128
        # If reference is last frame → mean ≈ 64
        brightness_levels = [128, 126, 0, 255, 64]
        jpeg_frames = []
        for lvl in brightness_levels:
            img = Image.new('L', (64, 64), color=lvl)
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            jpeg_frames.append(buf.getvalue())

        state = Mock()
        state.attributes = {'entity_picture': '/api/camera/test'}
        mock_hass.states.get.return_value = state

        fetch_idx = {'n': 0}

        async def mock_fetch(url, **kwargs):
            i = fetch_idx['n']
            fetch_idx['n'] += 1
            return jpeg_frames[i] if i < len(jpeg_frames) else None
        processor._fetch = mock_fetch

        async def mock_resize(target_width, image_data=None, **kwargs):
            return base64.b64encode(image_data).decode() if image_data else ""
        processor.resize_image = mock_resize

        captured_ref = {}

        async def spy_select_keyframe(ref_bytes, candidates):
            captured_ref['bytes'] = ref_bytes
            return 0
        processor._select_keyframe_index = spy_select_keyframe
        processor._expose_image = AsyncMock()

        time_values = [
            0.0,
            0.0, 0.0, 0.1, 0.1, 0.2, 0.2,
            1.0, 1.0, 1.1, 1.1, 1.2,
            2.0, 2.0, 2.1, 2.1, 2.2,
            3.0, 3.0, 3.1, 3.1, 3.2,
            4.0, 4.0, 4.1, 4.1, 4.2,
            5.0,
        ]

        with patch('custom_components.llmvision.media_handlers.time') as mock_time, \
             patch('custom_components.llmvision.media_handlers.get_url', return_value='http://fake'), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            mock_time.time = Mock(side_effect=time_values)

            await processor.record(
                image_entities=['camera.test'],
                duration=4,
                max_frames=5,
                target_width=640,
                include_filename=False,
                expose_images=True,
            )

        ref_img = Image.open(io.BytesIO(captured_ref['bytes']))
        ref_mean = np.array(ref_img.convert('L')).mean()

        assert abs(ref_mean - 128) < 5, (
            f"Keyframe reference should be the first frame (brightness ~128), "
            f"got mean={ref_mean:.1f} which is closer to the last frame (brightness ~64)"
        )
