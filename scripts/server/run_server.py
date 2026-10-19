import zerorpc

from droid.franka.robot import FrankaRobot

if __name__ == "__main__":
    robot_client = FrankaRobot()
    # # Polymetis must already be running (e.g. launch_robot.py on the NUC).
    # # Connect the RPC server to the live robot/gripper interfaces.
    # robot_client.launch_robot()
    s = zerorpc.Server(robot_client)
    s.bind("tcp://0.0.0.0:4242")
    s.run()
