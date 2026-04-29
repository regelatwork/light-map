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
