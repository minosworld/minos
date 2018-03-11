from minos.lib.util.measures import MeasureGoalRoomType

config = {
    'task': 'room_goal',
    'goal': {'minRooms': 1, 'roomTypes': 'any', 'select': 'random'},
    'measure_fun': MeasureGoalRoomType(),
    'reward_type': 'dist_time',
    'agent': {'radialClearance': 0.2},
    'scenes_file': '../data/scenes.mp3d.csv',
    'states_file': '../data/episode_states.mp3d.csv.bz2',
    'num_episodes_per_scene': 100,
    'max_states_per_scene': 10,
    'scene': {'dataset': 'mp3d'},
    'scene_filter': lambda s: 2 < s['nrooms'] < 11,
    'episode_filter': lambda e: e['pathNumRooms'] > 0,
    'objective_size': 9 # For UNREAL
}
