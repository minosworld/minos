# Simulator API

MINOS uses WebSockets for communication between the server and client modules.

A typical communication flow:
1. Initialize and start the simulator using the `start` message.
2. Run simulator by sending `action` messages and processing the returned observations.
3. Send `reset` message to reset simulator state and rerun using `action`.
4. Send a `configure` message to load new scene and `start` to start acting in the environment.
5. Send a `close` message to terminate simulation.

### Configuration

The environment, agent and sensor configurations can be specified through preset configuration files under the [minos/config](minos/config) directory.  Finer or dynamic configuration can be implemented by direct API calls, but these files are a good start for familiarization with the overall configuration space.

- The default sensor configuration is in [minos/config/sensors.yml](minos/config/sensors.yml).  It specifies the parameters for the default set of sensors and is commented at a high level.  Refer to the sensor API section below for more details.
- The default agent configuration is in [minos/config/agent_continuous.yml](minos/config/agent_continuous.yml).  Comments are in the file, and details in the agent API section.  Alternative agent configurations can be found in [minos/config/agent_gridworld.yml](minos/config/agent_gridworld.yml) and [minos/config/agent_firstperson.yml](minos/config/agent_firstperson.yml).  The latter agent is convenient for smooth human control.
- Various environment and task configuration presets are found in [minos/config/envs](minos/config/envs).
- Object instance replacement macros (for now, used to substitute closed and semi-open doors with only their door frame) are specified in [minos/config/replace_doors.json](minos/config/replace_doors.json).
- The default configuration set is assembled in [minos/config/index.json](minos/config/index.json).

### API functions

The simulator API is implemented in [minos/lib/Simulator.py](lib/Simulator.py).  The main functions have pydoc strings, and are also described below.

1. `init`

   Initializes the simulator (called once).  See `configure` for configuration options.

2. `start`

   Resets and starts the simulation (initializes the simulator if not already initialized).  See `configure` for configuration options.  Call `start` after any major configuration changes such as scene change.

3. `configure`

   Reconfigures the simulator.  All old configuration parameters are kept, only changes to configuration need to be specified.

   #### Parameters:
   ```
   {
     agent: { ... },         # Agent options (see agent configuration section)
     scene: { fullId: ... }, # Load options for scene
     observations: {         # What type of observations to return (requires corresponding sensor specification)
       color: true,
       forces: false,
       objects: false,
       depth: false,
       audio: false,
       map: false
     },
     sensors: [              # Sensor specification array (see sensor configuration section)
       {...},
       ...
     ],
     start: 'random',        # Start state
     goal:  'random',        # Goal state (see goal configuration)
     navmap: {               # Navigation map configuration
       ...
     }
   }
   ```

   #### Agent configuration
   ```
      {
        eyeHeight: 1.09                   # m height eye level
        radius: 0.1                       # 10cm radius cylinder
        mass: 32.0                        # agent mass in kg
        coeffRestitution: 0.0             # ratio of relative velocity before and after collision in direction of collision normal
        stepAcceleration: 20.0            # base linear acceleration for steps in m/s^2
        maxSpeed: 2.0                     # maximum agent linear speed in m/s
        linearFriction: 0.5               # coefficient of friction applied to linear speed every step (k in F=-k*m*v/dt)
        turnAcceleration: 12.5663706144   # turn acceleration in rad/s^2
        maxAngularSpeed: 12.5663706144    # maximum turn rate in rad/s
        angularFriction: 1.0              # coefficient of angular friction applied every step (k in tau=-k*m*w/dt)
        radialClearance: 0.2              # clearance to leave from center of agent for shortest path computations
      }
   ```
   
   #### Scene configuration
   ```yaml
      {
         fullId: "mp3d.17DRP5sb8fy",                            # id of scene to load  
         archOnly: false,                                       # (optional) include objects or just load the scene
         retexture: false,                                      # (optional) retexturing of scene
         hideCategories: ["plant", "door", "person"],           # (optional) array of categories to hide (default is none)
         level: 0,                                              # (optional) restrict loading to only specified house level
         room:  0                                               # (optional) restrict loading to only specified room
      }
   ```
   #### Sensor configuration
   Sensor configurations are specified in a `"sensors"` array where each member has the following structure:
   ```yaml
      {
         name: "name",                                     # readable name for this sensor (group)
         type: "color|semantic|normal|depth|force|audio",
         configuration: "positional|radial|radial-group",  # type of position provided
         position: [[x0,y0,z0], [r0,y0,t0], ...],          # position of each sensor element in agent-centric coordinate frame (+x=right, +y=up, -z=forward). For radial, given as radius, height, theta ccw from +z). For radial-group, specifies origin of radial disk.
         orientation: [[x0,y0,z0], ...],                   # orientation of each sensor element in agent-centric coordinate frame.  For radial group, specifies orientation of first element, subsequent ones are rotated around the up axis.
         radial: [r,k,thetaStart,thetaEnd],                # Required for radial-group: radius, number of points, angle start and end measured ccw from +z
         resolution: [w0,h0]                               # resolution of sensor (width,height) for rgb|depth, or (timeInSec) for audio, or (dx,dy,dz) for force
         # sensor-specific encoding of return data
         encoding: "rgba|gray|objectId|objectType|roomId|roomType|xyza|depth|raw_contact|pcm"
      }
   ```
   #### Start state configuration
   
   Default is `random` position on floor (sampled uniformly from positions where agent can stand).
   
   #### Goal configuration
   
   Default is `random` which selects a random navigatable position.
   
   To specify a point as a goal (with radius r as a distance threshold):
   ```
      { 'position': [x, y, z], 'radius': r }
   ```
   To specify object categories as goals and select a random instance of the category as the goal:
   ```
      { 'categories': ['arch', 'door'], 'select': 'random' }
   ```
   To specify room types as goals and select a random room of the category as the goal:
   ```
      { 'roomTypes': ['bedroom', 'bathroom'], 'select': 'random' }
   ```
   To specify instances of a model id as a goal, and select the closest from start as the goal:
   ```
      { 'modelIds': ['3dw.abc...', '3dw.efg...'], 'select': 'closest' }
   ```
   To specify a specific object id as a goal:
   ```
      { 'objectIds': ['0_12'] }
   ```
   To specify a specific room id as the goal:
   ```
      { 'roomIds': ['0_1'] }
   ```

   #### Navigation map

   A navigation map can be used in the simulator to provide walkable tiles and shortest path computations.
   Recomputation of the navigation map can be slow so it is disabled by default.

   ```
   {
      recompute: undefined,    // true = force recomputing instead of using precomputed navigation map
                               //        otherwise, precomputed navigation map is loaded if available
                               //        if not available, falls back to recomputing the navigation map
                               
      autoUpdate: false        // Whether to automatically update shortest path computation on step
   }
   ```

