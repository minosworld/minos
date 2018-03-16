import argparse
import numpy as np
import pygame
from pygame.locals import *
from timeit import default_timer as timer
import traceback

from minos.lib.RoomSimulator import RoomSimulator
from minos.lib import common
from minos.config import sim_config
from minos.config.sim_args import parse_sim_args


def interactive_loop(sim, args):
    # Action to key map
    action_key_map = {
        'forwards': K_i,
        'backwards': K_k,
        'turnLeft': K_j,
        'turnRight': K_l,
        'strafeLeft': K_LEFT,
        'strafeRight': K_RIGHT,
        'lookUp': K_UP,
        'lookDown': K_DOWN,
    }
    action_keys = [action_key_map[action] for action in sim.available_controls]

    # initialize
    pygame.mixer.pre_init(frequency=8000, channels=1)
    pygame.init()
    font = pygame.font.SysFont("monospace", 12)
    pygame.key.set_repeat(500, 50)  # delay, interval
    nimages = 1
    if 'modality' in args and 'depth' in args['modality']:
        nimages = 2
    display_surf = pygame.display.set_mode((args['width'] * nimages, args['height']), pygame.RESIZABLE | pygame.DOUBLEBUF)

    print('IJKL+Arrows = move agent, N = next state/scene, O = print observation, Q = quit')
    init_time = timer()
    num_frames = 0
    prev_key = ''
    # Initial idle step
    actions = [0 for k in action_keys]
    response = sim.step(actions)
    observation = response['observation']
    while sim.sim.running:
        pygame.event.wait()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sim.sim.running = False

        # read keys
        keys = pygame.key.get_pressed()
        print_next_observation = False
        if keys[K_q]:
            break

        if keys[K_o]:
            print_next_observation = True
        elif keys[K_n]:
            prev_key = 'n' if prev_key is not 'n' else ''
            if prev_key is 'n':
                sim.end_episode(success=False, print_episode_stats=True)

        # step simulator and get observation
        actions = [keys[k] for k in action_keys]
        if sum(actions) > 0:
            response = sim.step(actions)
            observation = response['observation']
        if observation is None:
            print('No observations.  Exiting...')
            break

        def printable(x): return type(x) is not bytearray and type(x) is not np.ndarray
        if print_next_observation:
            simple_observations = {k: v for k, v in observation.items() if k not in ['color', 'depth', 'audio']}
            dicts = [simple_observations]
            for d in dicts:
                for k, v in d.items():
                    if type(v) is not dict:
                        info = '%s: %s' % (k,v)
                        print(info[:75] + (info[75:] and '..'))
                    else:
                        print('%s: %s' % (k, str({i: v[i] for i in v if printable(v[i])})))

        # update image
        sensors = observation['sensors']
        if 'color' in sensors:
            img = sensors.get('color').get('data')
            if len(img.shape) == 2:  # assume gray
                img = np.dstack([img, img, img])
            else:  # assume rgba
                img = img[:, :, :-1]
            surface = pygame.surfarray.make_surface(np.transpose(img, (1, 0, 2)))
            display_surf.blit(surface, (0, 0))

        if 'depth' in sensors:
            img = sensors.get('depth').get('data')
            img *= (255.0 / img.max())  # naive rescaling for visualization
            if len(img.shape) == 2:  # assume gray
                img = np.dstack([img, img, img])
            else:  # assume rgba
                img = img[:, :, :-1]
            surface = pygame.surfarray.make_surface(np.transpose(img, (1, 0, 2)))
            display_surf.blit(surface, (args['width'], 0))

        if 'audio' in sensors:
            audio_data = sensors.get('audio').get('data')
            pygame.sndarray.make_sound(audio_data).play()
            # pygame.mixer.Sound(audio_data).play()

        if 'measurements' in observation:
            meas_str = str(observation['measurements'])
            label = font.render(meas_str, 1, (255, 0, 0))
            display_surf.blit(label, (5, 5))

        pygame.display.flip()
        num_frames += 1

    # cleanup and quit
    time_taken = timer() - init_time
    print('time=%f sec, fps=%f' % (time_taken, num_frames / time_taken))
    print('Thank you for playing - Goodbye!')
    pygame.quit()


def main():
    parser = argparse.ArgumentParser(description='MINOS gym wrapper')
    args = parse_sim_args(parser)
    sim = RoomSimulator(args)
    common.attach_exit_handler(sim.sim)
    try:
        print('Starting RoomSimulator...')
        sim.init()
        print('RoomSimulator started.')
        interactive_loop(sim, args)
    except:
        traceback.print_exc()
        print('Error running simulator. Aborting.')

    if sim is not None:
        sim.close_game()
        del sim


if __name__ == "__main__":
    main()
