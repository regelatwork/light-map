import functools
import logging
import os

import cv2
import numpy as np
import svgelements

from light_map.rendering.svg.blockers import get_visibility_blockers as extract_blockers
from light_map.rendering.svg.geometry import (
    analyze_spacing_and_origin,
    collect_grid_coordinates,
)
from light_map.rendering.svg.renderer import (
    detect_grid_spacing_raster,
    render_image_element,
    render_shape_element,
    render_text_element,
)
from light_map.rendering.svg.utils import get_element_label, get_viewport_matrix
from light_map.visibility.visibility_types import VisibilityBlocker


class SVGLoader:
    """Loads and renders SVG maps."""

    def __init__(self, filename: str):
        self.filename = os.path.abspath(filename)
        try:
            self.svg = svgelements.SVG.parse(self.filename)
            self.id_map = {}
            if self.svg:
                for e in self.svg.elements():
                    if hasattr(e, "id") and e.id:
                        self.id_map[str(e.id)] = e
        except Exception as e:
            logging.error("Error loading SVG: %s", e)
            self.svg = None
            self.id_map = {}

    @property
    def width(self) -> float:
        """Returns the width of the SVG in pixels."""
        if not self.svg:
            return 0.0
        try:
            # Try explicit width first
            if self.svg.width is not None:
                w = float(self.svg.width)
                if w > 0:
                    return w
            # Fallback to viewbox width
            if self.svg.viewbox is not None:
                return float(self.svg.viewbox.width)
        except (ValueError, TypeError):
            pass
        return 0.0

    @property
    def height(self) -> float:
        """Returns the height of the SVG in pixels."""
        if not self.svg:
            return 0.0
        try:
            # Try explicit height first
            if self.svg.height is not None:
                h = float(self.svg.height)
                if h > 0:
                    return h
            # Fallback to viewbox height
            if self.svg.viewbox is not None:
                return float(self.svg.viewbox.height)
        except (ValueError, TypeError):
            pass
        return 0.0

    def _find_door_ids(self) -> set[int]:
        """Identifies door elements (including children of door groups)"""
        door_element_ids = set()

        def find_doors(elem, in_door=False):
            tag = elem.values.get("tag")
            if tag in ("symbol", "defs"):
                return

            is_this_door = in_door
            if not is_this_door:
                label = get_element_label(elem)
                if label and "door" in label.lower():
                    is_this_door = True

            if is_this_door:
                door_element_ids.add(id(elem))

            if isinstance(elem, list):
                for child in elem:
                    find_doors(child, is_this_door)

        find_doors(self.svg)
        return door_element_ids

    def detect_grid_spacing(self) -> tuple[float, float, float]:
        """Analyzes the SVG geometry to find the most likely grid spacing and origin."""
        if not self.svg:
            return 0.0, 0.0, 0.0
        x_coords, y_coords = collect_grid_coordinates(self.svg)
        spacing_x, origin_x = analyze_spacing_and_origin(x_coords)
        spacing_y, origin_y = analyze_spacing_and_origin(y_coords)

        if spacing_x > 0 and spacing_y > 0:
            spacing = (
                (spacing_x + spacing_y) / 2
                if abs(spacing_x - spacing_y) < 1.0
                else spacing_x
            )
        else:
            spacing = max(spacing_x, spacing_y)

        if spacing > 0:
            return spacing, origin_x, origin_y

        raster_spacing = detect_grid_spacing_raster(self.svg, self.render)
        return (raster_spacing, 0.0, 0.0) if raster_spacing > 0 else (0.0, 0.0, 0.0)

    def render(
        self,
        width: int,
        height: int,
        scale_factor: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        rotation: float = 0.0,
        quality: float = 1.0,
    ) -> np.ndarray:
        """Renders the SVG to a BGR numpy array with caching and dynamic quality."""
        q_scale = round(scale_factor, 4)
        q_rot = round(rotation, 2)
        q_quality = round(max(0.1, min(1.0, quality)), 2)
        q_offset_x, q_offset_y = int(round(offset_x)), int(round(offset_y))

        return self._render_internal(
            width, height, q_scale, q_offset_x, q_offset_y, q_rot, q_quality
        )

    def _render_mask(
        self, mask_id, final_vp_matrix, render_w, render_h, scale_factor, quality
    ):
        """Renders an SVG mask into a grayscale buffer."""
        mask_elem = self.svg.get_element_by_id(mask_id)
        if not mask_elem or not isinstance(mask_elem, svgelements.Group):
            return None

        temp_buffer = np.zeros((render_h, render_w, 3), dtype=np.uint8)

        def traverse_mask(elem, current_matrix):
            tag = elem.values.get("tag")
            if tag in ("symbol", "defs"):
                return

            local_matrix = current_matrix
            if hasattr(elem, "transform") and elem.transform is not None:
                local_matrix = svgelements.Matrix(elem.transform) * current_matrix

            if isinstance(elem, svgelements.Image):
                render_image_element(
                    elem, temp_buffer, local_matrix, render_w, render_h, self.svg
                )
            elif isinstance(elem, svgelements.Text):
                render_text_element(elem, temp_buffer, local_matrix, self.svg)
            elif isinstance(elem, svgelements.Shape):
                render_shape_element(
                    elem,
                    temp_buffer,
                    local_matrix,
                    scale_factor,
                    quality,
                    self.svg,
                    root_matrix=final_vp_matrix,
                    id_map=self.id_map,
                )

            if isinstance(elem, list):
                for child in elem:
                    traverse_mask(child, local_matrix)

        for child in mask_elem:
            traverse_mask(child, final_vp_matrix)

        return cv2.cvtColor(temp_buffer, cv2.COLOR_BGR2GRAY)

    @functools.lru_cache(maxsize=32)
    def _render_internal(
        self,
        target_width: int,
        target_height: int,
        scale_factor: float,
        offset_x: int,
        offset_y: int,
        rotation: float,
        quality: float,
    ) -> np.ndarray:
        """Internal cached renderer."""
        render_w, render_h = int(target_width * quality), int(target_height * quality)
        image = np.zeros((max(1, render_h), max(1, render_w), 3), dtype=np.uint8)

        if self.svg is None:
            return (
                cv2.resize(image, (target_width, target_height))
                if quality < 1.0
                else image
            )

        final_vp_matrix = get_viewport_matrix(
            target_width,
            target_height,
            scale_factor,
            offset_x,
            offset_y,
            rotation,
            quality,
        )
        door_element_ids = self._find_door_ids()

        def render_to_buffer(elem, buffer, current_matrix):
            try:
                if isinstance(elem, svgelements.Image):
                    render_image_element(
                        elem,
                        buffer,
                        current_matrix,
                        render_w,
                        render_h,
                        self.svg,
                    )
                elif isinstance(elem, svgelements.Text):
                    render_text_element(elem, buffer, current_matrix, self.svg)
                elif isinstance(elem, svgelements.Shape):
                    render_shape_element(
                        elem,
                        buffer,
                        current_matrix,
                        scale_factor,
                        quality,
                        self.svg,
                        root_matrix=final_vp_matrix,
                        id_map=self.id_map,
                    )
            except Exception:
                pass

        def traverse(elem):
            tag = elem.values.get("tag")
            if tag in ("symbol", "defs", "mask", "radialGradient", "linearGradient"):
                return

            if id(elem) in door_element_ids:
                return

            # Check for mask
            mask_val = elem.values.get("mask")
            if mask_val and mask_val.startswith("url(#"):
                mask_id = mask_val[5:-1]
                # Masks with userSpaceOnUse are relative to root units
                mask_gray = self._render_mask(
                    mask_id,
                    final_vp_matrix,
                    render_w,
                    render_h,
                    scale_factor,
                    quality,
                )
                if mask_gray is not None:
                    # Render element (and children if it's a group/list) into a 4-channel buffer
                    elem_buffer = np.zeros((render_h, render_w, 4), dtype=np.uint8)

                    # Temporarily clear mask to avoid infinite recursion
                    old_mask = elem.values.get("mask")
                    elem.values["mask"] = None

                    def render_subtree(e):
                        render_to_buffer(e, elem_buffer, final_vp_matrix)
                        if isinstance(e, list):
                            for child in e:
                                render_subtree(child)

                    render_subtree(elem)

                    # Restore mask
                    elem.values["mask"] = old_mask

                    # Apply mask to alpha channel
                    alpha_final = elem_buffer[:, :, 3].astype(float) * (
                        mask_gray.astype(float) / 255.0
                    )
                    elem_buffer[:, :, 3] = alpha_final.astype(np.uint8)

                    # Alpha-blend back to main image
                    alpha_f = elem_buffer[:, :, 3].astype(float) / 255.0
                    alpha_f = alpha_f[:, :, np.newaxis]
                    warped_bgr = elem_buffer[:, :, :3]
                    image[:] = (
                        warped_bgr.astype(float) * alpha_f
                        + image.astype(float) * (1.0 - alpha_f)
                    ).astype(np.uint8)
                    return

            render_to_buffer(elem, image, final_vp_matrix)

            if isinstance(elem, list):
                for child in elem:
                    traverse(child)

        traverse(self.svg)

        return (
            cv2.resize(image, (target_width, target_height)) if quality < 1.0 else image
        )

    def get_visibility_blockers(self) -> list[VisibilityBlocker]:
        """Extracts walls, doors, and windows from the SVG based on layer names."""
        return extract_blockers(self.svg) if self.svg else []
