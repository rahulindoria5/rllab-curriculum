import numpy as np

from rllab.core.serializable import Serializable
from rllab.envs.base import Step
from rllab.envs.mujoco.mujoco_env import MujocoEnv
from rllab.misc import autoargs
from rllab.misc import logger
from rllab.misc.overrides import overrides


# states: [
# 0: z-coord,
# 1: x-coord (forward distance),
# 2: forward pitch along y-axis,
# 6: z-vel (up = +),
# 7: xvel (forward = +)


class HopperEnv(MujocoEnv, Serializable):

    FILE = 'hopper.xml'

    @autoargs.arg('alive_coeff', type=float,
                  help='reward coefficient for being alive')
    @autoargs.arg('ctrl_cost_coeff', type=float,
                  help='cost coefficient for controls')
    def __init__(
            self,
            alive_coeff=0.5,
            ctrl_cost_coeff=0.01,
            *args, **kwargs):
        self.alive_coeff = alive_coeff
        self.ctrl_cost_coeff = ctrl_cost_coeff
        super(HopperEnv, self).__init__(*args, **kwargs)
        Serializable.quick_init(self, locals())

    @overrides
    def get_current_obs(self):
        return np.concatenate([
            self.model.data.qpos[0:1].flat,
            self.model.data.qpos[2:].flat,
            np.clip(self.model.data.qvel, -10, 10).flat,
            np.clip(self.model.data.qfrc_constraint, -10, 10).flat,
            #self.get_body_com("torso").flat,
        ])

    @overrides
    def step(self, action):
        self.forward_dynamics(action)
        next_obs = self.get_current_obs()
        lb, ub = self.action_bounds
        scaling = (ub - lb) * 0.5
        vel = self.get_body_comvel("torso")[0]
        reward = vel + self.alive_coeff - \
            0.5 * self.ctrl_cost_coeff * np.sum(np.square(action / scaling))
        state = self._state
        notdone = np.isfinite(state).all() and \
            (np.abs(state[3:]) < 100).all() and (state[0] > .7) and \
            (abs(state[2]) < .2)
        done = not notdone

        com = np.concatenate([self.get_body_com("torso").flat]).reshape(-1)
        return Step(next_obs, reward, done, com=com)

    @overrides
    def log_diagnostics(self, paths):
        progs = [
            path["observations"][-1][-3] - path["observations"][0][-3]
            for path in paths
        ]
        logger.record_tabular('AverageForwardProgress', np.mean(progs))
        logger.record_tabular('MaxForwardProgress', np.max(progs))
        logger.record_tabular('MinForwardProgress', np.min(progs))
        logger.record_tabular('StdForwardProgress', np.std(progs))

    def log_stats_just_for_reference_dont_use_as_is(self, epoch, paths):
        # forward distance
        progs = [
            path["observations"][-1][-3] - path["observations"][0][-3]
            # -3 refers to the x coordinate of the com of the torso
            for path in paths
            ]
        n_directions = [
            np.max(progs) > self.prog_threshold,
            np.min(progs) < - self.prog_threshold,
            ].count(True)
        stats = {
            'env: ForwardProgressAverage': np.mean(progs),
            'env: ForwardProgressMax': np.max(progs),
            'env: ForwardProgressMin': np.min(progs),
            'env: ForwardProgressStd': np.std(progs),
            'env: ForwardProgressDiff': np.max(progs) - np.min(progs),
            'env: n_directions': n_directions,
        }
        if self.visitation_plot_config is not None:
            self.plot_visitation(
                epoch,
                paths,
                mesh_density=self.visitation_plot_config["mesh_density"],
                prefix=self.visitation_plot_config["prefix"],
                variant=self.visitation_plot_config["variant"],
                save_to_file=True,
            )
        return stats
