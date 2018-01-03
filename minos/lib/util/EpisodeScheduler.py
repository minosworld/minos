import math
import random


class EpisodeScheduler:
    def __init__(self, state_set, schedule, seed, num_episodes_per_scene):
        if schedule != 'random' and schedule != 'fixed':
            raise Exception('Invalid schedule type: ' + schedule)
        self.random = random.Random(seed)
        self.state_set = state_set
        self.schedule = schedule
        self.num_episodes_per_scene = num_episodes_per_scene
        self.num_episodes_this_scene = 0
        self.state_index = -1
        self.scene_index = -1
        self.scene_id = None

    def seed(self, s):
        self.random.seed(s)

    def next_episode(self):
        if self.schedule == 'random':
            return self._next_random_state()
        elif self.schedule == 'fixed':
            return self._next_state()

    def num_states(self):
        if self.schedule == 'random':
            return math.inf
        elif self.schedule == 'fixed':
            return len(self.state_set.get_scenes()) * self.num_episodes_per_scene

    def reset(self):
        self.state_index = -1
        self.num_episodes_this_scene = 0
        self.scene_id = None

    def get_all_scene_ids(self):
        return [s['id'] for s in self.state_set.get_scenes()]

    def _next_random_state(self):
        scenes = self.state_set.get_scenes()
        if self.num_episodes_this_scene % self.num_episodes_per_scene == 0:
            # print('picking random from', scenes)
            self.scene_id = self.random.choice(scenes)['id']
        self.num_episodes_this_scene += 1
        return {'scene_id': self.scene_id}

    def _next_state(self):
        scenes = self.state_set.get_scenes()
        if self.num_episodes_this_scene % self.num_episodes_per_scene == 0:
            self.scene_index = (self.scene_index + 1) % len(scenes)
            self.scene_id = scenes[self.scene_index]['id']
            # print('next_scene', self.scene_id)

        states = self.state_set.get_states_by_scene_id(self.scene_id)
        self.state_index = (self.state_index + 1) % min(len(states), self.num_episodes_per_scene)
        # print('next_state', self.state_index)

        self.num_episodes_this_scene += 1
        return states[self.state_index]
