import scipy.ndimage

import numpy as np


class Measure:
    num_meas = 0

    def __init__(self, goal_dist_threshold=1.0e-6,  # success when dist < this value
                 termination_dist_value=-10.0,  # overrides distance value returned at term
                 termination_time=50.0,
                 termination_on_success=True):
        self.goal_dist_threshold = goal_dist_threshold
        self.termination_dist_value = termination_dist_value
        self.termination_time = termination_time
        self.termination_on_success = termination_on_success

    def reset(self):
        pass

    def measure(self, observation, episode_info=None):
        meas = self.my_measure(observation, episode_info)
        success, term = self._get_success_and_term(observation, episode_info)
        return meas, success, term

    def my_measure(self, observation, episode_info=None):
        return []

    def get_objectives(self, observation, episode_info=None):
        # Extract objectives from observation and episode_info
        return None

    def _get_success_and_term(self, observation, episode_info):
        task = episode_info.get('task', 'point_goal')
        measurements = observation.get('measurements')
        distances = measurements.get('distance_to_goal')
        time = observation.get('time')

        if task == 'room_goal':
            room_info = observation['roomInfo']
            success = episode_info['goal']['room'] == room_info['id']
        else:
            success = distances[0] <= self.goal_dist_threshold

        term = time > self.termination_time
        if self.termination_on_success:
            term = term or success
        return success, term


def rescale_and_quantize(x, shape, num_bins, max_val):
    zoom_factor = list(np.array(shape) / np.array(x.shape))
    x = scipy.ndimage.zoom(x, zoom_factor, order=0)
    bins = np.linspace(0, max_val, num_bins)
    x_quant = np.digitize(x, bins)
    return x_quant


class RunningMeans:
    def __init__(self, dim, steps):
        max_step = steps[-1]
        self.step_indices = np.array(steps) - 1
        self.norms = 1.0 / np.array(steps)
        self.xs = np.zeros((dim, max_step))

    def reset(self):
        self.xs = np.zeros(self.xs.shape)

    def add(self, x):
        self.xs = np.roll(self.xs, 1, axis=1)
        self.xs[:, 0] = x

    def values(self):
        return self.xs

    def means(self):
        cumsums = np.cumsum(self.xs, axis=1)
        cumsums[:, self.step_indices] *= self.norms
        return cumsums[:, self.step_indices]


class MeasureDist(Measure):
    num_meas = 1

    def my_measure(self, observation, episode_info=None):
        d = observation.get('measurements').get('distance_to_goal')
        dist = d[0]
        dterm = self.termination_dist_value
        if dterm is not None and dist < self.goal_dist_threshold:
            dist = dterm
        return [dist]


class MeasureTime(MeasureDist):
    num_meas = 1

    def my_measure(self, observation, episode_info=None):
        time_spent = observation.get('time') / self.termination_time
        return [time_spent]


class MeasureDistTime(MeasureDist):
    num_meas = MeasureDist.num_meas + 1

    def my_measure(self, observation, episode_info=None):
        time_spent = observation.get('time') / self.termination_time
        return super().my_measure(observation) + [time_spent]


class MeasureDistOffset(MeasureDist):
    num_meas = MeasureDist.num_meas + 2

    def my_measure(self, observation, episode_info=None):
        offsets = observation.get('measurements').get('offset_to_goal')
        return super().my_measure(observation) + [offsets[0], offsets[2]]


class MeasureDistOffsetHealth(MeasureDist):
    num_meas = MeasureDist.num_meas + 3

    def my_measure(self, observation, episode_info=None):
        offsets = observation.get('measurements').get('offset_to_goal')
        time = observation.get('time')
        health = 100 - (2 * time)
        return super().my_measure(observation) + [offsets[0], offsets[2], health]


class MeasureDistDir(MeasureDist):
    num_meas = MeasureDist.num_meas + 2

    def my_measure(self, observation, episode_info=None):
        dirs = observation.get('measurements').get('direction_to_goal')
        return super().my_measure(observation) + [dirs[0], dirs[2]]


class MeasureNavMapDistDirTime(Measure):
    num_meas = 4

    def my_measure(self, observation, episode_info=None):
        time_spent = observation.get('time') / self.termination_time
        p = observation.get('measurements').get('shortest_path_to_goal')
        if p and 'distance' in p:
            d = p.get('direction', [0.0, 0.0, 0.0])
            return np.array([p['distance'], d[0], d[2], time_spent])
        else:
            return np.array([1000.0, 0.0, 0.0, time_spent])


class MeasureAudioDistDirAmp(Measure):
    num_meas = 8  # TODO parameterize for more than default two receivers

    def my_measure(self, observation, episode_info=None):
        paths = observation.get('sensors').get('audio').get('endpointShortestPaths')
        dterm = self.termination_dist_value
        d = observation.get('measurements').get('distance_to_goal')[0]
        if dterm is not None and d < self.goal_dist_threshold:
            paths[0] = dterm  # sensor 1 dist
            paths[3] = dterm  # sensor 2 dist
        return paths


