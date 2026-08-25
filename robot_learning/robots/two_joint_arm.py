from pathlib import Path

TWO_JOINT_ARM_XML_PATH = Path(__file__).resolve().parent / "two_joint_arm.xml"

UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10
MAX_REACH = UPPER_ARM_LENGTH + FOREARM_LENGTH
