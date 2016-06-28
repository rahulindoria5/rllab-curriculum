from __future__ import print_function
from __future__ import absolute_import

import numpy as np
from .base import Distribution
import tensorflow as tf

TINY = 1e-8


def from_onehot(x_var):
    ret = np.zeros((len(x_var),), 'int32')
    nonzero_n, nonzero_a = np.nonzero(x_var)
    ret[nonzero_n] = nonzero_a
    return ret


class Categorical(Distribution):
    def __init__(self, dim):
        self._dim = dim

    @property
    def dim(self):
        return self._dim

    def kl_sym(self, old_dist_info_vars, new_dist_info_vars):
        """
        Compute the symbolic KL divergence of two categorical distributions
        """
        old_prob_var = old_dist_info_vars["prob"]
        new_prob_var = new_dist_info_vars["prob"]
        ndims = old_prob_var.get_shape().ndims
        # Assume layout is N * A
        return tf.reduce_sum(
            old_prob_var * (tf.log(old_prob_var + TINY) - tf.log(new_prob_var + TINY)),
            reduction_indices=ndims - 1
        )

    def kl(self, old_dist_info, new_dist_info):
        """
        Compute the KL divergence of two categorical distributions
        """
        old_prob = old_dist_info["prob"]
        new_prob = new_dist_info["prob"]
        return np.sum(
            old_prob * (np.log(old_prob + TINY) - np.log(new_prob + TINY)),
            axis=-1
        )

    def likelihood_ratio_sym(self, x_var, old_dist_info_vars, new_dist_info_vars):
        old_prob_var = old_dist_info_vars["prob"]
        new_prob_var = new_dist_info_vars["prob"]
        ndims = old_prob_var.get_shape().ndims
        x_var = tf.cast(x_var, tf.float32)
        # Assume layout is N * A
        return (tf.reduce_sum(new_prob_var * x_var, ndims - 1) + TINY) / \
               (tf.reduce_sum(old_prob_var * x_var, ndims - 1) + TINY)

    def entropy(self, info):
        probs = info["prob"]
        return -np.sum(probs * np.log(probs + TINY), axis=1)

    def log_likelihood_sym(self, x_var, dist_info_vars):
        probs = dist_info_vars["prob"]
        ndims = probs.get_shape().ndims
        return tf.log(tf.reduce_sum(probs * tf.cast(x_var, tf.float32), ndims - 1) + TINY)

    def log_likelihood(self, xs, dist_info):
        probs = dist_info["prob"]
        # Assume layout is N * A
        N = probs.shape[0]
        return np.log(probs[np.arange(N), from_onehot(np.asarray(xs))] + TINY)

    @property
    def dist_info_specs(self):
        return [("prob", (self.dim,))]

    def sample_sym(self, dist_info):
        probs = dist_info["prob"]
        samples = tf.multinomial(tf.log(probs + 1e-8), num_samples=1)[:, 0]
        return tf.nn.embedding_lookup(np.eye(self.dim, dtype=np.float32), samples)