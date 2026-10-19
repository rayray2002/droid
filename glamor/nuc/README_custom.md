run following first
```
sudo ethtool -C enp86s0 rx-usecs 0
```


run following to double-check the communication between nuc and robot is set properly
on one terminal:
```
conda activate polymetis-local
launch_robot.py robot_client=franka_hardware
```

open another terminal:
```
conda activate polymetis-local
sudo CONDA_PREFIX=/home/franka/miniconda3 taskset -c 0-3 chrt -f 99 /home/franka/miniconda3/envs/polymetis-local/bin/benchmark_control_latency.py
```
You should see both the joint control and cartesian control get a success rate of near 100%.