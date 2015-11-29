import lasagne.layers as L
import lasagne.nonlinearities as NL
import lasagne
import tensorfuse.tensor as TT

from rllab.qfun.base import ContinuousQFunction
from rllab.core.lasagne_powered import LasagnePowered
from rllab.core.serializable import Serializable


class ContinuousNNQFunction(ContinuousQFunction, LasagnePowered, Serializable):

    @autoargs.arg('hidden_sizes', type=int, nargs='*',
                  help='list of sizes for the fully-connected hidden layers')
    @autoargs.arg('hidden_nl', type=str, nargs='*',
                  help='list of nonlinearities for the hidden layers')
    @autoargs.arg('hidden_W_init', type=str, nargs='*',
                  help='list of initializers for W for the hidden layers')
    @autoargs.arg('hidden_h_init', type=str, nargs='*',
                  help='list of initializers for h for the hidden layers')
    @autoargs.arg('output_nl', type=str,
                  help='nonlinearity for the output layer')
    @autoargs.arg('output_W_init', type=str,
                  help='initializer for W for the output layer')
    @autoargs.arg('output_h_init', type=str,
                  help='initializer for h for the output layer')
    # pylint: disable=dangerous-default-value
    def __init__(
            self,
            mdp,
            hidden_sizes=[100, 100],
            hidden_nl=['lasagne.nonlinearities.rectify'],
            hidden_W_init=['lasagne.init.HeUniform()'],
            hidden_h_init=['lasagne.init.Constant(0.)'],
            output_nl='None',
            output_W_init='lasagne.init.Uniform(-3e-3, 3e-3)',
            output_b_init='lasagne.init.Uniform(-3e-3, 3e-3)',
            ):
        # pylint: enable=dangerous-default-value
        # create network
        # if isinstance(nonlinearity, str):
        #     nonlinearity = locate('lasagne.nonlinearities.' + nonlinearity)
        obs_var = TT.tensor(
            'obs',
            ndim=1+len(mdp.observation_shape),
            dtype=mdp.observation_dtype
        )
        action_var = TT.matrix(
            'action',
            dtype=mdp.action_dtype
        )
        l_obs = L.InputLayer(shape=(None,) + mdp.observation_shape,
                             input_var=obs_var)
        l_action = L.InputLayer(shape=(None, mdp.action_dim),
                                input_var=action_var)
        l_hidden1 = L.DenseLayer(
            l_obs,
            num_units=100,
            W=lasagne.init.HeUniform(),
            b=lasagne.init.Constant(0.),
            nonlinearity=NL.rectify,
            name="h1"
        )

        l_with_action = L.ConcatLayer([l_hidden1, l_action])

        l_hidden2 = L.DenseLayer(
            l_with_action,
            num_units=100,
            W=lasagne.init.HeUniform(),
            b=lasagne.init.Constant(0.),
            nonlinearity=NL.rectify,
            name="h2"
        )


        l_output = L.DenseLayer(
            l_hidden2,
            num_units=1,
            W=lasagne.init.Uniform(-3e-3, 3e-3),
            b=lasagne.init.Uniform(-3e-3, 3e-3),
            nonlinearity=None,
            name="output"
        )

        self._output_layer = l_output
        self._obs_layer = l_obs
        self._action_layer = l_action

        super(ContinuousNNQFunction, self).__init__(mdp)
        LasagnePowered.__init__(self, [l_output])
        Serializable.__init__(self, mdp)

    def get_qval_sym(self, obs_var, action_var):
        qvals = L.get_output(
            self._output_layer,
            {self._obs_layer: obs_var, self._action_layer: action_var}
        )
        return TT.reshape(qvals, (-1,))