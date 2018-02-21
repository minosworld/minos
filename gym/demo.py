#!/usr/bin/env python3

import argparse
import gym
import gym_minos

from minos.config import sim_config
from minos.config.sim_args import add_sim_args_basic


def run_gym(sim_args):
    env = gym.make('indoor-v0')
    env.configure(sim_args)
    print('Running MINOS gym example')
    for i_episode in range(20):
        print('Starting episode %d' % i_episode)
        observation = env.reset()
        done = False
        num_steps = 0
        while not done:
            env.render()
            action = env.action_space.sample()
            observation, reward, done, info = env.step(action)
            num_steps += 1
            if done:
                print("Episode finished after {} steps; success={}".format(num_steps, observation['success']))
                break


def main():
    parser = argparse.ArgumentParser(description='MINOS gym wrapper')
    add_sim_args_basic(parser)
    parser.add_argument('--env_config',
                        default='objectgoal_suncg_sf',
                        help='Environment configuration file')
    args = parser.parse_args()
    sim_args = sim_config.get(args.env_config, vars(args))
    run_gym(sim_args)


if __name__ == "__main__":
    main()
