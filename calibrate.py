import sys
import os

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.calibration import load_calibration_images, calibrate_camera_from_images
import numpy as np

def main():
    image_dir = './images'
    print(f"Looking for images in {image_dir}...")
    
    images = load_calibration_images(image_dir)
    
    if not images:
        print("No images found. Please ensure .jpg or .jpeg files are in the 'images' directory.")
        return

    print(f"Found {len(images)} images. Starting calibration...")
    
    try:
        matrix, distortion = calibrate_camera_from_images(images)
        
        print("Camera matrix:")
        print(matrix)
        print("\nDistortion coefficients:")
        print(distortion)
        
        output_file = 'camera_calibration.npz'
        np.savez(output_file, camera_matrix=matrix, dist_coeffs=distortion)
        print(f"\nCalibration saved to {output_file}")
        
    except RuntimeError as e:
        print(f"Calibration failed: {e}")

if __name__ == '__main__':
    main()