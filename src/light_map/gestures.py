import numpy as np

def is_finger_extended(landmarks, finger_name, hand_label="Right"):
    """
    Determines if a finger is extended based on landmark positions.
    Using a simplified distance-from-wrist heuristic which is robust for 2D.
    """
    # Landmarks map
    # Thumb: 1-4
    # Index: 5-8
    # Middle: 9-12
    # Ring: 13-16
    # Pinky: 17-20
    
    # 0 is Wrist
    wrist = landmarks[0]
    
    if finger_name == "Thumb":
        tip = landmarks[4]
        ip = landmarks[3]
        mcp = landmarks[2]
        
        # Thumb is extended if the tip is further from the index finger MCP (5)
        # than the IP joint is? Or simple distance from wrist?
        # Thumb is tricky because it moves sideways.
        # Let's check if Tip is far from the Palm center (approx landmark 9 or 5/17 avg)
        
        # Simple check: Is tip further from wrist than IP? 
        # Usually yes even when curled.
        
        # Check X distance relative to pinky?
        # Let's use the standard "Tip is laterally outside" heuristic
        # Depending on hand label (Left/Right)
        
        # Vector logic is safer.
        # Vector form wrist to MCP(2). Vector from MCP(2) to Tip(4).
        # If angle is straight-ish...
        
        # Let's use a simpler geometry heuristic:
        # Distance from Tip(4) to Pinky MCP(17) > Distance from IP(3) to Pinky MCP(17)?
        # If thumb is open, it's far from pinky. If closed, it's closer.
        pinky_mcp = landmarks[17]
        
        d_tip = np.linalg.norm(np.array([tip.x, tip.y]) - np.array([pinky_mcp.x, pinky_mcp.y]))
        d_ip = np.linalg.norm(np.array([ip.x, ip.y]) - np.array([pinky_mcp.x, pinky_mcp.y]))
        
        return d_tip > d_ip

    else:
        # For other fingers, we check if the tip is further from the wrist than the PIP joint.
        # This works well for "Open" vs "Fist"
        
        indices = {
            "Index": (8, 6),   # Tip, PIP
            "Middle": (12, 10),
            "Ring": (16, 14),
            "Pinky": (20, 18)
        }
        
        tip_idx, pip_idx = indices[finger_name]
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        
        # Calculate distance to wrist (0)
        d_tip = np.linalg.norm(np.array([tip.x, tip.y]) - np.array([wrist.x, wrist.y]))
        d_pip = np.linalg.norm(np.array([pip.x, pip.y]) - np.array([wrist.x, wrist.y]))
        
        return d_tip > d_pip

def detect_gesture(landmarks, handedness_label):
    """
    Classifies the hand gesture based on landmarks.
    
    Args:
        landmarks: List of normalized landmark objects (from MediaPipe).
        handedness_label: "Left" or "Right".
        
    Returns:
        str: detected gesture name.
    """
    fingers = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
    state = {f: is_finger_extended(landmarks, f, handedness_label) for f in fingers}
    
    # Logic
    # All open -> Open Palm
    if all(state.values()):
        return "Open Palm"
    
    # All closed -> Closed Fist
    if not any(state.values()):
        return "Closed Fist"
    
    # Index only -> Pointing
    if state["Index"] and not state["Middle"] and not state["Ring"] and not state["Pinky"]:
        # Thumb state can vary for pointing (sometimes tucked, sometimes out)
        # Let's allow thumb to be anything or strict?
        # "Pointing" usually implies thumb is tucked or neutral.
        return "Pointing"
    
    # Index + Middle -> Victory
    if state["Index"] and state["Middle"] and not state["Ring"] and not state["Pinky"]:
        return "Victory"
    
    # Index + Pinky -> Rock? (Optional)
    if state["Index"] and state["Pinky"] and not state["Middle"] and not state["Ring"]:
        return "Rock"
    
    # Thumb + Pinky -> Shaka / Phone
    if state["Thumb"] and state["Pinky"] and not state["Index"] and not state["Middle"] and not state["Ring"]:
        return "Shaka"

    return "Unknown"