class MeasureAudioDistDirAmpTime(MeasureAudioDistDirAmp):
    num_meas = MeasureAudioDistDirAmp.num_meas + 1

    def my_measure(self, observation, episode_info=None):
        time_spent = observation.get('time') / self.termination_time
        return np.concatenate((super().my_measure(observation), [time_spent]))


class MeasureDistDirTime(MeasureDist):
    num_meas = MeasureDist.num_meas + 3

    def my_measure(self, observation, episode_info=None):
        dirs = observation.get('measurements').get('direction_to_goal')
        time_spent = observation.get('time') / self.termination_time
        return super().my_measure(observation) + [dirs[0], dirs[2], time_spent]


class MeasureDistDirTimeNavMapDist(MeasureDist):
    num_meas = MeasureDist.num_meas + 4

    def my_measure(self, observation, episode_info=None):
        dirs = observation.get('measurements').get('direction_to_goal')
        time_spent = observation.get('time') / self.termination_time
        p = observation.get('measurements').get('shortest_path_to_goal')
        d = p['distance'] if p and 'distance' in p else 1000.0
        return super().my_measure(observation) + [dirs[0], dirs[2], time_spent, d]


class MeasureDistDirTimeForces(MeasureDistDirTime):
    num_meas = MeasureDistDirTime.num_meas + 4  # TODO Parameterize forces length

    def my_measure(self, observation, episode_info=None):
        forces = observation.get('sensors').get('forces').get('data')
        return np.concatenate((super().my_measure(observation), forces))


class MeasureDistDirTimeContacts(MeasureDistDirTime):
    num_meas = MeasureDistDirTime.num_meas + 4

    def __init__(self, termination_dist_value=-10.0,  # overrides distance value returned at term
                 goal_dist_threshold=1.0e-6,
                 termination_time=50.0):
        super().__init__(goal_dist_threshold, termination_dist_value, termination_time)
        self.total_contacts = np.array([0., 0., 0., 0.])

    def reset(self):
        self.total_contacts = np.array([0., 0., 0., 0.])

    def my_measure(self, observation, episode_info=None):
        forces = observation.get('sensors').get('forces').get('data')
        self.total_contacts += forces
        return np.concatenate((super().my_measure(observation), self.total_contacts))


class MeasureDistDirTimeForceMeans(MeasureDistDirTime):
    def __init__(self, steps_to_take_mean,
                 termination_dist_value=-10.0,  # overrides distance value returned at term
                 goal_dist_threshold=1.0e-6,
                 termination_time=50.0):
        super().__init__(goal_dist_threshold, termination_dist_value, termination_time)
        num_means = len(steps_to_take_mean)
        self.num_meas = MeasureDistDirTime.num_meas + (4*num_means)  # TODO Parameterize forces length
        self.running_means = RunningMeans(4, steps_to_take_mean)

    def reset(self):
        self.running_means.reset()

    def my_measure(self, observation, episode_info=None):
        forces = observation.get('sensors').get('forces').get('data')
        self.running_means.add(forces)
        force_means = self.running_means.means().flatten()
        return np.concatenate((super().my_measure(observation), force_means))


class MeasureDistDirTimeDepthPred(MeasureDist):
    def __init__(self, depth_shape, depth_range,
                 termination_dist_value=-10.0,  # overrides distance value returned at term
                 goal_dist_threshold=1.0e-6,
                 termination_time=50.0):
        super().__init__(goal_dist_threshold, termination_dist_value, termination_time)
        num_depth_pixels = depth_shape[0] * depth_shape[1]
        self.num_meas = MeasureDistDirTime.num_meas + num_depth_pixels
        self.max_depth = depth_range[1]
        self.depth_shape = depth_shape

    def my_measure(self, observation, episode_info=None):
        dirs = observation.get('measurements').get('direction_to_goal')
        depth = observation.get('sensors').get('depth').get('data')
        depth_meas = rescale_and_quantize(depth, self.depth_shape[0:1], self.depth_shape[2], self.max_depth)
        time_spent = observation.get('time') / self.termination_time
        return np.concatenate((super().my_measure(observation), [dirs[0], dirs[2], time_spent], depth_meas.flatten()))

class MeasureGoalRoomType(Measure):
    def my_measure(self, observation, episode_info=None):
        goalRoomType = episode_info['goal']['roomTypeEncoded']
        return goalRoomType

class MeasureMatchRoomType(Measure):
    num_meas = 1

    def my_measure(self, observation, episode_info=None):
        roomInfo = observation.get('roomInfo')
        roomType = roomInfo['roomTypeEncoded']
        goalRoomType = episode_info['goal']['roomTypeEncoded']
        return np.asarray([roomType.dot(goalRoomType)])
