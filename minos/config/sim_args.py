import argparse
import csv
import json
import os

from minos.lib.common import get_goal_for_task
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
                        default='rgba',
                        help='Color frame encoding format (rgba|gray)')
    parser.add_argument('--log_action_trace', action='store_true',
                        default=False,
                        help='Whether to log action and state traces')
    parser.add_argument('--save_png', action='store_true',
                        default=False,
                        help='Whether to write out png sequence')
    parser.add_argument('--agent_config', type=str,
                        default='',
                        help='Agent configuration to use (corresponds to agent config JSON file in config dir)')
    return parser


def add_sim_args(parser):
    parser.add_argument('--host',
                        default='localhost',
                        help='Simulator server host')
    parser.add_argument('--port', type=int,
                        default=None,
                        help='Simulator server port')
    parser.add_argument('--busywait', type=int,
                        default=0,
                        help='Number of seconds for simulator server to busywait (test busy server)')
    parser.add_argument('--ping_timeout', type=int,
                        default=None,
                        help='Number of seconds between ping/pong before client timeout')
    parser.add_argument('--width', type=int,
                        default=256,
                        help='Image width')
    parser.add_argument('--height', type=int,
                        default=256,
                        help='Image height')
    parser.add_argument('--color_encoding',
                        default='rgba',
                        help='Color frame encoding format (rgba|gray)')
    parser.add_argument('--save_video', type=str,
                        default='',
                        help='Video filename to save frames')
    parser.add_argument('--use_lights', action='store_true',
                        help='Whether to enable lights')
    parser.add_argument('--use_shadows', action='store_true',
                        help='Whether to use shadows')
    parser.add_argument('--default_light_state', action='store_true',
                        help='Whether to have lights on by default or not')
    parser.add_argument('--manual_start', action='store_true',
                        default=False,
                        help='Whether to manual start the server')
    parser.add_argument('--depth', action='store_true',
                        default=False,
                        help='Depth frames enabled')
    parser.add_argument('--depth_noise', action='store_true',
                        default=False,
                        help='Depth gaussian noise enabled')
    parser.add_argument('--audio', action='store_true',
                        default=False,
                        help='Audio enabled')
    parser.add_argument('--collision_mode',
                        default='raycast',
                        help='Collision detection mode')
    parser.add_argument('--forces',
                        nargs='?', const='True',
                        default=True,
                        type=str2bool,
                        help='Collision forces enabled')
    parser.add_argument('-s', '--sensors',
                        action='append',
                        choices=['normal', 'objectId', 'objectType', 'roomType', 'roomId', 'map'],
                        default=[],
                        help='Additional sensors to enable')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--empty_room', action='store_true',
                       default=False,
                       help='Remove furniture and partitions')
    group.add_argument('--arch_only', action='store_true',
                       default=False,
                       help='Remove furniture')
    parser.add_argument('--retexture',
                        nargs='?', const='True',
                        default=True,
                        type=str2bool,
                        help='Retexture scenes')
    parser.add_argument('--texture_set',
                        nargs='?', const='all',
                        default='all',
                        choices=['train', 'val', 'test', 'all'],
                        help='Texture set to use for retexturing')
    parser.add_argument('--mirrors',
                        nargs='?', const='True',
                        default=False,
                        type=str2bool,
                        help='Enable mirrors')
    parser.add_argument('--source', type=str,
                        default='p5dScene',
                        help='Default data source')
    parser.add_argument('--log_action_trace', action='store_true',
                        default=False,
                        help='Whether to log action and state traces')
    parser.add_argument('--save_png', action='store_true',
                        default=False,
                        help='Whether to write out png sequence')
    parser.add_argument('--debug', action='store_true',
                        default=False,
                        help='Debug visualization mode')
    parser.add_argument('--debug_audio_memory', action='store_true',
                        default=False,
                        help='Debug audio memory')
    parser.add_argument('--profile_cpu', action='store_true',
                        default=False,
                        help='Profile cpu usage (by simserver)')
    parser.add_argument('--debug_mem', action='store_true',
                        default=False,
                        help='Debug memory usage (by simserver)')
    parser.add_argument('--scene_ids', nargs='*',
                        default=['00a76592d5cc7d92eef022393784a2de', '066e8a32fd15541e814a9eafa82abf5d',
                                 '11be354e8dbd5d7275c486a5037ea949'],
                        help='Scene ids to load')
    parser.add_argument('--room', type=str,
                        default=None,
                        help='Room id to load')
    parser.add_argument('--agent_config', type=str,
                        default='',
                        help='Agent configuration to use (corresponds to agent config JSON file in config dir)')
    parser.add_argument('--env_config',
                        default='objectgoal_suncg_sf',
                        help='Environment configuration file to use (corresponds to py file in config/envs dir)')
    parser.add_argument('--task', type=str,
                        default='object_goal',
                        help='Type of task to perform')
    parser.add_argument('--scene_format',
                        default=None, type=str,
                        help='Scene format to use')
    parser.add_argument('--roomtypes_file', help='File to use for room types')
    parser.add_argument('--objecttypes_file', help='File to use for object types')
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

    script_path = os.path.dirname(os.path.realpath(__file__))
    replace_doors_file = os.path.join(script_path, './replace_doors.json')
    with open(replace_doors_file, 'r') as f:
        replace_doors = json.load(f)
    if args.depth_noise:
        args.sensors = [{'name': 'depth', 'noise': True}]
    args.observations = {'color': True, 'depth': args.depth, 'forces': args.forces, 'audio': args.audio}
    for s in args.sensors:
        args.observations[s] = True
    args.collision_detection = {'mode': args.collision_mode}
    args.scene = {'fullId': args.source + '.' + args.scene_ids[0],
                  'room': args.room,
                  'archOnly': args.arch_only, 'emptyRoom': args.empty_room,
                  'retexture': args.retexture,
                  'texturedObjects': 'all',
                  'textureSet': args.texture_set,
                  'enableMirrors': args.mirrors,
                  'hideCategories': ['person', 'plant'], 'replaceModels': replace_doors,
                  'createArch': True,
                  'format': args.scene_format}
    if args.source == 'p5dScene':
        args.scene['defaultModelFormat'] = 'obj'
        args.scene['defaultSceneFormat'] = 'suncg'

    args.goal = get_goal_for_task(args.task)
    args.audio = {'debug': args.debug, 'debug_memory': args.debug_audio_memory}
    args.actionTraceLogFields = ['forces']
    args.auto_start = not args.manual_start
    if not args.auto_start:
        args.audio = {'port': 1112}
        args.port = 4899

    sim_args = sim_config.get(args.env_config, vars(args))

    return sim_args