4. `action`

   Performs specified action with given input arguments.  See Agent section below for list of actions supported.
   
   #### Action object
   ```
   {
     name: 'forwards',          # Name of action
     distance: 1                # Additional arguments to action (action specific)
   }
   ```

   #### Return object
   ```yaml
   {
     "time": 1.5,  # time in seconds since start of current episode
     "collision": true,  # whether a collision between the agent and environment was detected this step
     "observation": {
       "sensors": [  # returned observations for all active sensors
         { "name": "rgb1", "frame": [pixels], "shape": [w,h,d], "encoding": "rgba", ... },
         { "name": "force1", [fx0,fy0,fz0,...], "shape": [k,n,3], "encoding": "raw_contact", ... },
         { "name": "objectmask", "frame": [pixels], "shape": [w,h,1], "encoding": "indexed",
           "index": [object ids], "counts": {index to count}, },
         { "name": "audio1", "frame": [buffer], "shape": [k,n], "encoding": "pcm", ... }
       ],
       "measurements": {  # returned non-sensor measurements (goal distance and direction)
         "distance_to_goal": [d0,d1,...],
         "offset_to_goal": [dx0,dy0,dz0,dx1,dy1,dz1,...],
         "direction_to_goal": [dx0,dy0,dz0,dx1,dy1,dz1,...],
         "shortest_path_to_goal": {"distance": d, "direction": [dx,dy,dz]}
       },
       "roomInfo": {  # current room information
         "id": "0_1",
         "roomType": "Bathroom"
       },
       "map": {  # top-down map image with shortest path plotted
         "data": [pixels], "shape": [w,h,4]
       }
     },
     "info": {
       "agent_state": {"position": [x,y,z], "orientation":[dx,dy,dz]},  # current agent state
     },
     "success": false,  # whether this step ended with success for the episode task
     "measurements": [m0, m1, m2, m3, ...]  # arbitrary measurement values returned by measurement_fun function specified in config
   }
    ```

5. `reset`

   Resets the simulator to an initial state.

6. `close`

   Closes the current connection with the simulator server

## Agent

Actions supported by default agent:

```yaml
  # Generic actions
  { name: 'idle' }
  { name: 'moveTo', position: <vector3>, angle: <radians> }
  
  # Movement
  { name: 'forwards', strength: <multiplier> }
  { name: 'backwards', strength: <multiplier> }
  { name: 'strafeLeft', strength: <multiplier> }
  { name: 'strafeRight', strength: <multiplier> }
   
  # Rotation
  { name: 'turnLeft', strength: <multiplier> }
  { name: 'turnRight', strength: <multiplier> }
  
  # Look
  { name: 'lookUp', angle: <radians> }
  { name: 'lookDown', angle: <radians> }
```

