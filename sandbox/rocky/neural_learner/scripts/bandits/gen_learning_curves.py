import csv

from rllab import config
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rc('font', family='Times New Roman')
mpl.rcParams.update({'font.size': 14})

from rllab.viskit.core import load_exps_data, color_defaults

exp_prefix = "mab-17"

exp_folder = os.path.join(config.PROJECT_PATH, "data/s3/%s" % exp_prefix)

exps = load_exps_data([exp_folder], ignore_missing_keys=True)

exp_by_settings = dict()

for exp in exps:

    K = exp.params['n_arms']
    T = exp.params['n_episodes']

    key = (K, T)

    if key not in exp_by_settings:
        exp_by_settings[key] = []

    exp_by_settings[key].append(exp)

path = os.path.join(config.PROJECT_PATH, "data/iclr2016_new/best_gittins_mab.csv")

gittins = dict()

with open(path, "r") as f:
    reader = csv.DictReader(f)
    for line in reader:
        n_arms = int(line['n_arms'])
        n_episodes = int(line['n_episodes'])

        key = (n_arms, n_episodes)
        gittins[(n_arms, n_episodes)] = float(line['avg'])

counter = 0

for T in [10, 100, 500]:

    f, ax = plt.subplots(figsize=(8, 5))

    for color, K in zip(color_defaults, [5, 10, 50]):
        # if T == 10:
        #     itr_cutoff = 250
        # else:
        #     itr_cutoff = 500

        cur_exps = exp_by_settings[(K, T)]

        max_len = max([len(exp.progress['AverageReturn']) for exp in cur_exps])

        all_returns = np.asarray([
                                     np.concatenate([exp.progress['AverageReturn'],
                                                     np.ones(max_len - len(exp.progress['AverageReturn'])) *
                                                     np.nan]) for exp in cur_exps])

        # normalize: use the initial score as 0, and gittins as 1
        lower = np.nanmean(all_returns[:, 0])
        upper = gittins[(K, T)]

        all_returns = (all_returns - lower) / (upper - lower)

        means = np.nanmean(all_returns, axis=0)
        stds = np.nanstd(all_returns, axis=0)

        x = list(range(len(means)))
        y = list(means)
        y_upper = list(means + stds)
        y_lower = list(means - stds)

        ax.fill_between(
            x, y_lower, y_upper, interpolate=True, facecolor=color, linewidth=0.0, alpha=0.3)

        ax.plot(x, y, color=color, linewidth=1.0, label="k = %d" % K)

    ax.plot(x, np.ones_like(x), color='#666666', linewidth=1.0, linestyle="--", label="Gittins")

    # ax.grid(True)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    ax.set_ylim([-0.04, 1.2])

    if T == 10:
        plt.xticks([0, 300])
    else:
        plt.xticks([0, 600])
    plt.yticks([0, 1])

    leg = ax.legend(loc='lower right', ncol=1, prop={'size': 12})
    for legobj in leg.legendHandles:
        legobj.set_linewidth(1.0)

    plt.xlabel("Iteration")
    plt.ylabel("Normalized total reward")
    # plt.title("%d episodes" % T)

    # plt.show()
    plt.savefig(os.path.join(config.PROJECT_PATH, "data/images/bandit_%d_episodes.pdf" % T), bbox_inches='tight')
    # counter += 1
