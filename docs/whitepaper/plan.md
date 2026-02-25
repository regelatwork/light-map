# Whitepaper Plan: Token Calibration and Tracking in Light Map

## 1. Abstract

Brief summary of the Augmented Reality tabletop platform and the technical challenges of calibration and tracking.

## 2. Introduction

- Context: Digital vs. Physical tabletop gaming.
- Problem Statement: Low-cost, high-immersion interaction.
- Proposed Solution: Light Map system overview.

## 3. Mathematical Foundations

- Camera Pinhole Model.
- Projector as an Inverse Camera.
- Homographies and Perspective Transformations.

## 4. Calibration Workflow

- **Intrinsics**: Camera matrix and distortion coefficients.
- **Projector-Camera Mapping**: Solving the mapping from image space to projection space.
- **Scale Calibration**: PPI (Pixels Per Inch) and metric consistency.
- **Extrinsics**: Spatial relationship between camera and projection surface.

## 5. Token Tracking

- **Aruco-based Tracking**: Detection, ID management, and pose estimation.
- **Structured Light/Flash Detection**: Tracking physical objects without markers.
- **Noise Mitigation**: Temporal filtering and stability algorithms.

## 6. Implementation

- Software Stack (Python, OpenCV, GStreamer).
- Real-time constraints and performance optimizations.

## 7. Results

- Tracking accuracy measurements.
- Latency analysis.

## 8. Conclusion

- Summary of achievements and future directions (e.g., dynamic depth sensing).

## 9. References
