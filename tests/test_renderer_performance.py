import numpy as np
import time
from light_map.rendering.renderer import Renderer
from light_map.core.common_types import ImagePatch, LayerMode, AppConfig


from light_map.rendering.composition_utils import composite_patch

def test_renderer_correctness():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)

    # Create a background: half white, half black
    background = np.zeros((100, 100, 3), dtype=np.uint8)
    background[:, :50] = 255
    renderer.output_buffer[:] = background

    # Create a patch: Red with 50% alpha (128)
    # RGBA: (0, 0, 255, 128) -> BGR + Alpha
    patch_data = np.zeros((50, 50, 4), dtype=np.uint8)
    patch_data[:, :, 2] = 255  # Red in BGR is index 2
    patch_data[:, :, 3] = 128  # Alpha

    patch = ImagePatch(x=25, y=25, width=50, height=50, data=patch_data)

    # Render
    composite_patch(renderer.output_buffer, patch, LayerMode.NORMAL, 100, 100)

    # Check a pixel that was white (255, 255, 255)
    # Expected: (255, 0, 0) * 0.5 + (255, 255, 255) * 0.5 = (255, 127, 127)
    # Note: BGR -> Red is (0, 0, 255)
    # White BGR: (255, 255, 255)
    # Red BGR: (0, 0, 255)
    # Result BGR: (0*0.5 + 255*0.5, 0*0.5 + 255*0.5, 255*0.5 + 255*0.5)
    # = (127, 127, 255)

    pixel_white = renderer.output_buffer[30, 30]
    print(f"White background blend: {pixel_white}")
    assert np.allclose(pixel_white, [127, 127, 255], atol=2)

    # Check a pixel that was black (0, 0, 0)
    # Expected: (0, 0, 255) * 0.5 + (0, 0, 0) * 0.5 = (0, 0, 127)
    pixel_black = renderer.output_buffer[30, 60]
    print(f"Black background blend: {pixel_black}")
    assert np.allclose(pixel_black, [0, 0, 127], atol=2)


def test_renderer_binary_mask_optimization():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    renderer = Renderer(config)
    renderer.output_buffer.fill(255)  # White

    # Create a patch: Blue with 100% alpha (255)
    patch_data = np.zeros((50, 50, 4), dtype=np.uint8)
    patch_data[:, :, 0] = 255  # Blue
    patch_data[:, :, 3] = 255  # Alpha

    patch = ImagePatch(x=25, y=25, width=50, height=50, data=patch_data)

    composite_patch(renderer.output_buffer, patch, LayerMode.NORMAL, 100, 100)

    assert np.all(renderer.output_buffer[30, 30] == [255, 0, 0])


def benchmark_renderer():
    width, height = 1920, 1080
    config = AppConfig(width=width, height=height, projector_matrix=np.eye(3))
    renderer = Renderer(config)

    # 10 large patches
    patches = []
    for i in range(10):
        data = np.random.randint(0, 256, (400, 400, 4), dtype=np.uint8)
        data[:, :, 3] = np.random.randint(0, 256, (400, 400), dtype=np.uint8)
        patches.append(
            ImagePatch(x=i * 100, y=i * 50, width=400, height=400, data=data)
        )

    start = time.perf_counter()
    for _ in range(100):
        for patch in patches:
            composite_patch(renderer.output_buffer, patch, LayerMode.NORMAL, width, height)
    end = time.perf_counter()

    print(f"Time for 1000 patches: {end - start:.4f}s")


if __name__ == "__main__":
    test_renderer_correctness()
    test_renderer_binary_mask_optimization()
    benchmark_renderer()
