# FAQ

Frequently asked usage questions and answers.

### Reporting issues

If you observe any issues or bugs, please check the log files in `logs/<timestamp>/simserver.log and logs/<timestamp>/simulator.log` to and include them in a new issue that you open on the github repository.

### Sensor configuration

#### Setting the field of view for camera sensors
The `fov` parameter in `config/sensors.yml` controls the vertical field of view.  The horizontal field of view is determined by the aspect ratio of the image and the vertical field of view.

### Getting shortest path to goal and navigation map data

Information about the shortest path is given at each step in `["observation"]["measurements"]["shortest_path_to_goal"]`.  If the map sensor is enabled (through `--sensors map`) then there will also be data in `["observation"]["map"]` giving a top-down image view of the environment, and the shortest path from the current agent position to the goal.

### Common questions

#### How do I control what sensors are enabled?
The `observations` parameter defined in `minos/config/sim_config.py` controls which sensor types will return data on each step.  You can control which of these sensors are enabled using the command line arguments `--depth` or `--sensors`, or alternatively set the `observations` parameter directly in `sim_config.py`.

#### How can I run headless on a server?
It is possible to run the code on machines without a full X server session using the xvfb-run tool. See https://github.com/stackgl/headless-gl#how-can-headless-gl-be-used-on-a-headless-linux-machine for details. You can prefix command calls to the simulator with `xvfb-run` in this way: e.g., `NODE_BASE_URL=~\work xvfb-run -s "-ac -screen 0 1280x1024x24" python3 demo.py --env_config objectgoal_suncg_mf` . If you still have issues, check that the `LIBGL_ALWAYS_INDIRECT` environment variable is not defined. If it is defined, you can use `unset LIBGL_ALWAYS_INDIRECT` to undefine it.  A detailed discussion of this problem is in https://github.com/minosworld/minos/issues/5. In case you ecounter problems, please run `xvfb-run -s "-ac -screen 0 1280x1024x24" xvinfo` and/or `xvfb-run -s "-ac -screen 0 1280x1024x24" glxinfo` and follow up by reporting these outputs and your overall machine configuration in that github issue.

#### Where are the train/val/test splits defined and how are episodes sampled?
The splits are stored as part of the presampled episode files in [data/episodes_states.suncg.csv.bz2](https://github.com/minosworld/minos/blob/master/data/episode_states.suncg.csv.bz2) and [data/episodes_states.mp3d.csv.bz2](https://github.com/minosworld/minos/blob/master/data/episode_states.mp3d.csv.bz2).  To set the split from which episodes will be picked, you can either pass an `episode_schedule` parameter to the `RoomSimulator` constructor, or use the `set_episode_schedule` call to the `RoomSimulator`.  The strings `train`, `val`, and `test` are the three valid options, and they will correspondingly select the subset of episodes for the given split (from the above two files by default, or other episode_states files if you set the `states_file` parameter to a different file).  You can further restrict the episodes that will be used by a particular `RoomSimulator` through the `episode_filter` parameter in the env config files.  This is an arbitrary python function that can check the value of any of the columns in the episode_states csv files and return a boolean for whether the episode should be included.  For example, you can filter on `sceneId` and `roomId` to select only episodes in a specific house and room.

### Common issues/errors

#### I get an error about data
Please check that you define the `$NODE_BASE_URL` environment variable and that it points to the parent directory containing the extracted `suncg` and `mp3d` datasets.

#### I get an error from the `socketIO_client` package
We actually use our own fork of the python socketIO client package to fix issues with binary mode transport.  Confirm that when you run `pip install -r requirements.txt` our fork of the package is downloaded and installed. It should be listed as https://github.com/msavva/socketIO-client-2/zipball/master

#### I get a symbol lookup error on a machine with an nvidia GPU
This is due to an issue with the precompiled headless-gl nvidia GPU driver.  You can resolve this by following the steps in https://github.com/stackgl/headless-gl/issues/65#issuecomment-252742795 . When you obtain a freshly compiled webgl.node file, overwrite the file in `node_modules/gl/build/Release/webgl.node` with the file rebuilt on your system (copied from `headless-gl/build/Release/webgl.node`). It is good to check that there are no other copies of the `webgl.node` file in your minos directory tree that have not been updated.
