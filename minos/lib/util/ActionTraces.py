import csv


# TODO(MS) get rid of this default task-to-goal mapping by storing goal specs in action trace header
TASK_TO_DEFAULT_GOAL = {
    'point_goal': {'type': 'position', 'position': 'random', 'radius': 0.25},
    'object_goal': {'type': 'object', 'categories': ['arch', 'door'], 'select': 'random'},
    'room_goal': {'type': 'room', 'minRooms': 1, 'roomTypes': 'any', 'select': 'random'}
}

class ActionTrace:
    """ Action Trace for a episode"""
    def __init__(self, r):
        self.task = r['task']
        self.episode = r['episode']
        self.sceneId = r['sceneId']
        self.goals = []
        self.actions = []
        self.append(r)
        self.index = -1
        self.start = {'position': [r['px'], r['py'], r['pz']], 'angle': r['rotation']}
        self._start_state = None

    def start_state(self):
        if self._start_state is None:
            self._start_state = {
                'scene': {'fullId': self.sceneId},
                'task': self.task,
                'start': self.start,
                'goal': TASK_TO_DEFAULT_GOAL.get(self.task, None),
            }
        return self._start_state

    def curr_action_record(self):
        return self.actions[self.index] if 0 <= self.index < len(self.actions) else None

    def next_action_record(self):
        self.index += 1
        return self.curr_action_record()

    def append(self, r):
        if r['actions'] == 'goal':
            self.goals.append(r)
        else:
            self.actions.append(r)


class ActionTraces:
    """ Wrapper for a set of action traces """
    def __init__(self, log_file):
        self.traces = self._load_action_traces(log_file)
        self.index = -1

    def curr_trace(self):
        return self.traces[self.index] if 0 <= self.index < len(self.traces) else None

    def next_trace(self):
        self.index += 1
        return self.curr_trace()

    def _load_action_traces(self, csvfile):
        #    episode,sceneId,tick,px,py,pz,rotation,actions,actionArgs
        #    1,p5dScene.bf3c229ca4d17aa0854665c47632952b,0,-42.6000,1.0800,-39.0400,,goal,0_14
        #    -,-,1,-37.9170,0.5950,-38.6200,2.9940,idle
        traces = []
        int_fields = ['episode', 'tick']
        float_fields = ['px', 'py', 'pz', 'rotation']
        with open(csvfile) as f:
            reader = csv.DictReader(f)
            prev_record = None
            trace = None
            for r in reader:
                for f,v in r.items():
                    if v == '-':
                        r[f] = prev_record[f]
                    if r[f] == '':
                        r[f] = None
                for f in int_fields:
                    if r[f] is not None:
                       r[f] = int(r[f])
                for f in float_fields:
                    if r[f] is not None:
                        r[f] = float(r[f])
                if prev_record is None or r['episode'] != prev_record['episode']:
                    # New trace
                    trace = ActionTrace(r)
                    traces.append(trace)
                else:
                    # Append to old trace
                    trace.append(r)
                prev_record = r
        return traces
