import numpy as np
import logging
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory
from typing import Optional


class FrameProducer:
    """
    Consumer-side IPC abstraction for reading frames from shared memory.
    Ensures safe access via ref-counting and N+2 buffering strategy.
    """

    def __init__(
        self,
        shm_name: str,
        width: int = 1920,
        height: int = 1080,
        num_consumers: int = 2,
    ):
        self.width = width
        self.height = height
        self.n = num_consumers + 2
        self.frame_size = width * height * 3

        # timestamps: n * 8 bytes (int64)
        # shm_pushed: n * 8 bytes (int64)
        # latest_buffer_id: 4 bytes (int32)
        self.ctrl_ref_offset = 0
        self.ctrl_ts_offset = self.n * 4
        self.ctrl_shm_pushed_offset = self.ctrl_ts_offset + (self.n * 8)
        self.ctrl_latest_offset = self.ctrl_shm_pushed_offset + (self.n * 8)
        self.control_block_size = self.ctrl_latest_offset + 4

        # Attach to existing Shared Memory
        self.shm = SharedMemory(name=shm_name)
        self.lock = (
            mp.Lock()
        )  # Note: In a real system, this Lock would be shared from the manager

        # Internal state
        self._current_buffer_id: Optional[int] = None
        self._current_frame_view: Optional[np.ndarray] = None

        # Persistent views for control block
        self._ref_counts = np.frombuffer(
            self.shm.buf[self.ctrl_ref_offset : self.ctrl_ts_offset], dtype=np.int32
        )
        self._timestamps = np.frombuffer(
            self.shm.buf[self.ctrl_ts_offset : self.ctrl_shm_pushed_offset],
            dtype=np.int64,
        )
        self._shm_pushed_ts = np.frombuffer(
            self.shm.buf[self.ctrl_shm_pushed_offset : self.ctrl_latest_offset],
            dtype=np.int64,
        )
        self._latest_id = np.frombuffer(
            self.shm.buf[self.ctrl_latest_offset : self.control_block_size],
            dtype=np.int32,
        )

        logging.info(f"FrameProducer attached to shared memory: {shm_name}")

    def get_latest_timestamp(self) -> Optional[int]:
        """Returns the timestamp of the most recently published frame."""
        with self.lock:
            latest_id = self._latest_id[0]
            if latest_id == -1:
                return None
            if not (0 <= latest_id < self.n):
                # This indicates memory corruption or a serious logic error in IPC offsets
                logging.error(
                    f"FrameProducer ERROR: latest_id {latest_id} is out of bounds (n={self.n}, shm_name={self.shm.name})"
                )
                return None
            return int(self._timestamps[latest_id])

    def get_shm_pushed_timestamp(self) -> Optional[int]:
        """Returns the timestamp of when the most recent frame was pushed to SHM."""
        with self.lock:
            latest_id = self._latest_id[0]
            if latest_id == -1:
                return None
            if not (0 <= latest_id < self.n):
                return None
            return int(self._shm_pushed_ts[latest_id])

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Acquires a lease on the latest frame and returns it as a numpy view.
        MUST call release() before calling this again.
        """
        if self._current_buffer_id is not None:
            raise RuntimeError("Must release current frame before acquiring a new one.")

        # Increment ref_count
        # Note: In a real multi-process environment, self.lock MUST be the SAME lock as the producer.
        # This will be handled by the VisionProcessManager which will pass a shared Lock.
        # For now, we use self.lock which works for tests using the same process or shared lock objects.
        with self.lock:
            latest_id = self._latest_id[0]
            if latest_id == -1:
                return None
            if not (0 <= latest_id < self.n):
                return None

            self._ref_counts[latest_id] += 1
            self._current_buffer_id = int(latest_id)

        # Create view
        offset = self.control_block_size + (self._current_buffer_id * self.frame_size)
        shm_frame_buf = self.shm.buf[offset : offset + self.frame_size]
        self._current_frame_view = np.frombuffer(shm_frame_buf, dtype=np.uint8).reshape(
            (self.height, self.width, 3)
        )

        # Release the slice to avoid BufferError on close
        del shm_frame_buf

        return self._current_frame_view

    def release(self):
        """Releases the lease on the current frame."""
        if self._current_buffer_id is None:
            return

        with self.lock:
            if self._ref_counts[self._current_buffer_id] > 0:
                self._ref_counts[self._current_buffer_id] -= 1

        # Explicitly release references to SHM buffer
        self._current_frame_view = None
        self._current_buffer_id = None

    def close(self):
        """Closes access to shared memory. Does not unlink."""
        try:
            self.release()
        except Exception:
            pass

        # Clean up control block views
        if hasattr(self, "_ref_counts"):
            del self._ref_counts
        if hasattr(self, "_timestamps"):
            del self._timestamps
        if hasattr(self, "_shm_pushed_ts"):
            del self._shm_pushed_ts
        if hasattr(self, "_latest_id"):
            del self._latest_id

        # Also clear internal frame view just in case
        self._current_frame_view = None

        if hasattr(self, "shm"):
            try:
                self.shm.close()
            except BufferError:
                logging.warning(
                    "BufferError while closing SHM in FrameProducer. Some pointers still exist."
                )

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
