import argparse
import csv
import json
import os

from easydict import EasyDict as edict
from minos.config import sim_config

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def add_sim_args_basic(parser):
    parser.add_argument('--width', type=int,
                        default=128,
                        help='Image width')
    parser.add_argument('--height', type=int,
                        default=128,
                        help='Image height')
    parser.add_argument('--color_encoding',
                        help='Color frame encoding format (rgba|gray)')
    parser.add_argument('--log_action_trace',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to log action and state traces')
    parser.add_argument('--save_png',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to write out png sequence')
    parser.add_argument('--agent_config',
                        help='Agent configuration to use (corresponds to agent config JSON file in config dir)')
    return parser


def add_sim_args(parser):
    parser.add_argument('--host',
                        help='Simulator server host')
    parser.add_argument('--port', type=int,
                        help='Simulator server port')
    parser.add_argument('--busywait', type=int,
                        default=0,
                        help='Number of seconds for simulator server to busywait (test busy server)')
    parser.add_argument('--ping_timeout', type=int,
                        help='Number of seconds between ping/pong before client timeout')
    parser.add_argument('--assets',
                        help='Additional custom assets to load into the simulator')
    parser.add_argument('--width', type=int,
                        default=256,
                        help='Image width')
    parser.add_argument('--height', type=int,
                        default=256,
                        help='Image height')
    parser.add_argument('--color_encoding',
                        help='Color frame encoding format (rgba|gray)')
    parser.add_argument('--save_video',
                        help='Video filename to save frames')
    parser.add_argument('--use_lights',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to enable lights')
    parser.add_argument('--use_shadows',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to use shadows')
    parser.add_argument('--default_light_state',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to have lights on by default or not')
    parser.add_argument('--manual_start',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to manual start the server')
    parser.add_argument('--depth',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Depth frames enabled')
    parser.add_argument('--depth_noise',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Depth gaussian noise enabled')
    parser.add_argument('--audio',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Audio enabled')
    parser.add_argument('--collision_mode',
                        default='raycast',
                        help='Collision detection mode')
    parser.add_argument('--forces',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Collision forces enabled')
    parser.add_argument('-s', '--sensors',
                        action='append',
                        choices=['normal', 'objectId', 'objectType', 'roomType', 'roomId', 'map'],
                        default=[],
                        help='Additional sensors to enable')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--empty_room',
                       nargs='?', const='True',
                       type=str2bool,
                       help='Remove furniture and partitions')
    group.add_argument('--arch_only',
                       nargs='?', const='True',
                       type=str2bool,
                       help='Remove furniture')
    parser.add_argument('--retexture',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Retexture scenes')
    parser.add_argument('--texture_set',
                        nargs='?',
                        choices=['train', 'val', 'test', 'all'],
                        help='Texture set to use for retexturing')
    parser.add_argument('--mirrors',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Enable mirrors')
    parser.add_argument('--add_object_at_goal',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Add visible target object at goal location')
    parser.add_argument('--dataset',
                        help='Dataset for scene ids')
    parser.add_argument('--log_action_trace',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to log action and state traces')
    parser.add_argument('--save_png',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Whether to write out png sequence')
    parser.add_argument('--debug',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Debug visualization mode')
    parser.add_argument('--debug_audio_memory',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Debug audio memory')
    parser.add_argument('--profile_cpu',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Profile cpu usage (by simserver)')
    parser.add_argument('--debug_mem',
                        nargs='?', const='True',
                        type=str2bool,
                        help='Debug memory usage (by simserver)')
    parser.add_argument('--scene_ids', nargs='*',
                        default=['00a76592d5cc7d92eef022393784a2de', '066e8a32fd15541e814a9eafa82abf5d',
                                 '11be354e8dbd5d7275c486a5037ea949'],
                        help='Scene ids to load')
    parser.add_argument('--level',
                        help='Level to load')
    parser.add_argument('--room',
                        help='Room id to load')
    parser.add_argument('--sensors_config',
                        help='Sensor configuration to use (corresponds to sensors config JSON file in config dir)')
    parser.add_argument('--agent_config',
                        help='Agent configuration to use (corresponds to agent config JSON file in config dir)')
    parser.add_argument('--env_config',
                        default='objectgoal_suncg_sf',
                        help='Environment configuration file to use (corresponds to py file in config/envs dir)')
    parser.add_argument('--scene_format',
                        help='Scene format to use')
    parser.add_argument('--roomtypes_file',
                        help='File to use for room types')
    parser.add_argument('--objecttypes_file',
                        help='File to use for object types')
    return parser


# Read lines and returns as list (ignores empty lines)
def read_lines(filename):
    lines = []
    with open(filename) as x:
        for line in x:
            line = line.strip()
            if len(line):
                lines.append(line)
    return lines


def parse_sim_args(parser):
    add_sim_args(parser)
    args = parser.parse_args()

    if len(args.scene_ids) == 1:
        if args.scene_ids[0].endswith('txt'):
            # Read scene ids from file
            args.scene_ids = read_lines(args.scene_ids[0])
        elif args.scene_ids[0].endswith('csv'):
            # Read scene ids from file
            csvfile = args.scene_ids[0]
            with open(csvfile) as f:
                reader = csv.DictReader(f)
                args.scene_ids = [r.get('id') for r in reader]

    if args.depth_noise:
        args.sensors = [{'name': 'depth', 'noise': True}]
    args.observations = {'color': True, 'depth': args.depth, 'forces': args.forces, 'audio': args.audio}
    for s in args.sensors:
        args.observations[s] = True
    args.collision_detection = {'mode': args.collision_mode}
    if args.navmap and type(args.navmap) == bool and sim_config.sim_defaults.get('navmap'):
        args.navmap = None

    if args.add_object_at_goal:
        # print('add object at goal')
        args.modifications = [{
            'name': 'add',
            'modelIds': 'p5d.s__1957',
            'format': 'obj',
            'positionAt': 'goal'
        }]

    args.audio = {'debug': args.debug, 'debug_memory': args.debug_audio_memory}
    args.actionTraceLogFields = ['forces']
    args.auto_start = not args.manual_start
    if not args.auto_start:
        args.audio = {'port': 1112}
        args.port = 4899

    sim_args = sim_config.get(args.env_config, vars(args))
    sim_args = edict(sim_args)
    return sim_args
