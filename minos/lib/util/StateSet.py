import bz2
import csv
import collections
import math

from enum import Enum


class Select(Enum):
    FIRST = 'first'
    RANGE_KEY = 'range_key'
    RANGE_VALUE = 'range_value'


class SelectPolicy:
    def __init__(self, policy, field=None):
        self.policy = policy
        self.field = field


class StateSet:
    """ Wrapper for set of episode val/test states """
    def __init__(self, scenes_file=None, states_files=None,
                 scene_filter=None, episode_filter=None, max_states_per_scene=None,
                 select_policy=SelectPolicy(Select.FIRST)):
        self.states = []
        self.scenes = []
        self.scenes_by_id = {}
        self.states_by_scene = {}
        self.select_policy = select_policy
        if scenes_file:
            self._load_scenes(scenes_file, scene_filter)
        if states_files:
            if type(states_files) is str:
                self._load_states(states_files, max_states_per_scene, episode_filter)
            elif isinstance(states_files, collections.Iterable):
                for states_file in states_files:
                    self._load_states(states_file, max_states_per_scene, episode_filter)
            self._embed_states_in_scenes()

    def get_splits(self, max_states_per_scene=None):
        """Get dictionary of StateSets keyed by scene 'set' i.e. dataset split"""
        scenes_by_split = {}
        for scene in self.scenes:
            scenes_by_split.setdefault(scene['set'], []).append(scene)
        state_sets_dict = {}
        for split, scenes in scenes_by_split.items():
            ss = StateSet()
            ss._populate_from_lists(scenes, self.states_by_scene, max_states_per_scene)
            state_sets_dict[split] = ss
        return state_sets_dict

    def get_scenes(self):
        return self.scenes

    def get_states(self):
        return self.states

    def get_states_by_scene_id(self, scene_id):
        return self.states_by_scene[scene_id]

    def _select_n_states(self, states, n):
        # Select n states from big list of states
        policy = self.select_policy.policy
        field = self.select_policy.field
        if n is not None and n < len(states):
            if policy == Select.FIRST:
                if field is not None:
                    # sort by field
                    states = sorted(states, key=lambda x: x[field])
                return states[:n]
            elif policy == Select.RANGE_KEY:
                # sort by field
                states = sorted(states, key=lambda x: x[field])
                # select by evenly dividing indices
                r = len(states)/float(n)
                selected = []
                for i in range(n):
                    si = int(math.floor(math.ceil(r*i)/2))
                    selected.append(states[si])
                return selected
            elif policy == Select.RANGE_VALUE:
                # sort by field and get range (value)
                states = sorted(states, key=lambda x: x[field])
                fmin = states[0][field]
                fmax = states[-1][field]
                # print('Range is %f to %f' % (fmin,fmax))
                # from range, divide up into n buckets
                r = (fmax-fmin)/float(n)
                buckets = []
                for i in range(n):
                    buckets.append([])
                for state in states:
                    bi = int(min(math.ceil((state[field] - fmin)/r), n-1))
                    buckets[bi].append(state)
                # make sure all buckets have something
                for i, bucket in enumerate(buckets):
                    if len(bucket) == 0:
                        # print('Nothing in bucket %d' % i)
                        # still some from other buckets
                        pi = max(i-1, 0)
                        ni = min(i+1, n-1)
                        nlen = len(buckets[ni])
                        plen = len(buckets[pi])
                        if nlen > plen:
                            # take half from bucket[ni] and put in current bucket
                            k = math.floor(nlen/2)
                            buckets[i] = buckets[ni][:k]
                            buckets[ni] = buckets[ni][k:]
                        else:
                            k = math.floor(plen/2)
                            buckets[i] = buckets[pi][:k]
                            buckets[pi] = buckets[pi][k:]
                selected = []
                for bucket in buckets:
                    bii = math.floor(len(bucket)/2)
                    selected.append(bucket[bii])
                return selected
            else:
                raise ValueError('Unsupported select_policy ' + policy)
        else:
            return states

    def _populate_from_lists(self, my_scenes, my_states_by_scene, max_states_per_scene):
        self.scenes = my_scenes
        for scene in my_scenes:
            scene_id = scene['id']
            self.scenes_by_id[scene_id] = scene
            if scene_id in my_states_by_scene:
                my_states = self._select_n_states(my_states_by_scene[scene_id], max_states_per_scene)
                self.states_by_scene[scene_id] = my_states
                self.states += my_states

    def _load_scenes(self, filename, scene_filter):
        with bz2.open(filename, 'rt') if filename.endswith('bz2') else open(filename) as f:
            reader = csv.DictReader(f)
            self.scenes = []
            for r in reader:
                for v in ['nrooms', 'nobjects', 'nlevels']:
                    if v in r:
                        r[v] = int(r[v])
                for v in ['dimX', 'dimY', 'dimZ', 'floorArea']:
                    if v in r:
                        r[v] = float(r[v])
                if scene_filter and not scene_filter(r):
                    continue
                self.scenes.append(r)
                self.scenes_by_id[r['id']] = r
            self.scenes.sort(key=lambda x: x['nobjects'])

    def _load_states(self, filename, max_states_per_scene, state_filter):
        with bz2.open(filename, 'rt') if filename.endswith('bz2') else open(filename) as f:
            reader = csv.DictReader(f)
            all_states = [r for r in reader]

            # Convert scene state and group by sceneId
            counter = 0
            for r in all_states:
                for v in ['startX', 'startY', 'startZ', 'startAngle', 'startTilt', 'goalX', 'goalY', 'goalZ', 'goalAngle', 'goalTilt', 'dist', 'pathDist']:
                    r[v] = float(r[v]) if v in r else None
                for v in ['episodeId', 'pathNumDoors', 'pathNumRooms', 'level']:
                    r[v] = int(r[v]) if v in r else None
                scene_id = r['sceneId']
                scene_states = self.states_by_scene.setdefault(scene_id, [])
                rec = {
                    'episode_id': counter,
                    'scene_id': r['sceneId'],
                    'room_id': r['roomId'],
                    'start': {'position': [r['startX'], r['startY'], r['startZ']],
                              'angle': r['startAngle'], 'tilt': r.get('startTilt', 0.0)},
                    'goal': {'id': r['goalObjectId'], 'objectType': r.get('goalObjectType', ''),
                             'roomId': r.get('goalRoomId', ''), 'roomType': r.get('goalRoomType', ''),
                             'position': [r['goalX'], r['goalY'], r['goalZ']],
                             'angle': r.get('goalAngle', 0.0), 'tilt': r.get('goalTilt', 0.0)},
                    'dist': r['dist']
                }
                for k in ['pathDist', 'pathNumRooms', 'pathRoomIds', 'pathNumDoors', 'pathDoorIds', 'level']:
                    if k in r:
                        rec[k] = r[k]

                if not state_filter or state_filter(rec):
                    scene_states.append(rec)
                    counter = counter + 1

            # Filter down to states per scene and create big list of all scenes
            states = []
            for scene_id, scene_states in self.states_by_scene.items():
                self.states_by_scene[scene_id] = self._select_n_states(scene_states, max_states_per_scene)
                states += self.states_by_scene[scene_id]
            self.states = states

    def _embed_states_in_scenes(self):
        for state in self.states:
            scene_id = state['scene_id']
            if scene_id in self.scenes_by_id:
                self.scenes_by_id[scene_id].setdefault('states', []).append(state)
        scenes_with_no_states = []
        for i, scene in enumerate(self.scenes):
            if 'states' not in scene or len(scene['states']) == 0:
                scenes_with_no_states.append(scene['id'])
                del self.scenes_by_id[scene['id']]
        self.scenes = [s for s in self.scenes if s['id'] not in scenes_with_no_states]
        #print('Removed scenes with no episode states: ' + ','.join(scenes_with_no_states))


def main():
    import argparse
    # Argument processing
    parser = argparse.ArgumentParser(description='Load state set')
    parser.add_argument('-n', '--limit',
                        type=int,
                        help='Number of states per scene')
    parser.add_argument('--select',
                        default=Select.FIRST,
                        type=Select,
                        help='Number of states per scene')
    parser.add_argument('--field',
                        default=None,
                        help='Field to use for selection')
    parser.add_argument('--scenes',
                        type=str,
                        default=None,
                        help='Scenes file to load')
    parser.add_argument('input',
                        help='Input file to load')
    args = parser.parse_args()

    state_set = StateSet(scenes_file=args.scenes,
                         states_files=args.input,
                         max_states_per_scene=args.limit,
                         select_policy=SelectPolicy(args.select, args.field))
    for state in state_set.states:
        print(state)


if __name__ == "__main__":
    main()
