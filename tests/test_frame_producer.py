import numpy as np
import pytest
import time
from light_map.vision.camera_operator import CameraOperator
from light_map.vision.frame_producer import FrameProducer

def test_frame_producer_lifecycle():
    width, height = 160, 120
    # Setup a producer to create the SHM
    operator = CameraOperator(width=width, height=height, num_consumers=1)
    
    try:
        # Create a consumer (FrameProducer)
        consumer = FrameProducer(shm_name=operator.shm_name, width=width, height=height, num_consumers=1)
        
        # 1. No frames yet
        assert consumer.get_latest_frame() is None
        
        # 2. Publish a frame
        fake_frame = np.zeros((height, width, 3), dtype=np.uint8)
        fake_frame[5:15, 5:15] = [0, 255, 0] # Green square
        ts = 1000
        operator._publish_frame(fake_frame, ts)
        
        # 3. Consume frame
        shm_frame = consumer.get_latest_frame()
        assert shm_frame is not None
        assert np.array_equal(shm_frame, fake_frame)
        
        # Verify ref count is 1
        with operator.lock:
            # We must be careful not to hold references to operator.shm.buf slices
            ref_counts_buf = operator.shm.buf[operator.ctrl_ref_offset : operator.ctrl_ts_offset]
            ref_counts = np.frombuffer(ref_counts_buf, dtype=np.int32)
            
            latest_id_buf = operator.shm.buf[operator.ctrl_latest_offset : operator.control_block_size]
            latest_id = int(np.frombuffer(latest_id_buf, dtype=np.int32)[0])
            assert ref_counts[latest_id] == 1
            
            # Explicitly delete these local views
            del ref_counts
            del ref_counts_buf
            del latest_id_buf
            
        # 4. Release
        del shm_frame # Release the view reference
        consumer.release()
        with operator.lock:
            # We need another view to check result
            ref_counts_buf = operator.shm.buf[operator.ctrl_ref_offset : operator.ctrl_ts_offset]
            ref_counts = np.frombuffer(ref_counts_buf, dtype=np.int32)
            assert ref_counts[latest_id] == 0
            del ref_counts
            del ref_counts_buf
        
        consumer.close()
            
    finally:
        operator.cleanup()

def test_frame_producer_strict_lifecycle():
    width, height = 160, 120
    operator = CameraOperator(width=width, height=height, num_consumers=1)
    try:
        consumer = FrameProducer(shm_name=operator.shm_name, width=width, height=height, num_consumers=1)
        operator._publish_frame(np.zeros((height, width, 3), dtype=np.uint8), 1000)
        
        # Should not be able to call get_latest_frame twice without release
        f1 = consumer.get_latest_frame()
        with pytest.raises(RuntimeError):
            consumer.get_latest_frame()
        
        del f1
        consumer.release()
        # Now it should work
        f2 = consumer.get_latest_frame()
        del f2
        consumer.release()
        consumer.close()
    finally:
        operator.cleanup()
