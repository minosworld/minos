import argparse
import curses
import math
import numpy as np
import traceback

from config.sim_args import parse_sim_args
from lib import common
from lib.Simulator import Simulator


def _interactive_loop(stdscr, sim, scene_ids, scene_index):
    common.attach_exit_handler(sim)
    stdscr.timeout(1000)  # Set timeout to 1  second before running loop again

    curses.cbreak()
    stdscr.keypad(1)
    stdscr.addstr(0, 10, "Interactive mode (WASD + UP/DOWN). Hit 'q' to quit")
    stdscr.refresh()
    stdscr.move(1, 15)
    action_strength = 1  # Acceleration multiplier for actions
    look_angle = math.radians(15)  # Look up/down increment in radians

    print('IJKL+Arrows = move agent, N = next_scene, Q = quit, other keys = idle')
    while sim.running:
        key = stdscr.getch()
        if key < 0:
            continue   # check if we should exit
        elif key == ord('q'):
            break
        action = {'name': 'idle', 'strength': action_strength, 'angle': look_angle}
        stdscr.clrtobot()
        stdscr.refresh()
        if key == ord('i'):
            stdscr.addstr(1, 20, 'forward     ')
            action['name'] = 'forwards'
        elif key == ord('k'):
            stdscr.addstr(1, 20, 'backward    ')
            action['name'] = 'backwards'
        elif key == ord('j'):
            stdscr.addstr(1, 20, 'turn_left   ')
            action['name'] = 'turnLeft'
        elif key == ord('l'):
            stdscr.addstr(1, 20, 'turn_right  ')
            action['name'] = 'turnRight'
        elif key == ord('n'):
            scene_index = (scene_index + 1) % len(scene_ids)
            stdscr.addstr(1, 20, 'next_scene loading %s ...' % scene_ids[scene_index])
            sim.set_scene(scene_ids[scene_index])
            stdscr.refresh()
            sim.start()
            stdscr.addstr(1, 20, 'next_scene %s' % scene_ids[scene_index])
            stdscr.clrtoeol()
            stdscr.refresh()
        elif key == ord('r'):
            sim.restart(randomize_ports=True)
        elif key == curses.KEY_LEFT:
            stdscr.addstr(1, 20, 'strafe_left   ')
            action['name'] = 'strafeLeft'
        elif key == curses.KEY_RIGHT:
            stdscr.addstr(1, 20, 'strafe_right  ')
            action['name'] = 'strafeRight'
        elif key == curses.KEY_UP:
            stdscr.addstr(1, 20, 'look_up     ')
            action['name'] = 'lookUp'
        elif key == curses.KEY_DOWN:
            stdscr.addstr(1, 20, 'look_down   ')
            action['name'] = 'lookDown'
        else:
            stdscr.addstr(1, 20, 'idling      ')
            action['name'] = 'idle'
        stdscr.clrtobot()
        stdscr.move(1, 15)
        stdscr.refresh()
        response = sim.step(action, 1)
        observation = response.get('observation') if response is not None else None
        if observation is not None:
            nrow = 3
            simple_observations = {k:v for k,v in observation.items() if k not in ['measurements', 'sensors']}
            dicts = [simple_observations, observation.get('measurements'), observation.get('sensors')]
            for d in dicts:
                for k, v in d.items():
                    if type(v) is not dict:
                        info = '%s: %s' % (k,v)
                        stdscr.addstr(nrow, 20, info[:75] + (info[75:] and '..'))
                        nrow += 1
                    else:
                        stdscr.addstr(nrow, 20, '%s: %s' % (k, str({i: v[i] for i in v if type(v[i]) is not bytearray and type(v[i]) is not np.ndarray})))
                        nrow += 1
        stdscr.move(1, 15)


def interactive_loop(sim, scene_ids, scene_index):
    def run_loop(stdscr):
        _interactive_loop(stdscr, sim, scene_ids, scene_index)
    curses.wrapper(run_loop)
    print('Thank you for playing - Goodbye!')


def main():
    parser = argparse.ArgumentParser(description='Simulator console client')
    args = parse_sim_args(parser)
    sim = Simulator(vars(args))
    try:
        print('Starting simulator...')
        if sim.start():
            print('Simulator started.')
            interactive_loop(sim, args.scene_ids, 0)
    except:
        traceback.print_exc()
        print('Error running simulator. Aborting.')

    if sim is not None:
        sim.kill()
        del sim


if __name__ == "__main__":
    main()
