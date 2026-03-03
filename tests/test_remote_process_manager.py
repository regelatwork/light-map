import pytest
import multiprocessing as mp
from light_map.vision.process_manager import VisionProcessManager

def test_process_manager_remote_exclusive_hands():
    """Verify that physical hand worker is NOT spawned in exclusive mode."""
    manager = VisionProcessManager(remote_mode_hands="exclusive")
    manager.start()
    
    # Check process names
    process_names = [p.name for p in manager.processes]
    
    assert "ArucoWorker" in process_names
    assert "RemoteDriverWorker" in process_names
    assert "HandWorker" not in process_names
    
    manager.stop()

def test_process_manager_remote_exclusive_tokens():
    """Verify that physical aruco worker is NOT spawned in exclusive mode."""
    manager = VisionProcessManager(remote_mode_tokens="exclusive")
    manager.start()
    
    process_names = [p.name for p in manager.processes]
    
    assert "HandWorker" in process_names
    assert "RemoteDriverWorker" in process_names
    assert "ArucoWorker" not in process_names
    
    manager.stop()

def test_process_manager_remote_ignore():
    """Verify that remote driver is NOT spawned if both modes are ignore."""
    manager = VisionProcessManager(remote_mode_hands="ignore", remote_mode_tokens="ignore")
    manager.start()
    
    process_names = [p.name for p in manager.processes]
    
    assert "HandWorker" in process_names
    assert "ArucoWorker" in process_names
    assert "RemoteDriverWorker" not in process_names
    
    manager.stop()
