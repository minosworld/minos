import collections
import copy
import json
import os
import pprint
import time
from minos.lib.util import measures


def resolve_relative_path(path):
    return os.path.join(os.path.dirname(__file__), path)


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
    'observations': {'color': True, 'forces': False, 'audio': False, 
        'normal': False, 'depth': False, 
        'objectId': False, 'objectType': False, 'roomType': False, 'roomId': False,
        'map': False},
    'color_encoding': 'rgba',
    'scene': {
        'arch_only': False, 'empty_room': False,
        'create_arch': True, 'dataset': 'p5dScene',
        'hide_categories': ['person', 'plant'],
        'retexture': True, 'texture_set': 'train', 'textured_objects': 'all',
    },

    # DoomSimulator params
    'config': '',            # Also in RoomSimulator but unused
    'color_mode': 'GRAY',
    'maps': ['MAP01'],       # Also in RoomSimulator but unused
    'switch_maps': False,
    'game_args': '',

    # task params
    'task': 'room_goal',
    'goal': {'type': 'room', 'roomTypes': 'any', 'select': 'random'},
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

    # these members are non-serializable
    'nonserializable': ['measure_fun', 'scene_filter', 'episode_filter']
}


def update_dict(d, u):
    if d and u:
        for k, v in u.items():
            if v is None:  # avoid overwriting with None
                continue
            if isinstance(v, collections.defaultdict):
                d[k] = update_dict(d.get(k, {}), v)
            else:
                d[k] = v
    return d


def get(env_config, override_args=None, print_config=False):
    simargs = copy.deepcopy(sim_defaults)
    if env_config:
        env = __import__('minos.config.envs.' + env_config, fromlist=['config'])
        update_dict(simargs, env.config)

    # augmentation / setting of simargs for scene configuration parameters
    s = {}
    s['arch_only'] = override_args.get('arch_only', None)
    s['retexture'] = override_args.get('retexture', None)
    s['empty_room'] = override_args.get('empty_room', None)
    s['enableMirrors'] = override_args.get('mirrors', None)
    s['room'] = override_args.get('room', None)
    s['texture_set'] = override_args.get('texture_set', None)
    s['format'] = override_args.get('scene_format', None)
    s['dataset'] = override_args.get('dataset', None)
    if s['arch_only'] and s['empty_room']:
        raise Exception('Cannot specify both arch_only and empty_room for scene params')
    replace_doors_file = resolve_relative_path('./replace_doors.json')
    with open(replace_doors_file, 'r') as f:
        replace_doors = json.load(f)
    s['replaceModels'] = replace_doors

    for path in ['scenes_file', 'states_file', 'roomtypes_file']:
        simargs[path] = resolve_relative_path(simargs[path])
    simargs['logdir'] = os.path.join('logs', time.strftime("%Y_%m_%d_%H_%M_%S"))

    # merge augmented scene object into simargs['scene']
    update_dict(simargs['scene'], s)
    clean_args = copy.deepcopy(override_args)
    # remove keys we used from top level of override_args
    for k in ['arch_only', 'retexture', 'empty_room', 'dataset', 'texture_set',
              'mirrors', 'room', 'scene_format']:
        if k in clean_args:
            del clean_args[k]
    # now merge remaining keys in at top level
    update_dict(simargs, clean_args)

    simargs['scene']['defaultModelFormat'] = 'obj' if simargs['scene']['dataset'] == 'p5dScene' else None
    simargs['scene']['defaultSceneFormat'] = 'suncg' if simargs['scene']['dataset'] == 'p5dScene' else None

    if 'scene_ids' in override_args:
        simargs['scene']['fullId'] = simargs['scene']['dataset'] + '.' + override_args.get('scene_ids')[0]

    if print_config:
        pprint.pprint(simargs)

    return simargs
