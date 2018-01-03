import argparse
from collections import namedtuple
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import math
import random
from timeit import default_timer as timer
import traceback

from minos.lib import common
from minos.lib.Simulator import Simulator
from minos.config.sim_args import parse_sim_args

actions = ['forwards', 'backwards', 'turnLeft', 'turnRight', 'strafeLeft', 'strafeRight', 'lookUp', 'lookDown', 'idle'];

Timing = namedtuple('Timing', 'name secs')

random.seed(12345678)

def process_simulators(sims, act, repeat=1, async=False):
    if async:
        with ThreadPoolExecutor(max_workers=len(sims)) as executor:
            for i in range(0,repeat):
                futures = []
                for sim in sims:
                    future = executor.submit(lambda s: act(s), sim)
                    futures.append(future)
                concurrent.futures.wait(futures)
    else:
        for i in range(0,repeat):
            for sim in sims:
                act(sim)

def run_simulators(sims, steps, async=False):
    def step(sim):
        action = {'name': random.choice(actions), 'strength': 1, 'angle': math.radians(15)}
        sim.step(action, 1)
    process_simulators(sims, act=step, repeat=steps, async=async)

def report_times(scene_id, episode, nsteps, timings):
    line = '%s,%s,%d' % (scene_id, episode, nsteps)
    for timing in timings:
        line += ',%d,%f' % (timing.secs, nsteps/timing.secs)
    print(line)

def benchmark(args):
    scene_source = args.source
    scene_ids = args.scene_ids
    nsims = args.sims
    nsteps = args.steps_per_episode
    nepisodes = args.episodes_per_scene
    nscenes = args.num_scenes or len(scene_ids)
    async = args.async

    print('Benchmarking %d simulators (%s) with %d scenes, %d episodes each scene, %d steps each episode'
          % (nsims, 'async' if async else 'sync', nscenes, nepisodes, nsteps))

    total_secs_from_start = 0
    total_secs_from_init = 0
    total_steps = 0
    episode = 0

    sims = []
    for i in range(0, nsims):
        sims.append(Simulator(vars(args)))
    common.attach_exit_handler(sims)
    process_simulators(sims, act=lambda s: s.init(), async=async)

    init_time = timer()
    print('scene,episode,nsteps,secs_no_setup,fps_no_setup,secs_with_setup,fps_with_setup')
    try:
        def start_sim(sim, reset_only):
            sim.seed(random.randint(0, 12345678))
            if reset_only:
                sim.reset()
            else:
                sim.start()
        for i in range(0, nscenes):
            scene_id = scene_ids[i % len(scene_ids)]
            process_simulators(sims, act=lambda s: s.set_scene(scene_source + '.' + scene_id), async=async)
            for j in range(0, nepisodes):
                print('=== Starting/resetting simulators for scene ...' + scene_id)
                reset_only = j > 0
                process_simulators(sims, act=lambda s: start_sim(s, reset_only=reset_only), async=async)
                print('=== Simulator started.')
                start_time = timer()
                run_simulators(sims, nsteps, async=async)

                curr_time = timer()
                secs_from_start = curr_time - start_time
                total_secs_from_start += secs_from_start
                secs_from_init = (curr_time - init_time) - total_secs_from_init
                total_secs_from_init = curr_time - init_time

                total_steps += nsteps
                episode += 1
                report_times(scene_id, episode, nsteps,
                             [Timing('no_setup', secs_from_start),
                              Timing('with_setup', secs_from_init)])
    except:
        traceback.print_exc()
        print('Error running simulator. Aborting.')

    if total_steps != nsteps:
        report_times('ALL', 'ALL', total_steps,
                     [Timing('no_setup', total_secs_from_start),
                      Timing('with_setup', total_secs_from_init)])
    for sim in sims:
        sim.kill()
        del sim


def main():
    parser = argparse.ArgumentParser(description='Benchmarking the Simulator')
    parser.add_argument('--steps_per_episode',
                        default=500,
                        type=int,
                        help='Number of steps to take per episode')
    parser.add_argument('--episodes_per_scene',
                        default=1,
                        type=int,
                        help='Number of episodes per scene')
    parser.add_argument('--num_scenes',
                        default=1,
                        type=int,
                        help='Number of scenes (0 for all scenes)')
    parser.add_argument('--sims',
                        default=1,
                        type=int,
                        help='Number of simulators to run')
    parser.add_argument('--async',
                        action='store_true',
                        default=False,
                        help='Test simulators asynchronously')
    args = parse_sim_args(parser)
    benchmark(args)

if __name__ == "__main__":
    main()
