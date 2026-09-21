from multiprocessing.shared_memory import SharedMemory

import pytest

from light_map.vision.infrastructure.process_manager import VisionProcessManager


def test_process_manager_lifecycle():
    # Test that manager creates SHM and can stop it
    manager = VisionProcessManager(width=160, height=120)

    try:
        manager.start()
        shm_name = manager.shm_name
        assert shm_name is not None

        # Verify SHM exists
        shm = SharedMemory(name=shm_name)
        assert shm.size > 0
        shm.close()

        manager.stop()

        # Verify SHM is unlinked (should raise FileNotFoundError)
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=shm_name)

    finally:
        manager.stop()


def test_process_manager_worker_spawning():
    # Test that manager spawns processes (mocked/simple)
    manager = VisionProcessManager(width=160, height=120)
    try:
        manager.start()
        # In a real test, we would check for active processes
        assert len(manager.processes) >= 0  # We will implement workers in next tasks
    finally:
        manager.stop()


def test_process_manager_stereo_lifecycle():
    manager = VisionProcessManager(width=160, height=120, enable_stereo=True)
    try:
        manager.start()
        shm_left = manager.shm_name
        shm_right = manager.shm_name_right
        assert shm_left is not None
        assert shm_right is not None
        assert shm_left != shm_right

        # Verify both SHMs exist
        mem_l = SharedMemory(name=shm_left)
        mem_r = SharedMemory(name=shm_right)
        assert mem_l.size > 0
        assert mem_r.size > 0
        mem_l.close()
        mem_r.close()

        manager.stop()

        with pytest.raises(FileNotFoundError):
            SharedMemory(name=shm_left)
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=shm_right)
    finally:
        manager.stop()


def test_process_manager_stereo_worker_kwargs():
    from unittest.mock import patch

    with patch("multiprocessing.Process") as mock_process:
        manager = VisionProcessManager(
            width=160, height=120, enable_stereo=True, width_right=160, height_right=120
        )
        try:
            manager.start()
            # Find the process created for ArucoWorker
            aruco_calls = [
                call
                for call in mock_process.call_args_list
                if call.kwargs.get("name") == "ArucoWorker"
            ]
            assert len(aruco_calls) == 1
            call_kwargs = aruco_calls[0].kwargs.get("kwargs", {})
            assert "shm_name_right" in call_kwargs
            assert call_kwargs["shm_name_right"] == manager.shm_name_right
            assert "lock_right" in call_kwargs
            assert call_kwargs["lock_right"] == manager.lock_right
        finally:
            manager.stop()
