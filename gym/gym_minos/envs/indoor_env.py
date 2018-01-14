"""
OpenAI gym environment wrapper
"""

import gym
from gym import spaces
from gym.utils import seeding
import numpy as np

# This is currently an experimental wrapper that wraps around the room simulator
# It may make sense to wrap the Simulator and have several prespecified configurations
#  (or have a base IndoorEnv and specific scenarios on top of it)
from lib.RoomSimulator import RoomSimulator


class IndoorEnv(gym.Env):
    metadata = {'render.modes': ['human', 'rgb_array']}

    def __init__(self):
        self._last_state = None
        self._sim = None
        self.viewer = None

    def configure(self, sim_args):
        self._sim = RoomSimulator(sim_args)
        self._sim_obs_space = self._sim.get_observation_space(sim_args['outputs'])
        #self.action_space = spaces.Discrete(self._sim.num_buttons)
        self.action_space = spaces.MultiBinary(self._sim.num_buttons)
        self.screen_height = self._sim_obs_space['color'].shape[1]
        self.screen_width = self._sim_obs_space['color'].shape[0]
        self.observation_space = spaces.Box(low=0, high=255, 
            shape=(self.screen_height, self.screen_width, 3))
        # TODO: have more complex observation space with additional modalities and measurements
        # obs_space = self._sim.get_observation_space
        #self.observation_space = spaces.Dict({"images": ..., "depth": ...})

    def _seed(self, seed=None):
        """Sets the seed for this env's random number generator(s).
        Note:
            Some environments use multiple pseudorandom number generators.
            We want to capture all such seeds used in order to ensure that
            there aren't accidental correlations between multiple generators.
        Returns:
            list<bigint>: Returns the list of seeds used in this env's random
              number generators. The first value in the list should be the
              "main" seed, or the value which a reproducer should pass to
              'seed'. Often, the main seed equals the provided 'seed', but
              this won't be true if seed=None, for example.
        """
        # TODO: generate another seed for use in simulator? 
        # What happens to this seed?
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def _reset(self):
        """Resets the state of the environment and returns an initial observation.
        Returns: observation (object): the initial observation of the
            space.
        """
        res = self._sim.reset()
        return res.get('observation')

    def _step(self, action):
        """Run one timestep of the environment's dynamics. When end of
        episode is reached, you are responsible for calling `reset()`
        to reset this environment's state.
        Accepts an action and returns a tuple (observation, reward, done, info).
        Args:
            action (object): an action provided by the environment
        Returns:
            observation (object): agent's observation of the current environment
            reward (float) : amount of reward returned after previous action
            done (boolean): whether the episode has ended, in which case further step() calls will return undefined results
            info (dict): contains auxiliary diagnostic information (helpful for debugging, and sometimes learning)
        """
        ## a = [0]*self._sim.num_buttons
        ## a[action] = 1
        state = self._sim.step(action)
        self._last_state = state  # Last observed state
        observation = {k:v for k,v in state.items() if k not in ['rewards','terminals']}
        info = state['info']
        return observation, state['rewards'], state['terminals'], info

    def _render(self, mode='human', close=False):
        """Renders the environment.
        The set of supported modes varies per environment. (And some
        environments do not support rendering at all.) By convention,
        if mode is:
        - human: render to the current display or terminal and
          return nothing. Usually for human consumption.
        - rgb_array: Return an numpy.ndarray with shape (x, y, 3),
          representing RGB values for an x-by-y pixel image, suitable
          for turning into a video.
        - ansi: Return a string (str) or StringIO.StringIO containing a
          terminal-style text representation. The text can include newlines
          and ANSI escape sequences (e.g. for colors).
        Note:
            Make sure that your class's metadata 'render.modes' key includes
              the list of supported modes. It's recommended to call super()
              in implementations to use the functionality of this method.
        Args:
            mode (str): the mode to render with
            close (bool): close all open renderings
        """
        if close:
            if self.viewer is not None:
                self.viewer.close()
                self.viewer = None      # If we don't None out this reference pyglet becomes unhappy
            return
        if self._last_state is not None:
            img = self._last_state['observation']['sensors']['color']['data']
            if len(img.shape) == 2:  # assume gray
                img = np.dstack([img, img, img])
            else:  # assume rgba
                img = img[:, :, :-1]
            if mode == 'human':
                from gym.envs.classic_control import rendering
                if self.viewer is None:
                    if self.viewer is None:
                        self.viewer = rendering.SimpleImageViewer()
                self.viewer.imshow(img)
            elif mode == 'rgb_array':
                return img

    def _close(self):
        if self._sim is not None:
            self._sim.close_game()
