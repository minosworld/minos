import math
import numpy as np
import random
import sys
import time

from .Simulator import Simulator
from . import common


class RoomSimulator:
    """Provides interface to an indoor simulation server"""

    def __init__(self, params):
        self.my_rand = random.Random()
        if 'seed' in params:
            self.my_rand.seed(params['seed'])

        self.reward_type = params.get('reward_type', 'dist_time')
        self.frame_skip = params['frame_skip']
        self.resolution = params['resolution']
        self.measure_fun = params['measure_fun']
        self.episode_schedulers = common.create_episode_schedulers(params)
        self.curr_schedule = params.get('episode_schedule', 'train')
        self.available_controls = params.get('available_controls',
                                             ['turnLeft', 'turnRight', 'forwards'])
        self.num_meas = self.measure_fun.num_meas
        self.params = params

        self.continuous_controls = np.array([False for _ in self.available_controls])
        self.discrete_controls = np.invert(self.continuous_controls)
        self.num_buttons = len(self.discrete_controls)

        self.initialized = False
        self.episode_is_running = False
        self.num_channels = 1
        self.num_episodes = 0
        self.num_episodes_this_scene = 0
        self.num_episodes_since_restart = 0
        self.num_steps_this_episode = 0
        self.start_time_this_episode = None
        self.start_config_this_episode = None
        self.start_dist = -1
        self.scene_id = None

        self.sim = Simulator(params)
        self.sid = self.sim.id

    def get_random_action(self):
        return [(self.my_rand.random() >= .5) for _ in range(self.num_buttons)]

    def end_episode(self, success, print_episode_stats=False):
        if print_episode_stats and self.start_time_this_episode is not None:
            time_taken = time.time() - self.start_time_this_episode
            dist = self.get_distance_to_goal()
            end_dist = dist[0] if len(dist) > 0 else -1
            sconf = self.start_config_this_episode
            has_spath = sconf and 'shortestPath' in sconf
            path_start_dist = sconf['shortestPath'].get('distance', -1.0) if has_spath else -1.0
            if not path_start_dist:
                path_start_dist = -1.0
            path_numdoors = len(sconf['shortestPath'].get('doors', [])) if has_spath else 0
            path_numrooms = len(sconf['shortestPath'].get('rooms', [])) if has_spath else 0
            print('%s:EPISODE:%d,%s,%f,%d,%s,%f,%f,%f,%f,%d,%d'
                  % (self.sim.id, self.num_episodes, self.scene_id, time_taken, self.num_steps_this_episode,
                     success, self.num_steps_this_episode / time_taken, self.start_dist, end_dist, path_start_dist,
                     path_numdoors, path_numrooms))
            print('%s:EPINFO:%d,%s' % (self.sim.id, self.num_episodes, str(self.start_config_this_episode)))
            sys.stdout.flush()
        self.episode_is_running = False

    def new_episode(self):
        self.episode_is_running = True
        self.num_episodes += 1
        self.num_steps_this_episode = 0
        self.start_time_this_episode = time.time()

        # Check if we should restart
        self.num_episodes_since_restart += 1
        num_episodes_per_restart = self.params.get('num_episodes_per_restart', 0)
        restart_needed = num_episodes_per_restart and self.num_episodes_since_restart > num_episodes_per_restart
        if restart_needed:
            self.sim.restart_child_servers(randomize_ports=True)
            self.sim.init()
            self.num_episodes_since_restart = 1

        # update episode configuration
        self.num_episodes_this_scene += 1
        ep_settings = self.episode_schedulers[self.curr_schedule].next_episode()
        if not 'level' in ep_settings:  # default to 0th level
            ep_settings['level'] = 0  # NOTE: this assumes that we only use one level
        config = {}
        scene_changed = ep_settings['scene_id'] != self.scene_id
        if 'goal' in ep_settings:
            if self.params['task'] == 'room_goal':
                room_id = ep_settings['room_id']
                config['goal'] = {'type': 'room', 'roomIds': [room_id]}
            else:
                object_id = ep_settings['goal']['id']
                if object_id:
                    config['goal'] = {'type': 'object', 'objectIds': [object_id]}
        #else:  # remove objectIds to reset to default goal selection strategy
            #config['goal'] = {'type': 'position', 'objectIds': None, 'roomIds': None}
        if 'start' in ep_settings:
            config['start'] = ep_settings['start']
        self.sim.seed(self.my_rand.randint(0, 123456789))
        if restart_needed or scene_changed:
            if scene_changed:
                self.num_episodes_this_scene = 1
            config['scene'] = {'fullId': self.params['scene']['dataset'] + '.' + ep_settings['scene_id'],
                               'level': ep_settings['level'],
                               'textureSet': self.curr_schedule}
            # print('restart_needed or scene_changed: config', config, 'ep_settings', ep_settings)
            self.sim.configure(config)
            result = self.sim.start()
        else:
            # print('reset: config', config, 'ep_settings', ep_settings)
            self.sim.configure(config)
            result = self.sim.reset()
        # update our current scene id
        self.scene_id = ep_settings['scene_id']

        # set starting dist to goal from last observation
        if result:
            if 'roomType' in result['goal'] and hasattr(self.sim, 'roomTypes'):
                result['goal']['roomTypeEncoded'] = self.sim.roomTypes.get_index_one_hot(result['goal']['roomType'])
            dist = self.get_distance_to_goal()
            if len(dist):
                self.start_dist = dist[0]
            else:
                print('new_episode() could not get valid starting distance, setting to -1')
                self.start_dist = -1
        else:  # if failure, print error and reset start_dist, else pull out start_dist
            print('new_episode(): failure in start/reset')
            self.start_dist = -1

        if 'goalObservations' in result:
            del result['goalObservations']
        self.measure_fun.reset()
        self.start_config_this_episode = result
        return result

    def get_distance_to_goal(self):
        last_obs = self.sim.get_last_observation()
        measurements = last_obs['observation'].get('measurements')
        dist = measurements.get('distance_to_goal')
        return dist

    def init(self):
        if not self.initialized:
            self.sim.init()
            self.initialized = True
        if not self.episode_is_running:
            return self.new_episode()

    def close_game(self):
        if self.episode_is_running:
            self.end_episode(None, print_episode_stats=False)
        if self.initialized:
            self.sim.close()
            self.sim.kill()
            self.initialized = False

    def reset(self, force=False):
        episode_info = self.init()
        if not episode_info:
            # no episode_info
            if force or self.num_steps_this_episode > 0:
                # Start new episode if previous episode has been acted in or forcing reset
                #print('Reset: end episode')
                self.end_episode(False, print_episode_stats=True)
                episode_info = self.new_episode()
            else:
                episode_info = self.start_config_this_episode
        observation = self.sim.get_last_observation()
        output = self._augment_response(observation, None)
        return {'episode_info': episode_info, 'observation': output}

    def step(self, action):
        self.init()

        act_msg = {'name': 'idle', 'strength': 1, 'angle': math.radians(5)}
        actions = []
        for action_idx, do_action in enumerate(action):
            if do_action:
                act_msg['name'] = self.available_controls[action_idx]
                actions.append(act_msg.copy())
        if len(actions) == 0:
            act_msg['name'] = 'idle'
            actions.append(act_msg)

        last_observation = self.sim.get_last_observation()  # for computing differences
        response = self.sim.step(actions, self.frame_skip)
        self.num_steps_this_episode += self.frame_skip
        response = self._augment_response(response, last_observation)

        if response['terminals']:
            self.end_episode(response['success'], print_episode_stats=True)

        return response

    def _augment_response(self, response, last_observation):
        observation = response['observation']

        # TODO: move encoding to Simulator.py?
        room_info = observation.get('roomInfo')
        if room_info and self.sim.roomTypes:
            rt = self.sim.roomTypes.get_index_one_hot(room_info['roomType'] if room_info else '')
            room_info['roomTypeEncoded'] = rt  # Updates observation!!!

        meas, success, term = self.measure_fun.measure(observation, self.start_config_this_episode)
        response['success'] = success
        response['measurements'] = meas
        response['rewards'] = common.observation_to_reward(self.reward_type, observation, meas, term, success,
                                                           last_observation, self.frame_skip)
        response['terminals'] = term
        #response['objectives'] = self.measure_fun.get_objectives(observation, self.start_config_this_episode)
        return response

    def get_observation_space(self, outputs):
        # NOTE: This forces the game to start and a new episode created (it helps get everything setup)
        # TODO: Don't create new episode if not needed
        self.init()
        sim_obs_space = self.sim.get_observation_space()
        sens_space = sim_obs_space.get('sensors')
        obs_space = {}
        # TODO: add observation space for roomType and goalRoomType
        for outp in outputs:
            if outp == 'color':
                obs_space[outp] = sens_space.get('color')
            elif outp == 'depth':
                obs_space[outp] = sens_space.get('depth')
            elif outp == 'depth_clean':
                obs_space[outp] = sens_space.get('depth')
            elif outp == 'force':
                obs_space[outp] = sens_space.get('force')
            #elif outp == 'audiopath':
            elif outp == 'audio':
                obs_space[outp] = sens_space.get('audio')
            elif outp == 'measurements':
                obs_space[outp] = sim_obs_space.get('measurements')
        return obs_space

    def close(self):
        self.close_game()

    def set_episode_schedule(self, schedule, end_current_episode=False):
        print('setting episode schedule to ', schedule)
        if schedule not in self.episode_schedulers:
            raise Exception('Unknown episode schedule type: ' + schedule)
        self.curr_schedule = schedule
        if end_current_episode and self.episode_is_running:
            self.end_episode(None, print_episode_stats=False)

    def get_episode_scheduler(self, schedule):
        return self.episode_schedulers[schedule]

    def is_all_scheduled_episodes_done(self):
        total_episodes = self.get_episode_scheduler(self.curr_schedule).num_states()
        return self.num_episodes > total_episodes

