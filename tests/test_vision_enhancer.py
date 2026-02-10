import pytest
import numpy as np
from light_map.vision_enhancer import VisionEnhancer

@pytest.fixture
def enhancer():
    return VisionEnhancer(gamma=0.5, clahe_clip=2.0)

def test_gamma_darkening(enhancer):
    # Create a bright grey image (all 200)
    img = np.full((100, 100, 3), 200, dtype=np.uint8)
    
    # Apply gamma 0.5 (should darken highlights significantly)
    # v_out = 200 ^ (1/0.5) = 200 ^ 2 -> will be small since normalized 0..1
    # Normalized: (200/255)^2 * 255 ~= (0.78^2) * 255 ~= 0.6 * 255 ~= 153
    out = enhancer.apply_gamma(img)
    
    assert np.mean(out) < np.mean(img)
    assert out.shape == img.shape

def test_clahe_contrast(enhancer):
    # Create a low-contrast image (mid-grey gradient)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    for i in range(100):
        img[i, :] = 120 + (i // 10) # range 120..130
        
    out = enhancer.apply_clahe(img)
    
    # Contrast (Std Dev) should increase
    assert np.std(out) > np.std(img)
    assert out.shape == img.shape

def test_process_pipeline(enhancer):
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    out = enhancer.process(img)
    
    assert out.shape == img.shape
    assert out.dtype == np.uint8
