#!/usr/bin/env python3

import argparse
import gym
import gym_minos

from minos.config import sim_config
from minos.config.sim_args import parse_sim_args


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
    args = parse_sim_args(parser)
    run_gym(args)


if __name__ == "__main__":
    main()
