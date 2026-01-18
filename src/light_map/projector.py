import cv2
import numpy as np

def generate_calibration_pattern(width, height, pattern_rows, pattern_cols, border_size=100):
    """
    Generates a visual calibration pattern (checkerboard).
    
    Args:
        width: Total width of the screen/image.
        height: Total height of the screen/image.
        pattern_rows: Number of rows in the pattern.
        pattern_cols: Number of columns in the pattern.
        border_size: Padding around the pattern.
        
    Returns:
        pattern_image: The generated image.
        pattern_params: Dict containing metadata like square size (pixels), offsets, etc.
    """
    # Calculate square size based on available space and requested rows/cols
    max_sq_w = (width - 2 * border_size) // pattern_cols
    max_sq_h = (height - 2 * border_size) // pattern_rows
    square_size = min(max_sq_w, max_sq_h)
    
    pattern_image = np.zeros((height, width, 3), dtype=np.uint8)
    pattern_image.fill(255) # White background

    # Calculate starting position to center the pattern
    total_pattern_w = square_size * pattern_cols
    total_pattern_h = square_size * pattern_rows
    
    start_x = (width - total_pattern_w) // 2
    start_y = (height - total_pattern_h) // 2
    
    for i in range(pattern_rows):
        for j in range(pattern_cols):
            x1 = start_x + j * square_size
            y1 = start_y + i * square_size
            x2 = start_x + (j + 1) * square_size
            y2 = start_y + (i + 1) * square_size
            
            if (i + j) % 2 == 0:
                color = (0, 0, 0)
            else:
                color = (255, 255, 255)
                
            cv2.rectangle(pattern_image, (x1, y1), (x2, y2), color, -1)

    return pattern_image, {
        "square_size": square_size,
        "border_size": border_size,
        "start_x": start_x,
        "start_y": start_y,
        "rows": pattern_rows,
        "cols": pattern_cols
    }

def compute_projector_homography(camera_image, pattern_params, camera_matrix=None, dist_coeffs=None):
    """
    Computes the homography matrix to map camera coordinates to projector coordinates.
    
    Args:
        camera_image: The image captured by the camera showing the projected pattern.
        pattern_params: Metadata from generate_calibration_pattern.
        
    Returns:
        transformation_matrix: 3x3 homography matrix.
    """
    gray = cv2.cvtColor(camera_image, cv2.COLOR_BGR2GRAY)
    
    # Inner corners are (rows-1, cols-1)
    # Note: cv2.findChessboardCorners expects (cols, rows)
    board_size = (pattern_params["cols"] - 1, pattern_params["rows"] - 1)
    
    ret, corners = cv2.findChessboardCorners(gray, board_size, None)
    
    if not ret:
        raise RuntimeError("Chessboard pattern not detected in the captured image.")

    # Prepare screen points (where we drew the corners)
    # The corners correspond to the intersections of the squares.
    screen_points = []
    
    sq_size = pattern_params["square_size"]
    start_x = pattern_params.get("start_x", pattern_params.get("border_size", 0))
    start_y = pattern_params.get("start_y", pattern_params.get("border_size", 0))
    
    # The loop order must match the order findChessboardCorners returns (row by row, left to right)
    for i in range(board_size[1]): # rows
        for j in range(board_size[0]): # cols
            # The first inner corner is at the bottom-right of the first square (0,0)
            # if we consider (0,0) to be top-left square.
            # Actually, (0,0) square is at x=border, y=border.
            # Its bottom-right corner is at x=border+100, y=border+100.
            # So coordinate is (j+1)*sq_size + border
            
            # Original code logic:
            # screen_points[i * ... + j] = [j * 100 + 50 + border, i * 100 + 50 + border]
            # Wait, the original code added 50? That puts it in the *center* of the square?
            # cv2.findChessboardCorners finds *internal corners* (intersections).
            # If the original code used centers, that might be a misunderstanding of findChessboardCorners,
            # OR they were detecting blobs/circles?
            # Re-reading original code:
            # ret, corners = cv2.findChessboardCorners(...)
            # screen_points... = [j * 100 + 50 + border_size, i * 100 + 50 + border_size]
            
            # If they drew squares of size 100 starting at border_size.
            # The first intersection is at (border + 100, border + 100).
            # The original code puts the target point at (border + 50, border + 50)? 
            # That is the center of the first top-left square.
            # findChessboardCorners finds the *intersections*.
            
            # Correction: If the user wants to map the *detected corner* to a specific *screen pixel*,
            # and findChessboardCorners returns intersections, then screen_points MUST be the pixel coordinates
            # of those intersections on the generated image.
            
            # Intersection (0,0) corresponds to the point between square(0,0), (0,1), (1,0), (1,1).
            # x = border + 1 * square_size
            # y = border + 1 * square_size
            
            # The original code seems to be mapping the detected corner to the *center* of the square. 
            # This is mathematically incorrect for standard chessboard calibration if they are using findChessboardCorners.
            # However, I should probably stick to a Correct implementation or replicate the behavior if it was intentional?
            # Given the original code was likely "experimental", I will implement the STANDARD correct mapping:
            # Mapping detected corners to the grid intersections.
            
            x = start_x + (j + 1) * sq_size
            y = start_y + (i + 1) * sq_size
            screen_points.append([x, y])

    screen_points = np.array(screen_points, dtype=np.float32)
    camera_points = corners.reshape(-1, 2)

    # Compute homography
    transformation_matrix, _ = cv2.findHomography(camera_points, screen_points)
    
    return transformation_matrix
