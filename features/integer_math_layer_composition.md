# Feature: Integer Math Layer Composition

## Overview

The current `Renderer` implementation uses floating-point math (`float32`) for alpha blending in `LayerMode.NORMAL`. This involves converting high-resolution image patches and buffers to floats, performing linear interpolation, and converting back to `uint8`. This process is computationally expensive and memory-intensive.

## Goal

Replace all floating-point alpha blending in the `Renderer` with optimized integer math (fixed-point arithmetic). This will improve frame rates and reduce CPU/memory overhead, especially for layers with many patches or large transparency regions.

## Proposed Implementation

1. **Fast-Path for Binary Masks**: Identify patches where the alpha channel is purely binary (0 or 255) and use a direct memory assignment (masked copy) instead of blending.
1. **Integer Blending Formula**: Use a bit-shift approximation for alpha blending:
   `Result = ((Patch * Alpha) + (ROI * (256 - Alpha))) >> 8`
1. **SIMD Optimization**: Leverage NumPy's vectorized operations to perform these integer calculations across entire arrays.

## Benefits

- Reduced CPU usage per frame.
- Lower memory footprint (no intermediate float32 buffers).
- Higher sustainable FPS on lower-end hardware.

## Dependencies

- `src/light_map/renderer.py`
