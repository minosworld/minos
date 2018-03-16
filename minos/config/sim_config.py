import collections
import copy
import json
import os
import pprint
import time
from minos.lib.util import measures


def resolve_relative_path(path):
    return os.path.join(os.path.dirname(__file__), path)


def get_scene_params(arch_only=False, retexture=False, empty_room=False, dataset='p5dScene'):
    if arch_only and empty_room:
        raise Exception('Cannot specify both arch_only and empty_room for scene params')
    replace_doors_file = resolve_relative_path('./replace_doors.json')
    with open(replace_doors_file, 'r') as f:
        replace_doors = json.load(f)
    return {
        'source': dataset,
        'archOnly': arch_only, 'retexture': retexture,
        'textureSet': 'train',
        'texturedObjects': 'all',
        'emptyRoom': empty_room,
        'hideCategories': ['person', 'plant'],
        'replaceModels': replace_doors,
        'createArch': True,
        'defaultModelFormat': 'obj' if dataset == 'p5dScene' else None,
        'defaultSceneFormat': 'suncg' if dataset == 'p5dScene' else None
    }


sim_defaults = {
    'simulator': 'room_simulator',
    'num_simulators': 1,

    # Shared RoomSimulator and DoomSimulator params
    'modalities': ['color', 'measurements'],
    'outputs': ['color', 'measurements', 'rewards', 'terminals'],
    'resolution': (84, 84),
    'frame_skip': 1,

    # RoomSimulator params (most are also Simulator.py params)
    'host': 'localhost',
    'log_action_trace': False,
    'auto_start': True,
    'collision_detection': {'mode': 'navgrid'},
    'navmap': {'refineGrid': True, 'autoUpdate': True, 'allowDiagonalMoves': True, 'reverseEdgeOrder': False},
    'reward_type': 'dist_time',
    'observations': {'color': True, 'forces': False, 'audio': False, 'objects': False, 'depth': False, 'map': False},
    'color_encoding': 'rgba',
    'scene': {'arch_only': False, 'retexture': False, 'empty_room': False, 'dataset': 'p5dScene'},

    # DoomSimulator params
    'config': '',            # Also in RoomSimulator but unused
    'color_mode': 'GRAY',
    'maps': ['MAP01'],       # Also in RoomSimulator but unused
    'switch_maps': False,
    'game_args': '',

    # task params
    'task': 'room_goal',
    'goal': {'roomTypes': 'any', 'select': 'random'},
    'scenes_file': '../data/scenes.multiroom.csv',
    'states_file': '../data/episode_states.suncg.csv.bz2',
    'roomtypes_file': '../data/roomTypes.suncg.csv',
    'num_episodes_per_restart': 1000,
    'num_episodes_per_scene': 10,
    'max_states_per_scene': 1,
    'episodes_per_scene_test': 1,  # DFP param
    'episodes_per_scene_train': 10,  # DFP param
    'episode_schedule': 'train',  # DFP param
    'measure_fun': measures.MeasureDistDirTime(),
}


def update_dict(d, u):
    if d and u:
        for k, v in u.items():
            if isinstance(v, collections.Mapping):
                d[k] = update_dict(d.get(k, {}), v)
            else:
                d[k] = v
    return d


def get(env_config, override_args=None, print_config=False):
    simargs = copy.copy(sim_defaults)
    if env_config:
        env = __import__('minos.config.envs.' + env_config, fromlist=['config'])
        simargs.update(env.config)

    # augmentation / setting of args
    s = simargs['scene']
    simargs['scene'] = get_scene_params(arch_only=s.get('arch_only', None),
                                        retexture=s.get('retexture', None),
                                        empty_room=s.get('empty_room', None),
                                        dataset=s.get('dataset', None))
    for path in ['scenes_file', 'states_file', 'roomtypes_file']:
        simargs[path] = resolve_relative_path(simargs[path])
    simargs['logdir'] = os.path.join('logs', time.strftime("%Y_%m_%d_%H_%M_%S"))

    update_dict(simargs, override_args)

    if print_config:
        pprint.pprint(simargs)

    return simargs
