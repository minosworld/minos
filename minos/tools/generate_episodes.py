import argparse
from easydict import EasyDict as edict
import random
import math

from minos.config.sim_args import parse_sim_args
from minos.lib import common
from minos.lib.Simulator import Simulator

random.seed(12345678)

EPISODE_ID = 0


def process_scene(sim, dataset, scene_id, f, level, num_levels, n_episodes, scene_counter=0):
    if scene_counter == 0:
        header = ['episodeId', 'task', 'sceneId', 'level',
                  'startX', 'startY', 'startZ', 'startAngle', 'startTilt',
                  'goalRoomId', 'goalRoomType', 'goalObjectId', 'goalObjectType',
                  'goalX', 'goalY', 'goalZ', 'goalAngle', 'goalTilt',
                  'dist', 'pathDist', 'pathNumDoors', 'pathDoorIds',
                  'pathNumRooms', 'pathRoomIndices']
        f.write(','.join(header) + '\n')

    sim.set_scene(dataset + '.' + scene_id)
    if level >= 0:  # do one level
        sim.configure({'scene': {'level': level}})
        for j in range(0, n_episodes):
            if j > 0:
                sim.reset()
            else:
                sim.start()
            write_configuration(f, edict(sim.get_scene_data()['data']), level)
    else:  # do all levels
        for i_level in range(0, num_levels):
            sim.configure({'scene': {'level': i_level}})
            for j in range(0, n_episodes):
                if j > 0:
                    sim.reset()
                else:
                    sim.start()
                scene_data = edict(sim.get_scene_data()['data'])
                write_configuration(f, scene_data, i_level)


def run(args):
    if args.scenes:
        scenes = edict(common.load_scenes_file(args.scenes))
        scene_ids = [r.id for r in scenes[args.split] if args.min_rooms < r.nrooms < args.max_rooms]
    else:
        scene_ids = args.scene_ids

    sim = Simulator(vars(args))
    common.attach_exit_handler(sim)
    sim.init()
    sim.seed(random.randint(0, 12345678))

    f = open(args.output, 'w')
    n_scenes = len(scene_ids)
    for i in range(0, n_scenes):
        process_scene(sim, args.scene.dataset, scene_ids[i], f, args.level, args.num_levels,
                      args.samples_per_scene, i)


def write_configuration(f, c, level):
    global EPISODE_ID
    scene_id = c.sceneId.split('.')[1]
    task = c.task
    s = c.start
    sp = s.position
    sangle = s.angle
    stilt = s.get('tilt', 0.0)
    g = c.goal
    print(g)
    gp = g.position
    gangle = g.get('angle', 0.0)
    gtilt = g.get('tilt', 0.0)
    gid = g.get('objectId', '')
    gid = gid[0] if isinstance(gid, list) else gid
    groomid = g.get('room', '')
    groomid = groomid[0] if isinstance(groomid, list) else groomid
    groomtype = g.get('roomType', '')
    groomtype = groomtype[0] if isinstance(groomtype, list) else groomtype
    gobjecttype = g.get('objectType', '')
    gobjecttype = gobjecttype[0] if isinstance(gobjecttype, list) else gobjecttype
    path = c.shortestPath
    valid_path = path and path.isValid
    path_dist = path.distance if valid_path else -1
    path_doors = path.doors if valid_path else []
    path_rooms = path.rooms if valid_path else []
    dist = math.sqrt((sp[0] - gp[0])**2 + (sp[1] - gp[1])**2 + (sp[2] - gp[2])**2)
    p = '.3f'  # precision for floats
    f.write(f'{EPISODE_ID},{task[0]},{scene_id},{level:d},'
        f'{sp[0]:{p}},{sp[1]:{p}},{sp[2]:{p}},{sangle:{p}},{stilt:.0f},'  # NOTE lower precision on stilt since always 0
        f'{groomid},{groomtype},{gid},{gobjecttype},'
        f'{gp[0]:{p}},{gp[1]:{p}},{gp[2]:{p}},{gangle:.0f},{gtilt:.0f},'  # NOTE lower precision on gangle and gtilt since always 0
        f'{dist:{p}},{path_dist:{p}},{len(path_doors):d},{":".join(path_doors)},'
        f'{len(path_rooms):d},{":".join(str(r) for r in path_rooms)}\n')
    EPISODE_ID += 1


def main():
    parser = argparse.ArgumentParser(description='Sample Agent States')
    parser.add_argument('--samples_per_scene',
                        default=100,
                        type=int,
                        help='Number of episodes per scene')
    parser.add_argument('--min_rooms',
                        default=1,
                        type=int,
                        help='Only sample from scenes with more than this many rooms')
    parser.add_argument('--max_rooms',
                        default=10000,  # Huge default
                        type=int,
                        help='Only sample from scenes with less than this many rooms')
    parser.add_argument('--min_dist',
                        default=1.0,
                        type=float,
                        help='Minimum distance between start and goal')
    parser.add_argument('--max_dist',
                        default=10000.0,  # Huge default
                        type=float,
                        help='Maximum distance between start and goal')
    parser.add_argument('--scenes',
                        required=True,
                        help='Input scenes csv file')
    parser.add_argument('--level',
                        default=-1,
                        type=int,
                        help='Level of scene to sample')
    parser.add_argument('--num_levels',
                        default=1,
                        type=int,
                        help='Number of levels to sample from')
    parser.add_argument('--split',
                        default='test',
                        help='Scene split to sample')
    parser.add_argument('--output',
                        required=True,
                        help='Output states file to write sampled episode states')
    args = parse_sim_args(parser)

    # args for simulator consumption
    args.navmap = {'refineGrid': True}  # Always use navmap to precompute episode states
    # args.sampleValidStartGoal = {'maxStartSamples': 10, 'maxGoalSamples': 10}
    args.goal['minDist'] = args.min_dist
    args.goal['maxDist'] = args.max_dist
    args.goal['minRooms'] = args.min_rooms
    args.goal['maxRooms'] = args.max_rooms

    run(args)


if __name__ == "__main__":
    main()
