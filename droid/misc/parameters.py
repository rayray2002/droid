import os
from cv2 import aruco

# Robot Params #
# nuc_ip = "172.16.0.2"
nuc_ip = "169.254.202.1"
robot_ip = "169.254.202.10"
laptop_ip = "169.254.202.12"
sudo_password = os.environ.get("DROID_SUDO_PASSWORD", "")  # never commit it
robot_type = "fr3"  # 'panda' or 'fr3'
robot_serial_number = "295341-0051712"

# Camera ID's #
hand_camera_id = "14064085"
varied_camera_1_id = "33790348"
varied_camera_2_id = ""
# varied_camera_2_id = "37998989"

# Charuco Board Params #
CHARUCOBOARD_ROWCOUNT = 9
CHARUCOBOARD_COLCOUNT = 14
CHARUCOBOARD_CHECKER_SIZE = 0.020


# ifi
CHARUCOBOARD_MARKER_SIZE = 0.015
ARUCO_DICT = aruco.getPredefinedDictionary(aruco.DICT_5X5_100)

# Ubuntu Pro Token (RT PATCH) #
ubuntu_pro_token = ""

# Code Version [DONT CHANGE] #
droid_version = "1.3"

 