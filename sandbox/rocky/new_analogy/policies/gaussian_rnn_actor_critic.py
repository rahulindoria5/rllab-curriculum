import numpy as np
import sandbox.rocky.tf.core.layers as L
import tensorflow as tf
from sandbox.rocky.tf.core.layers_powered import LayersPowered
from sandbox.rocky.tf.distributions.recurrent_diagonal_gaussian import RecurrentDiagonalGaussian
from sandbox.rocky.tf.misc import tensor_utils
from sandbox.rocky.tf.policies.rnn_utils import create_recurrent_network, NetworkType
from sandbox.rocky.tf.spaces import Box
from sandbox.rocky.tf.spaces.discrete import Discrete
from sandbox.rocky.tf.policies.base import StochasticPolicy

from rllab.core.serializable import Serializable
from rllab.misc import special
from rllab.misc.overrides import overrides


class GaussianRNNActorCritic(StochasticPolicy, LayersPowered, Serializable):
    def __init__(
            self,
            name,
            env_spec,
            hidden_dim=32,
            feature_network=None,
            hidden_nonlinearity=tf.tanh,
            network_type=NetworkType.GRU,
            weight_normalization=False,
            layer_normalization=False,
            moments_update_rate=0.9,
    ):
        Serializable.quick_init(self, locals())
        """
        :param env_spec: A spec for the env.
        :param hidden_dim: dimension of hidden layer
        :param hidden_nonlinearity: nonlinearity used for each hidden layer
        :return:
        """
        with tf.variable_scope(name):
            assert isinstance(env_spec.action_space, Box)
            super(GaussianRNNActorCritic, self).__init__(env_spec)

            obs_dim = env_spec.observation_space.flat_dim
            action_dim = env_spec.action_space.flat_dim

            l_obs = L.InputLayer(
                shape=(None, None, obs_dim),
                name="obs"
            )

            if feature_network is None:
                feature_dim = obs_dim
                l_flat_feature = None
                l_feature = l_obs
            else:
                feature_dim = feature_network.output_layer.output_shape[-1]
                l_flat_feature = feature_network.output_layer
                l_feature = L.OpLayer(
                    l_flat_feature,
                    extras=[l_obs],
                    name="reshape_feature",
                    op=lambda flat_feature, input: tf.reshape(
                        flat_feature,
                        tf.pack([tf.shape(input)[0], tf.shape(input)[1], feature_dim])
                    ),
                    shape_op=lambda _, input_shape: (input_shape[0], input_shape[1], feature_dim)
                )

            head_network = create_recurrent_network(
                network_type,
                input_shape=(feature_dim,),
                input_layer=l_feature,
                output_dim=action_dim + 1,
                hidden_dim=hidden_dim,
                hidden_nonlinearity=hidden_nonlinearity,
                output_nonlinearity=None,
                weight_normalization=weight_normalization,
                layer_normalization=layer_normalization,
                name="head_network",
            )

            l_log_std = L.ParamLayer(
                incoming=l_obs,
                num_units=action_dim,
            )

            self.head_network = head_network
            self.feature_network = feature_network
            self.l_obs = l_obs
            self.l_log_std = l_log_std

            flat_input_var = tf.placeholder(dtype=tf.float32, shape=(None, obs_dim), name="flat_input")
            if feature_network is None:
                feature_var = flat_input_var
            else:
                feature_var = L.get_output(l_flat_feature, {feature_network.input_layer: flat_input_var})

            self.f_step = tensor_utils.compile_function(
                [
                    flat_input_var,
                    head_network.step_prev_state_layer.input_var
                ],
                L.get_output([
                    head_network.step_output_layer,
                    head_network.step_state_layer,
                ], {head_network.step_input_layer: feature_var}) + [l_log_std.param],
            )

            self.action_dim = action_dim
            self.hidden_dim = hidden_dim
            self.state_dim = head_network.state_dim

            self.prev_states = None
            self.dist = RecurrentDiagonalGaussian(dim=action_dim)
            self.moments_update_rate = moments_update_rate

            return_var = tf.placeholder(dtype=tf.float32, shape=(None, None), name="return")
            valid_var = tf.placeholder(dtype=tf.float32, shape=(None, None), name="valid")

            return_mean_var = tf.Variable(
                np.cast['float32'](0.),
                name="return_mean",
            )
            return_std_var = tf.Variable(
                np.cast['float32'](1.),
                name="return_std",
            )
            return_mean_stats = tf.reduce_sum(return_var * valid_var) / tf.reduce_sum(valid_var)
            return_std_stats = tf.sqrt(
                tf.reduce_sum(tf.square(return_var - return_mean_var) * valid_var) / tf.reduce_sum(valid_var)
            )

            self.return_mean_var = return_mean_var
            self.return_std_var = return_std_var

            self.f_update_stats = tensor_utils.compile_function(
                inputs=[return_var, valid_var],
                outputs=[
                    tf.assign(
                        return_mean_var,
                        (1 - self.moments_update_rate) * return_mean_var + \
                        self.moments_update_rate * return_mean_stats,
                    ),
                    tf.assign(
                        return_std_var,
                        (1 - self.moments_update_rate) * return_std_var + \
                        self.moments_update_rate * return_std_stats,
                    )
                ]
            )

            out_layers = [head_network.output_layer, l_log_std]
            if feature_network is not None:
                out_layers.append(feature_network.output_layer)

            LayersPowered.__init__(self, out_layers)

            obs_var = env_spec.observation_space.new_tensor_variable("obs", extra_dims=2)

            prev_state_var = tf.placeholder(dtype=tf.float32, shape=(None, self.head_network.state_dim),
                                            name="prev_state")
            state_info_vars = [
                tf.placeholder(dtype=tf.float32, shape=(None, None) + shape, name=k)
                for k, shape in self.state_info_specs
                ]

            self.f_dist_info = tensor_utils.compile_function(
                inputs=[obs_var] + state_info_vars,
                outputs=self.dist_info_sym(
                    obs_var, dict(zip(self.state_info_keys, state_info_vars))
                )
            )

            recurrent_layer = self.head_network.recurrent_layer

            hidden_var = self.hidden_sym(
                obs_var,
                state_info_vars=dict(zip(self.state_info_keys, state_info_vars)),
                recurrent_state={recurrent_layer: prev_state_var},
            )

            self.f_hiddens = tensor_utils.compile_function(
                inputs=[obs_var] + state_info_vars + [prev_state_var],
                outputs=hidden_var,
            )

    def get_params_internal(self, **tags):
        params = LayersPowered.get_params_internal(self, **tags)
        if not tags.get('trainable', False):
            params = params + [self.return_mean_var, self.return_std_var]
        return params

    def dist_info(self, observations, state_infos):
        return self.f_dist_info(observations, *(state_infos[k] for k in self.state_info_keys))

    def hidden_sym(self, obs_var, state_info_vars, **kwargs):
        obs_var = tf.cast(obs_var, tf.float32)
        if self.feature_network is None:
            hidden_out = L.get_output(
                self.head_network.recurrent_layer,
                {self.l_obs: obs_var},
                **kwargs
            )
        else:
            flat_input_var = tensor_utils.temporal_flatten_sym(obs_var)
            hidden_out = L.get_output(
                self.head_network.recurrent_layer,
                {self.l_obs: obs_var, self.feature_network.input_layer: flat_input_var},
                **kwargs
            )
        return hidden_out

    @overrides
    def dist_info_sym(self, obs_var, state_info_vars, **kwargs):
        obs_var = tf.cast(obs_var, tf.float32)
        if self.feature_network is None:
            head_out = L.get_output(
                self.head_network.output_layer,
                {self.l_obs: obs_var},
                **kwargs
            )
        else:
            flat_input_var = tensor_utils.temporal_flatten_sym(obs_var)
            head_out = L.get_output(
                self.head_network.output_layer,
                {self.l_obs: obs_var, self.feature_network.input_layer: flat_input_var},
                **kwargs
            )
        log_stds = L.get_output(self.l_log_std, {self.l_obs: obs_var})
        means = head_out[:, :, :self.action_dim]
        vf = head_out[:, :, self.action_dim:]
        vf = vf * self.return_std_var + self.return_mean_var
        return dict(
            mean=means, log_std=log_stds, vf=vf
        )

    @property
    def vectorized(self):
        return True

    def reset(self, dones=None):
        if dones is None:
            dones = [True]
        dones = np.cast['bool'](dones)
        if self.prev_states is None or len(dones) != len(self.prev_states):
            self.prev_states = np.zeros((len(dones), self.state_dim))

        if np.any(dones):
            self.prev_states[dones] = self.head_network.state_init_param.eval()

    def stateful_reset(self, dones, prev_states):
        assert np.sum(dones) == len(prev_states)
        dones = np.cast['bool'](dones)
        self.prev_states[dones] = prev_states

    @overrides
    def get_action(self, observation):
        actions, agent_infos = self.get_actions([observation])
        return actions[0], {k: v[0] for k, v in agent_infos.items()}

    @overrides
    def get_actions(self, observations):
        flat_obs = self.observation_space.flatten_n(observations)
        all_obs = flat_obs
        head_out, state_vec, log_std = self.f_step(all_obs, self.prev_states)
        action_means = head_out[:, :-1]
        vf = head_out[:, -1:]
        return_mean, return_std = tf.get_default_session().run([self.return_mean_var, self.return_std_var])
        vf = vf * return_std + return_mean
        log_stds = np.tile(np.expand_dims(log_std, axis=0), (len(observations), 1))
        actions = np.random.normal(size=action_means.shape) * np.exp(log_stds) + action_means
        agent_info = dict(mean=action_means, log_std=log_stds, vf=vf)
        self.prev_states = state_vec
        return actions, agent_info

    @property
    @overrides
    def recurrent(self):
        return True

    @property
    def distribution(self):
        return self.dist

    def fit_with_samples(self, paths, samples_data):
        # update the baseline jointly with the policy instead..
        # however, renormalize first
        self.f_update_stats(samples_data["returns"], samples_data["valids"])
