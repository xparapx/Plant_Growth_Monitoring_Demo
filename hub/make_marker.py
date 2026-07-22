"""Print at EXACT size, then MEASURE the printed side with a ruler."""
import cv2
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
cv2.imwrite("marker_id0.png", cv2.aruco.generateImageMarker(DICT, 0, 600))
print("saved marker_id0.png -- print at 100%, then measure in mm")
