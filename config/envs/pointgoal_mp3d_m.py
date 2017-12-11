from lib.util.measures import MeasureDistDirTime

config = {
    'task': 'point_goal',
    'goal': {'position': 'random', 'radius': 0.25},
    'measure_fun': MeasureDistDirTime(goal_dist_threshold=0.4),
    'reward_type': 'dist_time',
    'agent': {'radialClearance': 0.2},
    'scene': {'dataset': 'mp3d'},
    'scenes_file': '../data/scenes.mp3d.csv',
    'states_file': '../data/episode_states.mp3d.csv.bz2',
    'num_episodes_per_scene': 100,
    'max_states_per_scene': 10,
    'scene_filter': lambda s: 2 < s['nrooms'] < 25 and s['nlevels'] == 1,
    'episode_filter': lambda e: e['pathNumRooms'] > 0,
    'objective_size': 4 # For UNREAL
}
