import numpy as np
from src.light_map.common_types import GestureType


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
        landmarks[2]

        # Thumb is extended if the tip is further from the index finger MCP (5)
        # than the IP joint is? Or simple distance from wrist?
        # Thumb is tricky because it moves sideways.
        # Let's check if Tip is far from the Palm center (approx landmark 9 or 5/17 avg)

        # Thumb is extended if the tip is further from the pinky MCP than the IP joint
        # AND it must be far enough from the index MCP to be considered "spread out"
        pinky_mcp = landmarks[17]
        index_mcp = landmarks[5]

        d_tip_pinky = np.linalg.norm(
            np.array([tip.x, tip.y]) - np.array([pinky_mcp.x, pinky_mcp.y])
        )
        d_ip_pinky = np.linalg.norm(
            np.array([ip.x, ip.y]) - np.array([pinky_mcp.x, pinky_mcp.y])
        )

        d_tip_index = np.linalg.norm(
            np.array([tip.x, tip.y]) - np.array([index_mcp.x, index_mcp.y])
        )
        palm_width = np.linalg.norm(
            np.array([index_mcp.x, index_mcp.y]) - np.array([pinky_mcp.x, pinky_mcp.y])
        )

        return (d_tip_pinky > d_ip_pinky) and (d_tip_index > palm_width * 0.4)

    else:
        # For other fingers, we check if the tip is further from the wrist than the PIP joint.
        # This works well for "Open" vs "Fist"

        indices = {
            "Index": (8, 6),  # Tip, PIP
            "Middle": (12, 10),
            "Ring": (16, 14),
            "Pinky": (20, 18),
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
        GestureType: detected gesture.
    """
    fingers = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
    state = {f: is_finger_extended(landmarks, f, handedness_label) for f in fingers}

    # Logic
    # All open -> Open Palm
    if all(state.values()):
        return GestureType.OPEN_PALM

    # All closed -> Closed Fist
    if not any(state.values()):
        return GestureType.CLOSED_FIST

    # Thumb + Index -> Gun
    if (
        state["Thumb"]
        and state["Index"]
        and not state["Middle"]
        and not state["Ring"]
        and not state["Pinky"]
    ):
        return GestureType.GUN

    # Index only -> Pointing
    if (
        state["Index"]
        and not state["Middle"]
        and not state["Ring"]
        and not state["Pinky"]
    ):
        # Thumb state can vary for pointing (sometimes tucked, sometimes out)
        # Let's allow thumb to be anything or strict?
        # "Pointing" usually implies thumb is tucked or neutral.
        return GestureType.POINTING

    # Index + Middle -> Victory
    if state["Index"] and state["Middle"] and not state["Ring"] and not state["Pinky"]:
        return GestureType.VICTORY

    # Index + Pinky -> Rock? (Optional)
    if state["Index"] and state["Pinky"] and not state["Middle"] and not state["Ring"]:
        return GestureType.ROCK

    # Thumb + Pinky -> Shaka / Phone
    if (
        state["Thumb"]
        and state["Pinky"]
        and not state["Index"]
        and not state["Middle"]
        and not state["Ring"]
    ):
        return GestureType.SHAKA

    return GestureType.UNKNOWN
