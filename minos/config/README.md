Configuration files for MINOS

# Agent configuration
- `agent_continuous.yml` - Agent configuration for discrete controls with continuous movement
- `agent_gridworld.yml` - Agent configuration for discrete controls with discrete movement 
- `agent_firstperson.yml` - Human height for first person controls by humans (Note that the agent is taller than the ones specified in `agent_continuous.yml` and `agent_gridworld.yml`)

# Sensor configuration
- `sensors.yml` - Default sensors for MINOS (with `color`, `objectId`, `objectType`, `roomId`, `roomType`, `normal`, `depth`, and `force`)
- `sensors_mp3d.yml` - Semantic texture sensors for Matterport3D (with `color`, `objectId`, `normal`, `depth`, `force`)
- `sensors_equirectangular.yml` - Equirectangular panorama sensor (similar to `sensors.yml`)
- `sensors_im2pano3d.yml` - Panoramic sensor with four cameras as in the Im2Pano3D paper (similar to `sensors.yml`)

# Environment configuration
Environment configurations are in the `env` directory.
Each configuration follows the naming convention of `<goaltype>_<dataset>_<variant>` where we have `<goaltype> = objectgoal | pointgoal | roomgoal`, and `dataset = suncg | mp3d`.  For `<variant>`, we have `m` for medium sized environments, `s` for small environments, `f` for furnished, and `e` for empty.

# Other configuration
- `replace_doors.json` - SUNCG door models to be replaced so that the doors are removed 
- `visualize_traces.json` - Configuration file to use for `visualize_path.js`