import atexit
import csv
import os
import platform
import psutil
import random

import matplotlib.pyplot as plt
import numpy as np

from .util.EpisodeScheduler import EpisodeScheduler
from .util.StateSet import StateSet, Select, SelectPolicy


def get_random_port():
    rand = random.Random()
    while True:
        port = rand.randint(10000, 60000)
        my_os = platform.system()
        if 'Darwin' in my_os:  # checking open ports with psutil on Mac requires root!
            return port
        used_ports = [x.laddr[1] for x in psutil.net_connections()]
        if port not in used_ports:
            return port


def add_localhost_to_noproxy():
    no_proxy = os.environ.get('no_proxy', None)
    no_proxy_parts = no_proxy.split(',') if no_proxy else []
    localhosts = ['127.0.0.1', 'localhost']
    updated = False
    for localhost in localhosts:
        if localhost not in no_proxy_parts:
            no_proxy_parts.append(localhost)
            updated = True
    if updated:
        os.environ['no_proxy'] = ','.join(no_proxy_parts)


def ensure_dir_exists(path):
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise


def get_goal_for_task(task, goals=None):
    # set goal depending on task type
    if task == 'room_goal':
        goal = {'minRooms': 1, 'roomTypes': 'any', 'select': 'random'}
    elif task == 'point_goal':
        goal = {'position': 'random', 'radius': 0.25}
    elif task == 'door_goal':
        goal = {'categories': ['arch', 'door'], 'select': 'random'}
    else:  # default to door_goal
        goal = {'categories': ['arch', 'door'], 'select': 'random'}

    # if objectId goals provided, override default task goals
    if goals:
        goal = {'objectIds': [g['actionArgs'] for g in goals]}

    return goal


def observation_to_reward(reward_type, observation, meas, term, success, last_observation, frame_skip):
    if reward_type == 'path_delta':
        if term and success:
            return 10.0
        rwrd = -0.1 * frame_skip
        if observation.get('collision'):
            rwrd = rwrd - 0.3 * frame_skip

        if last_observation:
            path = observation['measurements'].get('shortest_path_to_goal', None)
            if path and 'distance' in path:
                last_meas = last_observation['observation']['measurements']
                last_path = last_meas.get('shortest_path_to_goal', None)
                if last_path and 'distance' in last_path:
                    delta_dist = last_path['distance'] - path['distance']
                    # NOTE: factor to promotove positive steps more than negative steps, and make close to +/-1
                    delta_dist_factor = 10 if delta_dist > 0 else 2
                    rwrd = rwrd + delta_dist_factor * delta_dist
        return rwrd
    elif reward_type == 'dist_time':
        if last_observation is None:
            return 0
        last_obs = last_observation['observation']
        last_meas = last_obs['measurements']
        last_time = last_obs['time']
        last_dist = last_meas['distance_to_goal'] if 'distance_to_goal' in last_meas else 0
        curr_meas = observation['measurements']
        curr_time = observation['time']
        curr_dist = curr_meas['distance_to_goal'] if 'distance_to_goal' in curr_meas else 0
        delta_time = last_time - curr_time
        delta_dist = last_dist[0] - curr_dist[0]
        rwrd = delta_dist + delta_time
        return rwrd
    elif reward_type == 'distpath_time':
        if last_observation is None:
            return 0
        last_obs = last_observation['observation']
        last_time = last_obs['time']
        curr_meas = observation['measurements']
        curr_time = observation['time']
        delta_time = last_time - curr_time
        delta_dist = 0
        path = curr_meas.get('shortest_path_to_goal', None)
        if path and 'distance' in path:
            last_meas = last_obs['measurements']
            last_path = last_meas.get('shortest_path_to_goal', None)
            if last_path and 'distance' in last_path:
                delta_dist = last_path['distance'] - path['distance']
        return delta_dist + delta_time
    else:
        raise Exception('Unknown reward type: ' + reward_type)


# load scenes dataset file and splits
def load_scenes_file(csvfile):
    with open(csvfile) as f:
        reader = csv.DictReader(f)
        all_scenes = [r for r in reader]
        for r in all_scenes:
            for v in ['nrooms', 'nobjects']:
                r[v] = int(r[v])
            for v in ['dimX', 'dimY', 'dimZ', 'floorArea']:
                r[v] = float(r[v])
        all_scenes.sort(key=lambda x: x['nobjects'])
        train_scenes = [r for r in all_scenes if r['set'] == 'train']
        val_scenes = [r for r in all_scenes if r['set'] == 'val']
        test_scenes = [r for r in all_scenes if r['set'] == 'test']
        scenes_dict = {'all': all_scenes, 'train': train_scenes,
                       'val': val_scenes, 'test': test_scenes}
        return scenes_dict


# graceful cleanup on sigint (ctrl-c)
def attach_exit_handler(sims):
    if not type(sims) == list:
        sims = [sims]

    def handler():
        for sim in sims:
            if sim.running:
                sim.close()
                sim.kill()
    atexit.register(handler)


def bearing_plot(x, sum_axis=1, bottom=0, loc_0='S'):
    n = x.shape[(sum_axis+1) % 1]  # number of radial bins

    fig = plt.figure(figsize=(10, 10), tight_layout=True)
    ax = plt.subplot(111, projection='polar')
    fig.add_axes(ax)

    if ax is None:
        ax = plt.subplot(111, polar=True)
    theta = np.linspace(0.0, 2*np.pi, n+1)
    if len(x.shape) > 1:
        radii = np.sum(x, sum_axis)
        ax.set_rmax(x.shape[1])  # Assume each element in axis 1 is normalized to 1
    else:
        radii = x
        ax.set_rmax(1) # Assume each element in axis 1 is normalized to 1
    width = (2*np.pi) / (n*2)

    ax.bar(theta[:-1], radii, width=width, bottom=bottom,
           facecolor=(255/255, 127/255, 14/255), edgecolor='k', linewidth=2)
    ax.set_theta_zero_location(loc_0)
    # ax.grid(False)
    ax.set_yticklabels([])
    ax.set_xticklabels([])

    return plt


def create_episode_schedulers(params):
    scene_filter = params.get('scene_filter', None)
    episode_filter = params.get('episode_filter', None)
    max_states_per_scene = params.get('max_states_per_scene', 100)
    seed = params.get('seed', 0)
    episodes_per_scene_train = params.get('episodes_per_scene_train', 10)
    episodes_per_scene_test = params.get('episodes_per_scene_test', 10)
    scenescsv = params['scenes_file']
    states = params['states_file']
    state_set = StateSet(scenescsv, [states], scene_filter, episode_filter,
                         select_policy=SelectPolicy(Select.RANGE_VALUE, 'pathDist'))
    state_set_splits = state_set.get_splits(max_states_per_scene)
    for k in state_set_splits:
        print(k + ':' + str(len(state_set_splits[k].states)) + ' episodes')

    train_scheduler = EpisodeScheduler(state_set_splits['train'], schedule='random', seed=seed,
                                       num_episodes_per_scene=episodes_per_scene_train)
    val_scheduler = EpisodeScheduler(state_set_splits['val'], schedule='fixed', seed=seed,
                                     num_episodes_per_scene=episodes_per_scene_test)
    test_scheduler = EpisodeScheduler(state_set_splits['test'], schedule='fixed', seed=seed,
                                      num_episodes_per_scene=episodes_per_scene_test)
    return {'train': train_scheduler, 'val': val_scheduler, 'test': test_scheduler}
