from pathlib import Path

ROBOT_XML_PATH = Path(__file__).resolve().parent / "robot.xml"

UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10
MAX_REACH = UPPER_ARM_LENGTH + FOREARM_LENGTH
