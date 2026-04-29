import logging
import multiprocessing as mp
import time
from multiprocessing.shared_memory import SharedMemory

import numpy as np


class CameraOperator:
    """
    Producer that captures camera frames and writes them into shared memory
    using an N+2 buffering strategy.
    """

    def __init__(self, width: int = 1920, height: int = 1080, num_consumers: int = 2):
        self.width = width
        self.height = height
        self.num_consumers = num_consumers
        self.n = num_consumers + 2
        self.frame_size = width * height * 3

        # Calculate Control Block size
        # ref_counts: n * 4 bytes (int32)
        # timestamps: n * 8 bytes (int64)
        # shm_pushed: n * 8 bytes (int64)
        # latest_buffer_id: 4 bytes (int32)
        self.ctrl_ref_offset = 0
        self.ctrl_ts_offset = self.n * 4
        self.ctrl_shm_pushed_offset = self.ctrl_ts_offset + (self.n * 8)
        self.ctrl_latest_offset = self.ctrl_shm_pushed_offset + (self.n * 8)
        self.control_block_size = self.ctrl_latest_offset + 4

        # Total size
        self.total_size = self.control_block_size + (self.n * self.frame_size)

        # Initialize Shared Memory
        self.shm = SharedMemory(create=True, size=self.total_size)
        self.shm_name = self.shm.name
        self.lock = mp.Lock()

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

        # Initialize ref_counts to 0 and latest_id to -1
        self._init_control_block()

        logging.info(
            f"CameraOperator initialized with shared memory: {self.shm_name}, size={self.total_size}"
        )

    def _init_control_block(self):
        with self.lock:
            self._ref_counts.fill(0)
            self._timestamps.fill(0)
            self._shm_pushed_ts.fill(0)
            self._latest_id[0] = -1

    def _find_free_buffer(self) -> int:
        """Finds a buffer with ref_count 0. Producer must lock control block."""
        if not hasattr(self, "_ref_counts"):
            return -1
        # Return first index that is 0
        indices = np.where(self._ref_counts == 0)[0]
        if len(indices) > 0:
            return int(indices[0])
        return -1

    def _publish_frame(self, frame: np.ndarray, timestamp: int) -> int:
        """
        Internal method to write a frame and update the control block.
        Used for testing and by the capture loop.
        """
        if not hasattr(self, "shm") or self.shm.buf is None:
            return -1

        target_id = -1

        with self.lock:
            target_id = self._find_free_buffer()
            if target_id == -1:
                logging.warning("No free buffer available in Shared Memory!")
                return -1

            # Reserve
            self._ref_counts[target_id] = -1

        # Write data
        offset = self.control_block_size + (target_id * self.frame_size)
        try:
            shm_frame_buf = self.shm.buf[offset : offset + self.frame_size]
            shm_frame = np.frombuffer(shm_frame_buf, dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )
            np.copyto(shm_frame, frame)

            # Explicitly delete views
            del shm_frame
            del shm_frame_buf
        except (BufferError, AttributeError, ValueError):
            # SHM might be closing
            return -1

        # Publish
        with self.lock:
            if not hasattr(self, "_ref_counts"):
                return -1
            self._timestamps[target_id] = timestamp
            self._shm_pushed_ts[target_id] = time.perf_counter_ns()
            self._latest_id[0] = target_id
            self._ref_counts[target_id] = 0

        return target_id

    def cleanup(self):
        """Releases shared memory and unlinks it."""
        with self.lock:
            if hasattr(self, "shm"):
                # Delete any views held by this object to avoid BufferError on close
                if hasattr(self, "_ref_counts"):
                    del self._ref_counts
                if hasattr(self, "_timestamps"):
                    del self._timestamps
                if hasattr(self, "_shm_pushed_ts"):
                    del self._shm_pushed_ts
                if hasattr(self, "_latest_id"):
                    del self._latest_id

                try:
                    self.shm.close()
                    self.shm.unlink()
                except (FileNotFoundError, BufferError):
                    pass
                logging.info(f"Shared memory {self.shm_name} cleaned up.")

    def __del__(self):
        self.cleanup()
