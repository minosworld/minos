#!/usr/bin/env python3

import argparse
import gym
import gym_minos
import matplotlib.pyplot as plt

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
            if sim_args.save_observations:
                save_observations(observation, sim_args)
            num_steps += 1
            if done:
                print("Episode finished after {} steps; success={}".format(num_steps, observation['success']))
                break


def save_observations(observation, sim_args):
    if sim_args.observations.get('color'):
        color = observation["observation"]["sensors"]["color"]["data"]
        plt.imsave('color.png', color)

    if sim_args.observations.get('depth'):
        depth = observation["observation"]["sensors"]["depth"]["data"]
        plt.imsave('depth.png', depth, cmap='Greys')

    if sim_args.observations.get('normal'):
        normal = observation["observation"]["sensors"]["normal"]["data"]
        plt.imsave('normal.png', normal)

    if sim_args.observations.get('objectId'):
        object_id = observation["observation"]["sensors"]["objectId"]["data"]
        plt.imsave('object_id.png', object_id)

    if sim_args.observations.get('objectType'):
        object_type = observation["observation"]["sensors"]["objectType"]["data"]
        plt.imsave('object_type.png', object_type)

    if sim_args.observations.get('roomId'):
        room_id = observation["observation"]["sensors"]["roomId"]["data"]
        plt.imsave('room_id.png', room_id)

    if sim_args.observations.get('roomType'):
        room_type = observation["observation"]["sensors"]["roomType"]["data"]
        plt.imsave('room_type.png', room_type)

    if sim_args.observations.get('map'):
        nav_map = observation["observation"]["map"]["data"]
        nav_map.shape = (nav_map.shape[1], nav_map.shape[0], nav_map.shape[2])
        plt.imsave('nav_map.png', nav_map)

    shortest_path = observation["observation"]["measurements"]["shortest_path_to_goal"]
    print(shortest_path)


def main():
    parser = argparse.ArgumentParser(description='MINOS gym wrapper')
    parser.add_argument('--save_observations', action='store_true',
                        default=False,
                        help='Save sensor observations at each step to images')
    args = parse_sim_args(parser)
    run_gym(args)


if __name__ == "__main__":
    main()
