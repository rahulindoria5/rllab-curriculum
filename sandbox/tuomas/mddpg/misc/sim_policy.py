"""
This script helps to conveniently plot the environment and Q values for
multi-headed policies.
"""

from rllab.sampler.utils import rollout
from rllab.misc import tensor_utils
from rllab.envs.proxy_env import ProxyEnv
import argparse
import joblib
import uuid
import os
import random
import numpy as np
import tensorflow as tf
import time
import matplotlib.pyplot as plt

def rollout_alg(alg):
    rollout(alg.sess, alg.env, alg.policy, None, alg.qf, animated=True)

def rollout(sess, env, policy, exploration_strategy, qf, random=False,
            pause=False, max_path_length=1, animated=False, speedup=10,
            optimal=False, plot_qf=True):
    observations = []
    actions = []
    rewards = []
    agent_infos = []
    env_infos = []
    o = env.reset()
    if exploration_strategy is not None:
        exploration_strategy.reset()
    path_length = 0

    fig = plt.figure()
    #plt.axis('equal')
    ax_env = fig.add_subplot(211)
    ax_qf = fig.add_subplot(212)
    true_env = env
    while isinstance(true_env,ProxyEnv):
        true_env = true_env._wrapped_env
    true_env.fig = fig
    true_env.ax = ax_env
    if animated:
        env.render()

    def get_Q(o):
        xx = np.arange(-1, 1, 0.05)
        X, Y = np.meshgrid(xx, xx)
        all_actions = np.vstack([X.ravel(), Y.ravel()]).transpose()
        obs = np.array([o] * all_actions.shape[0])
        feed = {
            qf.observations_placeholder: obs,
            qf.actions_placeholder: all_actions
        }
        Q = sess.run(qf.output, feed).reshape(X.shape)
        return X, Y, Q

    while path_length < max_path_length:
        if optimal:
            X, Y, Q = get_Q(o)
            X = X.ravel()
            Y = Y.ravel()
            Q = Q.ravel()
            index = np.argmax(Q)
            a = np.array((X[index], Y[index]))
        else:
            if random:
                a = exploration_strategy.get_action(0, o, policy)
            else:
                a, agent_info = policy.get_action(o)
        print('action: ', a)

        agent_info = {}
        next_o, r, d, env_info = env.step(a)
        # print('com x: ', env_info["com"][0])

        observations.append(env.observation_space.flatten(o))
        rewards.append(r)
        actions.append(env.action_space.flatten(a))
        agent_infos.append(agent_info)
        env_infos.append(env_info)
        path_length += 1
        if d:
            break
        if animated:
            env.render()
            if plot_qf:
                # render the Q values
                X, Y, Q = get_Q(o)
                ax_qf.clear()
                contours = ax_qf.contour(X, Y, Q, 20)
                ax_qf.clabel(contours, inline=1, fontsize=10, fmt='%.0f')

                # current action
                a = a.ravel()
                ax_qf.plot(a[0], a[1], 'r*')
                plt.xlim((-1.1, 1.1))
                plt.ylim((-1.1, 1.1))


                # all actions
                all_actions = []
                for i in range(50):
                    action, _ = policy.get_action(o)
                    all_actions.append(action.squeeze())

                for k, action in enumerate(all_actions):
                    x = action[0]
                    y = action[1]
                    ax_qf.plot(x, y, '*')
                    #ax_qf.text(x, y, '%d'%(k))


                plt.draw()
                timestep = 0.05
                plt.pause(timestep / speedup)
            if pause:
                input()
        o = next_o
    input("Press Enter to continue...") # pause between heads
    if animated:
        env.render(close=False) # close=True causes the mujoco sim to fail
    plt.close(fig)

    return dict(
        observations=tensor_utils.stack_tensor_list(observations),
        actions=tensor_utils.stack_tensor_list(actions),
        rewards=tensor_utils.stack_tensor_list(rewards),
        agent_infos=tensor_utils.stack_tensor_dict_list(agent_infos),
        env_infos=tensor_utils.stack_tensor_dict_list(env_infos),
    )

filename = str(uuid.uuid4())

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str,
                        help='path to the snapshot file')
    parser.add_argument('--max_path_length', type=int, default=1000,
                        help='Max length of rollout')
    parser.add_argument('--speedup', type=float, default=1,
                        help='Speedup')
    parser.add_argument('--random', default=False,
        action='store_true')
    parser.add_argument('--pause', default=False,
        action='store_true')
    parser.add_argument('--optimal', default=False,
        action='store_true')
    parser.add_argument('--head', default=-1, type=int)
    parser.add_argument('--noqf', default=False, action='store_true')
    args = parser.parse_args()

    policy = None
    env = None

    while True:
        with tf.Session() as sess:
            data = joblib.load(args.file)
            if "algo" in data:
                algo = data["algo"]
                policy = algo.policy
                env = algo.env
                es = algo.exploration_strategy
                qf = algo.qf
            else:
                policy = data['policy']
                env = data['env']
                es = data['es']
                qf = data['qf']
            while True:
                try:
                    path = rollout(
                        sess,
                        env,
                        policy,
                        es,
                        qf,
                        pause=args.pause,
                        optimal=args.optimal,
                        max_path_length=args.max_path_length,
                        animated=True,
                        speedup=args.speedup,
                        random=args.random,
                        head=args.head,
                        plot_qf=not args.noqf,
                    )

                # Hack for now. Not sure why rollout assumes that close is an
                # keyword argument
                except TypeError as e:
                    if (str(e) != "render() got an unexpected keyword "
                                  "argument 'close'"):
                        raise e