import collections
import copy
import json
import logging as log
import os
import pprint
import resource
import signal
import subprocess as sp
import time
import uuid
from collections import Counter
from datetime import datetime
from string import Template

import numpy as np
import scipy.io.wavfile as wavfile
import yaml
from PIL import Image
from easydict import EasyDict as edict
from socketIO_client import SocketIO  # pip install https://github.com/msavva/socketIO-client-2/zipball/master

from . import common
from .simdepth import simdepth
from .simdepth.simdepth import DepthNoiseSim
from .simdepth.simredwood import RedwoodDepthNoiseSim
from .util.BackgroundPOpen import BackgroundPopen
from .util.LabelMapping import LabelMapping
from .util.RpcCall import RpcCall

simdepth_path = os.path.dirname(simdepth.__file__)

FORMAT = '%(asctime)s %(levelname)s %(message)s'
log.basicConfig(level=log.INFO, format=FORMAT)


class Simulator:
    """Provides interface to an indoor simulation server"""

    BoxSpace = collections.namedtuple('BoxSpace', ['range', 'shape'])

    def __init__(self, params):
        params = edict(params)
        home = os.environ.get('HOME')
        common.add_localhost_to_noproxy()
        script_path = os.path.dirname(os.path.realpath(__file__))
        if 'SIM_PATH' not in params:
            params.SIM_PATH = os.environ.get('SIM_PATH', os.path.join(script_path, '../'))
        if 'NODE_BASE_URL' not in params:
            params.NODE_BASE_URL = os.environ.get('NODE_BASE_URL', os.path.join(home, 'work/'))
        if 'color_encoding' not in params:
            params.color_encoding = 'gray'
        if 'host' not in params:
            params.host = 'localhost'
        if 'port' not in params or params.port is None:
            params.port = common.get_random_port()
        if 'audio' not in params or not params.audio:
            params.audio = edict()
        if 'port' not in params.audio or params.audio.port is None:
            params.audio.port = common.get_random_port()
        if 'datapath' not in params.audio:
            params.audio.datapath = 'data/wav'    # where audio files are found
        if 'wallpath' not in params.audio:
            params.audio.wallpath = os.path.join(params.NODE_BASE_URL, 'suncg', 'wall')    # where scene wall files are found
        if 'width' not in params and 'resolution' in params:
            params.width = params.resolution[0]
            params.height = params.resolution[1]
        if 'sensors_config' not in params:
            params.sensors_config = '../config/sensors.yml'
        # TODO: Organize these encodings
        if params.get('roomtypes_file') is not None:
            self.roomTypes = LabelMapping(params['roomtypes_file'], 'roomType', 0)
        else:
            self.roomTypes = None
        if params.get('objecttypes_file') is not None:
            self.objectTypes = LabelMapping(params['objecttypes_file'], 'objectType', 0)
        else:
            self.objectTypes = None

        self.auto_start = params.auto_start if 'auto_start' in params else False
        self.start_time = None
        self.stats_counter = Counter()
        self.id = params.get('id', 'sim00')
        self._uuid = uuid.uuid4()
        self._rpcid = 0
        self._proc_sim = None
        self._proc_audio = None
        self._sio = None
        self._restarts = 0
        self._last_observation = None
        self.start_summary_info = None
        self.running = False
        self.killed = False
        self.params = params

        # Initialize logging
        if 'logdir' in params:
            self._logdir = params.logdir
        else:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            self._logdir = './logs/' + timestamp
        self._logger = self._get_logger('simulator', propagate=True)
        self._output_dir = params.output_dir if 'output_dir' in params else self._logdir
        params.output_dir = os.path.abspath(self._output_dir)

        # Track what version we are
        stk_sim_path = os.path.dirname(os.path.abspath(__file__))
        stk_git_hash = sp.check_output(['git', 'rev-parse', '--short', 'HEAD'], universal_newlines=True,
                                       cwd=stk_sim_path).rstrip(),
        sim_git_hash = sp.check_output(['git', 'rev-parse', '--short', 'HEAD'], universal_newlines=True,
                                       cwd=params.SIM_PATH).rstrip(),
        info = {
            'sim_id': self.id,
            'machine': os.uname()[1],
            'sim_git_hash': sim_git_hash[0],
            'stk_git_hash': stk_git_hash[0]
        }
        self._logger.info(info)

        # Initialize sensors
        sensors_file = os.path.join(script_path, params.sensors_config)
        if sensors_file.endswith('.yml') or sensors_file.endswith('.yaml'):
            sensor_configs = yaml.load(open(sensors_file, 'r'))
        else:
            sensor_configs = json.load(open(sensors_file, 'r'))
        self._depth_noise_sims = {}
        self._sensors_by_name = {}
        for sensor_config in sensor_configs:
            # merge sensor configuration overrides
            if 'sensors' in params:
                for sensor_override in [x for x in params.sensors
                                        if 'name' in x and x['name'] == sensor_config['name']]:
                    sensor_config.update(sensor_override)
            sensor = edict(copy.copy(sensor_config))  # make copy so our noise_sim not in config parameters
            self._sensors_by_name[sensor['name']] = sensor
            if sensor.type == 'depth':
                if sensor.get('noise'):
                    noise_model = sensor.get('noise_model')
                    if noise_model is not None:
                        sensor['noise_sim'] = self._get_depth_noise_sim(noise_model)
                    else:
                        raise Exception('noise_model not specified for sensor ' + sensor.name)
                else:
                    sensor['noise_sim'] = None
        params.semantic_encodings = {}
        if self.roomTypes is not None:
            params.semantic_encodings['roomType'] = self.roomTypes.to_dict()
        if self.objectTypes is not None:
            params.semantic_encodings['objectType'] = self.objectTypes.to_dict()
        params.sensors = sensor_configs

        # Initialize agent config
        if 'agent_config' in params and params['agent_config']:
            cfg_id = params['agent_config']
            cfg_file = os.path.realpath(os.path.join(script_path, '../config/', cfg_id + '.yml'))
            with open(cfg_file, 'r') as f:
                agent_cfg = yaml.load(f)
            params.agent = agent_cfg

    def __del__(self):
        if not self.killed:
            self.kill()

    def _get_logger(self, name, propagate=False):
        common.ensure_dir_exists(self._logdir)
        filename = os.path.join(self._logdir, name + '.log')
        logger = log.getLogger(self._uuid.hex + '.' + name)
        if len(logger.handlers) == 0:
            fh = log.FileHandler(filename)
            fh.setLevel(log.INFO)
            fh.setFormatter(log.Formatter(FORMAT))
            logger.addHandler(fh)              # output log messages to file
        logger.propagate = propagate           # don't propagate messages to root logger (keep just in file)
        return logger

    def _rpc(self, name, data=None, callback=None, seconds=1):
        self._rpcid = self._rpcid + 1
        rpc = RpcCall(self._sio, self._rpcid, self._logger)
        return rpc.call(name, data, callback, seconds, check_wait=lambda: self.running)

    def _get_depth_noise_sim(self, noise_model_spec):
        simkey = json.dumps(noise_model_spec)
        noise_sim = self._depth_noise_sims.get(simkey)

        if noise_sim is None:
            noise_type = noise_model_spec.get('type')
            if noise_type == 'simple':
                if noise_model_spec.noise[0] == 'gaussian':
                    noise_sim = DepthNoiseSim(near=noise_model_spec.clip[0], far=noise_model_spec.clip[1],
                                              mean=noise_model_spec.noise[1], sigma=noise_model_spec.noise[2])
                else:
                    raise ValueError('Unknown noise distribution ' + noise_model_spec.noise[0])
            elif noise_type == 'redwood':
                noise_model_file = Template(noise_model_spec.path).substitute({ "SIMDEPTH_DIR": simdepth_path })
                simkey = noise_type + ':' + noise_model_file
                noise_sim = RedwoodDepthNoiseSim(noise_model_file)
            else:
                raise ValueError('Unsupported noise type ' + noise_type)
            self._depth_noise_sims[simkey] = noise_sim
        return noise_sim

    def start_child_servers(self):
        if self.auto_start:
            if not self._proc_sim:
                script_path = os.path.dirname(os.path.realpath(__file__))
                path_sim = os.path.realpath(os.path.join(script_path, '../server/'))
                self._logger.info(self.id + ':Starting sim server at %s with port %d' % (path_sim + '/server.js', self.params.port))
                my_env = os.environ.copy()
                my_env['NODE_BASE_URL'] = self.params.NODE_BASE_URL

                simserver_cmd = ['node','--max-old-space-size=4096', path_sim + '/server.js',
                                 '-p', str(self.params.port)]
                if self.params.get('busywait', 0) > 0:
                    simserver_cmd.append('--busywait')
                    simserver_cmd.append(str(self.params.get('busywait')))
                if self.params.get('ping_timeout') is not None:
                    simserver_cmd.append('--ping_timeout')
                    simserver_cmd.append(str(self.params.get('ping_timeout')))
                if self.params.get('profile_cpu', False):
                    simserver_cmd.insert(1, '--prof')
                if self.params.get('debug_mem', False):
                    simserver_cmd.insert(1, '--expose-gc')
                self._proc_sim = BackgroundPopen('simserver', self._get_logger('simserver'),
                                                 out_handler=None, err_handler=None,
                                                 args=simserver_cmd,
                                                 #bufsize=0,
                                                 env=my_env, preexec_fn=os.setsid, cwd=path_sim)
                time.sleep(1)
            if not self._proc_audio and self.params.observations.audio:
                path_audio = os.path.join(self.params.SIM_PATH, 'r2sim')
                self._logger.info('Starting audio server at %s with port %d' % (path_audio, self.params.audio.port))

                r2sim_verbosity = 2 if self.params.audio.get('debug',False) else 1
                r2sim_cmd = ['bin/r2sim',
                             '-tcp_port', str(self.params.audio.port),
                             '-conf','config/r2sim.conf',
                             '-verbosity', str(r2sim_verbosity)]
                if self.params.audio.get('debug_memory', False):
                    r2sim_cmd = ['valgrind', '--leak-check=yes'] + r2sim_cmd
                self._proc_audio = BackgroundPopen('audioserver', self._get_logger('audioserver'),
                                                   out_handler=None, err_handler=None,
                                                   args=r2sim_cmd,
                                                   #bufsize=0,
                                                   preexec_fn=os.setsid, cwd=path_audio)
                time.sleep(1)
            if not self.check_status():
                return False
        if not self._sio:
            self._sio = SocketIO(self.params.host, self.params.port)
            self._sio.on('connect', self.on_connect)
            self._sio.on('disconnect', self.on_disconnect)
            self._sio.on('reconnect', self.on_reconnect)
        return True

    def restart_child_servers(self, randomize_ports=False, seconds=1):
        # Maybe something happened to our servers
        # Let's stop and restart!
        self._restarts += 1
        self._logger.info(self.id + ':Restart %d' % self._restarts)

        # FULL CLOSE
        # NOTE: set sio to none so it will be recreated again
        # Hypothetically, it should reconnected as long as simserver reuses the same port (but something goes wrong)
        self.close(seconds=seconds)
        self._sio = None

        # Partial close (not fully working)
        #self.running = False
        #self._rpc('close', seconds=seconds)  # Try to be good and tell other side we are closing

        # Stop servers
        self.stop_child_servers()

        # Restart servers
        if randomize_ports:
            # Only audio port need to be randomized (sio port is okay)
            self.params.audio.port = common.get_random_port()
        return self.start_child_servers()

    def restart(self, randomize_ports=False, seconds=1):
        self.restart_child_servers(randomize_ports, seconds)
        return self.start()

    def check_resources(self):
        resources_self = resource.getrusage(resource.RUSAGE_SELF)
        resources_children = resource.getrusage(resource.RUSAGE_CHILDREN)
        resources = { 'self': resources_self, 'children': resources_children }
        self._logger.info(pprint.pformat(resources))
        return resources

    def check_status(self):
        ok = True
        if self._proc_sim:
            rv = self._proc_sim.poll()
            if rv is not None:
                self._logger.info(self.id + ':sim server has exited with rv %d' % rv)
                self._proc_sim = None
                ok = False
        else:
            ok = False

        if self._proc_audio:
            rv = self._proc_audio.poll()
            if rv is not None:
                self._logger.info(self.id + ':audio simulator has exited with rv %d' % rv)
                self._proc_audio = None
                ok = False
        else:
            ok = not self.params.observations.audio

        return ok

    def start(self):
        """Starts the simulation. Returns summary of started configuration."""
        started = self.start_child_servers()
        if not started:
            self.running = False
            return False
        self.start_time = time.time()
        self.running = True
        self._rpc('start', self.params, self.on_started)
        return self.start_summary_info

    def init(self):
        """Initializes the simulation. Returns success."""
        started = self.start_child_servers()
        if not started:
            self.running = False
            return False
        return self._rpc('init', self.params, self.on_inited)

    def close(self, seconds=None):
        """Stops the simulation. Returns success."""
        self.start_summary_info = None
        res = self._rpc('close', seconds=seconds)
        self.running = False
        self._sio.disconnect()
        return res

    def seed(self, s):
        """Sets the random number seed for the simulator. Returns success."""
        return self._rpc('seed', s)

    def reset(self):
        """Resets the simulation. Returns summary of current configuration."""
        self._rpc('reset', callback=self.on_reset)
        return self.start_summary_info

    def move_to(self, pos, angle):
        """Move agent to position (x,y,z) and facing direction with angle degrees to +X axis. Returns success."""
        return self._rpc('move_to', {'position': pos, 'angle': angle})

    def set_goal(self, goal):
        """Set agent goal. Returns success."""
        return self._rpc('set_goal', goal)

    def set_scene(self, id):
        """Sets the scene in which simulator will run. Returns success."""
        return self._rpc('configure', { 'scene': { 'fullId': id }})

    def configure(self, config):
        """Sets the simulator configuration. Returns success."""
        if not config:  # check for empty config
            return True
        return self._rpc('configure', config)

    def step(self, action, frame_skip):
        """Takes simulation step carrying out action frame_skip times"""
        if action is None:
            action = {}
        if type(action) is list:
            for a in action:
                a['frame_skip'] = frame_skip
        else:
            action['frame_skip'] = frame_skip
        return self._rpc('action', action, self.on_observation)

    def get_last_observation(self):
        return self._last_observation

    def get_scene_data(self):
        """Returns metadata about current scene: { id: scene_id, bbox: {min, max} }"""
        return self._rpc('get_scene_data')

    def get_action_trace(self):
        """Returns trace of actions in current session"""
        return self._rpc('get_action_trace')

    def get_observation_space(self):
        """Return observation space"""
        obs_meta = self._rpc('get_observation_metadata')['data']
        sensors = obs_meta.get('sensors')
        sensor_obs_space = {k: Simulator.BoxSpace(range=s.get('dataRange'), shape=s.get('shape')) for k, s in sensors.items()}
        meas = obs_meta.get('measurements')
        meas_obs_space = {k: Simulator.BoxSpace(range=s.get('dataRange'), shape=s.get('shape')) for k, s in meas.items()}
        return {'sensors': sensor_obs_space, 'measurements': meas_obs_space}

    def __process_color(self, name, rgb):
        """Converts rgb bytes to Image and reshapes"""
        frame = rgb['data']
        encoding = rgb.get('encoding')
        data = None
        image = None

        # RGB image
        mode = 'RGBA'
        if encoding == 'rgba':
            data = np.reshape(frame, rgb['shape'])
        elif encoding == 'gray':
            mode = 'L'
            data = np.reshape(frame, (rgb['shape'][0], rgb['shape'][1]))

        if self.params.get('save_png'):
            if image is None:
                image = Image.frombytes(mode,(data.shape[0], data.shape[1]),data)
            cnt = self.stats_counter['frames_received']
            image.save(os.path.join(self._output_dir, name + ('_%d.png' % cnt)))

        return {'image': image, 'data': data}

    def __process_depth(self, name, depth):
        """Converts depth bytes to Image and reshapes"""
        frame = depth['data']
        encoding = depth.get('encoding')
        data = None
        data_clean = None
        image = None

        # depths
        #self._logger.info('frame length %d', len(frame))
        #self._logger.info('shape %s', depth['shape'])
        mode = 'RGBA'
        if encoding == 'rgba':
            data = np.reshape(frame, depth['shape'])
        elif encoding == 'depth' or encoding == 'binned':
            #dims = (depth['shape'][0], depth['shape'][1])
            #self._logger.info(dims)
            data = np.reshape(frame, (depth['shape'][0], depth['shape'][1]))
            mode = 'L'
            # TODO: need to make sure in meters and is float32 for depth sensor noise simulation
            depth_sensor = self._sensors_by_name[name]
            if depth_sensor.noise_sim is not None:
                # Simulate noise
                data_clean = np.copy(data)  # TODO: Is this copying unnecessarily expensive, should there be a flag guarding against this?
                depth_sensor.noise_sim.simulate(data)

        if self.params.get('save_png'):
            if image is None:
                # self._logger.info('type is %s' % type(data))
                d = data.astype(np.float32)
                d = (d * (255.0 / np.max(d))).astype(np.uint8)
                image = Image.frombytes(mode,(d.shape[0], d.shape[1]),d)
            cnt = self.stats_counter['frames_received']
            image.save(os.path.join(self._output_dir, name + ('_%d.png' % cnt)))
        return {'image': image, 'data': data, 'data_clean': data_clean}

    def __process_camera_frame(self, name, f):
        """Converts generic camera based frame (assume to be rgba) bytes to Image and reshapes"""
        data = np.reshape(f['data'], f['shape'])
        data_viz = None
        if 'data_viz' in f:
            data_viz = np.reshape(f['data_viz'], f['shape'])

        image = None
        if self.params.get('save_png'):
            if image is None:
                imgd = data_viz if data_viz is not None else data
                image = Image.frombytes('RGBA',(imgd.shape[0], imgd.shape[1]),imgd)
            cnt = self.stats_counter['frames_received']
            image.save(os.path.join(self._output_dir, name + ('_%d.png' % cnt)))

        return {'image': image, 'data': data, 'data_viz': data_viz}

    def __process_audio(self, name, audio):
        """Saves audio """
        data = audio['data']
        sample_rate = audio.get('sampleRate')
        encoding = audio.get('encoding')
        # self._logger.info('Sampling rate is %d' % sample_rate)

        # TODO: Change save_png flag to more generic save sensor output flag
        if self.params.get('save_png'):
            wavfile.write(os.path.join(self._output_dir, name + '.wav'), sample_rate, data)
            np.savetxt(os.path.join(self._output_dir, name + '.wav.txt'), data)

        return {'data': data}

    def __process_force(self, name, force):
        data = force['data']
        # TODO: Change save_png flag to more generic save sensor output flag
        if self.params.get('save_png'):
            plt = common.bearing_plot(data)
            cnt = self.stats_counter['frames_received']
            plt.savefig(os.path.join(self._output_dir, name + ('_%d.png' % cnt)), dpi=25)
            plt.close()
        return {'data': data}

    def __process_observation(self, data):
        observation = data['observation']
        sensors = observation['sensors']
        if observation.get('map') is not None:
            converted = self.__process_camera_frame('map', observation['map'])
            observation['map']['data'] = converted['data']
        # Go over observations from sensors and process them
        for name, sensor_data in sensors.items():
            sensor_type = sensor_data.get('type')
            if sensor_type == 'color':
                converted_rgb = self.__process_color(name, sensor_data)
                sensor_data['data'] = converted_rgb['data']
            elif sensor_type == 'depth':
                converted_depth = self.__process_depth(name, sensor_data)
                sensor_data['data'] = converted_depth['data']
                sensor_data['data_clean'] = converted_depth['data_clean']
            elif sensor_type == 'audio':
                converted_audio = self.__process_audio(name, sensor_data)
                sensor_data['data'] = converted_audio['data']
            elif sensor_type == 'force':
                converted_force = self.__process_force(name, sensor_data)
                sensor_data['data'] = converted_force['data']
            else:
                if (len(sensor_data['shape']) == 3 and sensor_data['shape'][2] == 4):
                    # Frame from camera like sensor?
                    converted = self.__process_camera_frame(name, sensor_data)
                    sensor_data['data'] = converted['data']
                    sensor_data['data_viz'] = converted['data_viz']

    def __process_goal_observations(self, goal_observations):
        if goal_observations is not None:
            for i, obs in enumerate(goal_observations):
                self.__process_observation(obs)

    def on_observation(self, message):
        self.stats_counter.update(['frames_received'])
        data = message.get('data') if message is not None else None
        if data is not None:
            if 'observation' not in data:
                err_str = self.id + ':Received data message with no observation : ' + str(data)
                self._logger.error(err_str)
                raise Exception(err_str)
            self.__process_observation(data)
        else:
            self.stats_counter.update(['empty_frames_received'])
        self._last_observation = data  # save last observation
        return data

    def on_started(self, message):
        if message is None or message.get('status') == 'error':
            return False
        else:
            self.start_summary_info = message.get('data')
            self.__process_goal_observations(self.start_summary_info.get('goalObservations'))
            self.step({'name': 'idle'}, 1)  # take a first step to fill last observation
            #self._logger.info('started')
            return True

    def on_reset(self, message):
        if message is None or message.get('status') == 'error':
            return False
        else:
            self.start_summary_info = message.get('data')
            self.__process_goal_observations(self.start_summary_info.get('goalObservations'))
            self.step({'name': 'idle'}, 1)  # take a first step to fill last observation
            return True

    def on_inited(self, message):
        if message is None or message.get('status') == 'error':
            return False
        else:
            self._logger.info(self.id + ':inited')
            return True

    def on_connect(self):
        self._logger.info(self.id + ':connect')

    def on_disconnect(self):
        self._logger.info(self.id + ':disconnect')

    def on_reconnect(self):
        self._logger.info(self.id + ':reconnect')

    def flush_logs(self):
        if self._proc_sim:
            self._proc_sim.flush()
        if self._proc_audio:
            self._proc_audio.flush()
        if self._logger is not None:
            for handler in self._logger.handlers:
                handler.flush()

    def stop_child_servers(self):
        self._logger.info(self.id + ':Stopping child servers')
        if self._proc_sim:
            self._logger.info(self.id + ':Killing sim pid %d' % self._proc_sim.pid)
            try:
                os.killpg(os.getpgid(self._proc_sim.pid), signal.SIGTERM)
            except:
                self._logger.info(self.id + ':Error killing sim server')
            self._proc_sim.close()
            self._proc_sim = None
        if self._proc_audio:
            self._logger.info(self.id + ':Killing audio sim pid %d' % self._proc_audio.pid)
            try:
                os.killpg(os.getpgid(self._proc_audio.pid), signal.SIGTERM)
            except:
                self._logger.info(self.id + ':Error killing audio sim')
            self._proc_audio.close()
            self._proc_audio = None
        self._logger.info(self.id + ':Stopped child servers')

    def kill(self):
        self._logger.info(self.id + ':Stopping the simulator')
        self._logger.info(self.stats_counter)
        if self.running:
            self.close(seconds=1)
        self.stop_child_servers()
        self._logger.info(self.id + ':Simulator killed.')
        self.killed = True
