# Hand Tracking and Gestures

The system continuously gets images from the camera, detects up to two hands, and projects the positions of the detected hand landmarks onto a fullscreen projector window. It utilizes a **multi-threaded pipeline** to decouple camera processing from UI rendering.

## Real-Time Feedback

The application displays:

- Real-time FPS (Frames Per Second).
- The number of detected hands.
- The recognized gesture for each hand (labeled Left/Right).

## Supported Gestures

The system currently recognizes the following gestures:

- **Open Palm**: All fingers extended.
- **Closed Fist**: All fingers curled.
- **Pointing**: Index finger extended.
- **Gun**: Thumb and Index fingers extended.
- **Victory**: Index and Middle fingers extended.
- **Shaka**: Thumb and Pinky extended.
- **Rock**: Index and Pinky extended.

## Debug Mode

To visualize hand tracking, gestures, and system stats (FPS), run the tracker with the debug flag:

```bash
python hand_tracker.py --debug
```

This will display an overlay with:

- FPS counter
- Hand count
- Recognized gesture name
- Cursor position
- Usage instructions
