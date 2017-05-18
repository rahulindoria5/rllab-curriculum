import random

import numpy as np

from rllab.core.serializable import Serializable
from rllab.envs.base import Step
from rllab.envs.mujoco.mujoco_env import MujocoEnv
from rllab.misc import autoargs
from rllab.misc import logger
from rllab.spaces.box import Box
from rllab.misc.overrides import overrides





class BlockInsertionEnv1(MujocoEnv, Serializable):

    FILE = 'block_insertion_1.xml'
    goal_lb = np.array([-0.36, -0.7, -0.25])
    goal_ub = np.array([0.36, 0, 0.25])

    def __init__(self, *args, **kwargs):
        MujocoEnv.__init__(self, *args, **kwargs)
        Serializable.quick_init(self, locals())

    @overrides
    def get_current_obs(self):
        return np.concatenate([
            self.model.data.qpos.flat,
            self.model.data.qvel.flat,
        ])

    @overrides
    def reset(self, **kwargs):
        # if 'goal' in kwargs:
        #     goal = np.array(kwargs['goal']).flatten()
        # else:
        #     goal = np.array([0, 0])
        self.set_state(self.init_qpos, self.init_qvel)
        self.current_com = self.model.data.com_subtree[0]
        self.dcom = np.zeros_like(self.current_com)
        
        return self.get_current_obs()

    def step(self, action):
        self.forward_dynamics(action)
        reward = 0

        ob = self.get_current_obs()
        done = False
        return Step(
            ob, reward, done,
        )

    def set_state(self, qpos, qvel):
        assert qpos.shape == (self.model.nq, 1) and qvel.shape == (self.model.nv, 1)
        self.model.data.qpos = qpos
        self.model.data.qvel = qvel
        # self.model._compute_subtree() #pylint: disable=W0212
        self.model.forward()
        
    def is_feasible(self, goal):
        return np.all(np.logical_and(self.goal_lb <= goal, goal <= self.goal_ub))
