require_relative '../utils'

params = {
  mdp: {
    _name: "box2d.cartpole_mdp",
    position_only: true,
  },
  normalize_mdp: true,
  policy: {
    _name: "mean_std_rnn_policy",
  },
  baseline: {
    _name: "linear_feature_baseline",
  },
  algo: {
    _name: "recurrent.rreps",
    batch_size: 1000,
    whole_paths: true,
    max_path_length: 500,
    n_itr: 500,
  },
  n_parallel: 1,
  snapshot_mode: "none",
  seed: 1,
}
command = to_command(params)
puts command
system(command)