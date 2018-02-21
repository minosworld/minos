from minos.lib.util.measures import MeasureDistDirTime

config = {
    'task': 'object_goal',
    'goal': {'categories': ['arch', 'door'], 'select': 'random', 'dist_from_bbox': True},
    'measure_fun': MeasureDistDirTime(),
    'reward_type': 'dist_time',
    'agent': {'radialClearance': 0.2},
    'scenes_file': '../data/scenes.multiroom.csv',
    'states_file': '../data/episode_states.suncg.csv.bz2',
    'scene': {'arch_only': False, 'retexture': True, 'empty_room': True, 'dataset': 'p5dScene'},
    'scene_filter': lambda s: 2 < s['nrooms'] < 6,
    'episode_filter': lambda e: e['pathNumDoors'] > 1,
    'objective_size': 4 # For UNREAL
}
