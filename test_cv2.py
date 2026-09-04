import cv2
import numpy as np
r_l = np.eye(3, dtype=np.float32)
r_l_mat, _ = cv2.Rodrigues(r_l)
print(f"r_l_mat:\n{r_l_mat}")
r_r = np.eye(3, dtype=np.float32)
r_r_mat, _ = cv2.Rodrigues(r_r)
print(f"r_r_mat:\n{r_r_mat}")
r_stereo = r_l_mat @ r_r_mat.T
print(f"r_stereo:\n{r_stereo}")
print(f"deviation: {np.max(np.abs(r_stereo - np.eye(3)))}")
