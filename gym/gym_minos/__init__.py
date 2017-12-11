import logging
from gym.envs.registration import register

logger = logging.getLogger(__name__)

register(
    id='indoor-v0',
    entry_point='gym_minos.envs:IndoorEnv',
)
