import argparse
from easydict import EasyDict as edict
import random
import math

from minos.config.sim_args import parse_sim_args
from minos.lib import common
from minos.lib.Simulator import Simulator

random.seed(12345678)


def process_scene(sim, source, scene_id, f, level, num_levels, n_episodes, scene_counter=0):
    if scene_counter == 0:
        header = ['sceneId', 'level', 'roomId', 'roomType',
                  'startX', 'startY', 'startZ', 'startAngle',
                  'goalObjectId', 'goalX', 'goalY', 'goalZ',
                  'dist', 'pathDist', 'pathNumDoors', 'pathDoorIds',
                  'pathNumRooms', 'pathRoomIndices']
        f.write(','.join(header) + '\n')

    sim.set_scene(source + '.' + scene_id)
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
                write_configuration(f, edict(sim.get_scene_data()['data']), i_level)


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
        process_scene(sim, args.source, scene_ids[i], f, args.level, args.num_levels,
                      args.samples_per_scene, i)


def write_configuration(f, c, level):
    scene_id = c.sceneId.split('.')[1]
    s = c.start
    sp = s.position
    g = c.goal
    print(g)
    gp = g.position
    gid = g.objectId if 'objectId' in g else ''
    groomtype = g.roomType if 'roomType' in g else ''
    path = c.shortestPath
    valid_path = path and path.isValid
    path_dist = path.distance if valid_path else -1
    path_doors = path.doors if valid_path else []
    path_rooms = path.rooms if valid_path else []
    dist = math.sqrt((sp[0] - gp[0])**2 + (sp[1] - gp[1])**2 + (sp[2] - gp[2])**2)
    f.write('%s,%d,%s,%s,%.3f,%.3f,%.3f,%.3f,%s,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%s,%d,%s\n'
            % (scene_id, level, g.room, groomtype, sp[0], sp[1], sp[2], s.angle,
               gid, gp[0], gp[1], gp[2],
               dist, path_dist, len(path_doors), ':'.join(path_doors),
               len(path_rooms), ':'.join(str(r) for r in path_rooms)))


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
                        help='Scenes file')
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
                        help='Output states file')
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
