from rllab.mdp.box2d.box2d_mdp import Box2DMDP
from rllab.mdp.box2d.parser import find_body, find_joint
import numpy as np
from rllab.core.serializable import Serializable
from rllab.misc import autoargs
from rllab.misc.overrides import overrides


# http://mlg.eng.cam.ac.uk/pilco/
class DoublePendulumMDP(Box2DMDP, Serializable):

    @autoargs.inherit(Box2DMDP.__init__)
    def __init__(self, **kwargs):
        # make sure mdp-level step is 100ms long
        kwargs["frame_skip"] = kwargs.get("frame_skip", 2)
        super(DoublePendulumMDP, self).__init__(
            self.model_path("double_pendulum.xml"),
            **kwargs
        )
        self.link_len = 1.
        self.link1 = find_body(self.world, "link1")
        self.link2 = find_body(self.world, "link2")
        Serializable.__init__(self)

    @overrides
    def reset(self):
        self._set_state(self.initial_state)
        stds = np.array([0.1, 0.1, 0.01, 0.01])
        pos1, pos2, v1, v2 = np.random.randn(*stds.shape) * stds
        self.link1.angle = pos1
        self.link2.angle = pos2
        self.link1.angularVelocity = v1
        self.link2.angularVelocity = v2
        return self.get_state(), self.get_current_obs()

    def get_tip_pos(self):
        cur_center_pos = self.link2.position
        cur_angle = self.link2.angle
        cur_pos = (
            cur_center_pos[0] - self.link_len*np.sin(cur_angle),
            cur_center_pos[1] - self.link_len*np.cos(cur_angle)
        )
        return cur_pos

    def get_current_reward(
            self, state, raw_obs, action, next_state, next_raw_obs):
        tgt_pos = np.asarray([0, self.link_len * 2])
        cur_pos = self.get_tip_pos()
        dist = np.linalg.norm(cur_pos - tgt_pos)
        return -dist

    def is_current_done(self):
        return False