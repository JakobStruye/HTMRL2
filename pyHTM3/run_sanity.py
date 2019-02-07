import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import pyHTM3.spatial_pooler as spatial_pooler
import yaml
import os
import datetime

from pyHTM3.env.bandit import Bandit
from pyHTM3.env.maze import Maze
from pyHTM3.env.sanity import Sanity
from pyHTM3.algo.qlearn import QLearn

from pyHTM3.encoders.maze_encoder import MazeEncoder
from pyHTM3.encoders.sanity_encoder import SanityEncoder



def run_htmrl(env, steps, htmrl_config):

    input_size = (htmrl_config["input_size"],)
    input_sparsity = htmrl_config["input_sparsity"]

    #fixed_input_indices = np.random.choice(input_size[0], round(input_size[0] * input_sparsity))
    #fixed_input = np.zeros(input_size)
    #fixed_input[fixed_input_indices] = 1

    boost_strength = float(htmrl_config["boost_strength"])
    only_reinforce_selected = bool(htmrl_config["only_reinforce_selected"])
    reward_scaled_reinf = bool(htmrl_config["reward_scaled_reinf"])
    normalized_rewards =  bool(htmrl_config["normalized_rewards"])
    boost_scaled_reinf = bool(htmrl_config["boost_scaled_reinf"])

    k = env.get_action_count()
    sp = spatial_pooler.SpatialPooler(input_size, k, boost_strength=boost_strength,
                                      only_reinforce_selected=only_reinforce_selected,
                                      reward_scaled_reinf=reward_scaled_reinf, normalize_rewards=normalized_rewards,
                                      boost_scaled_reinf=boost_scaled_reinf)
    rews = []
    actions = []
    best_count = 0
    total_reward = np.zeros(k)  # Set scoreboard for bandits to 0.
    total_selections = np.zeros(k)

    #encoder = MazeEncoder(env_config["size"])
    encoder = SanityEncoder(env_config["size"])

    state = env.get_state()

    for step in range(steps):
        #TEMP SANITY CHANGE
        #input_enc = encoder.encode(state[0], state[1])
        input_enc = encoder.encode(state[0])
        encoding = sp.step(input_enc)
        action = encoding_to_action(encoding, k, step)
        net_weight = action

        state, reward = env.do_action(action)  # Get our reward from picking one of the bandits.

        #best_count += 1 if env.is_best(action) else 0

        #env.visualize()

        sp.reinforce(action, reward)
        # Update our running tally of scores.
        total_reward[action] += reward
        total_selections[action] += 1
        rews.append(reward)
        actions.append(action)
        # if (step == 199 and best_count <100):
        #    print(action, b.arms, total_selections)
    print("BEST:", best_count)
    return (rews, actions, env.get_debug_info())


def run_greedy(env, steps, eps):
    k = env.get_action_count()
    rews = []
    actions = []
    sample_avgs = np.zeros((k,))
    sample_counts = np.zeros((k,))
    for step in range(steps):
        if np.random.uniform(0.,1.) <= eps:
            selection = np.random.randint(0,k)
        else:
            selection = np.argmax(sample_avgs)
        state, rew = env.do_action(selection)
        sample_avg = sample_avgs[selection]
        sample_count = sample_counts[selection]
        sample_avgs[selection] = (sample_count * sample_avg + rew) / (sample_count + 1)
        sample_counts[selection] += 1
        rews.append(rew)
        actions.append(selection)
    return (np.array(rews), actions, env.get_debug_info())

def run_q(env, steps):
    rews = []
    actions = []
    ql = QLearn((100,),4,0.0)
    state = env.get_state()
    for step in range(steps):
        action = ql.get_action(state)
        next_state, rew = env.do_action(action)
        ql.learn(state, next_state, action, rew)
        state = next_state

        rews.append(rew)
        actions.append(action)
        print(rew)
    return (np.array(rews), actions, env.get_debug_info())


def run_random(env, steps):
    k = env.get_action_count()
    rews = []
    actions = []
    for step in range(steps):
        action = np.random.randint(k)
        state, reward = env.do_action(action)
        rews.append(reward)
        actions.append(action)
    return (np.array(rews), actions, env.get_debug_info())


def repeat_algo(env_init, env_config, steps, repeats, algo, outfile, **kwargs):
    avg_rews = np.zeros((steps,))
    all_rews = []
    all_acts = []
    all_arms = []
    for i in range(repeats):
        env = env_init(env_config)
        (new_rews, new_actions, new_b) = algo(env, steps, **kwargs)
        outfile.write(str(new_rews))
        outfile.write(str(new_actions))
        outfile.write(str(new_b))
        #all_rews.append(new_rews)
        #all_acts.append(new_actions)
        #all_arms.append(new_b)
        new_rews = np.cumsum(new_rews)
        new_rews[100:] = new_rews[100:] - new_rews[:-100]
        new_rews /= 100.
        avg_rews = (i * avg_rews + new_rews) / (i+1)

    return avg_rews

#for eps in [0.1,0.01,0.0]:
#    results = repeat_greedy(10, eps, 1000, 2000)
#    print(results.shape)
#    plt.plot(range(1000), results)
#plt.show()


def encoding_to_action(encoding, actions, i=1):
    buckets = np.floor(encoding / (2050. / actions))
    buckets = buckets.astype(np.int32)
    counts = np.bincount(buckets)
    #print(counts)
    #if i%200 == 0:
    #    print(counts)
    return counts.argmax()



if __name__ == "__main__":
    with open("config/sanity.yml", 'r') as stream:
        try:
            yml = yaml.load(stream)
            config_main = yml["general"]
            env_main = yml["env"]
            if env_main["name"] == "Bandit":
                env_init = Bandit
            elif env_main["name"] == "Maze":
                env_init = Maze
            elif env_main["name"] == "Sanity":
                env_init = Sanity
            else:
                raise Exception("Unknown env type: " + env_main["name"])
            algorithms_main = yml["algorithms"]
            experiments = yml["experiments"]
            print(yml)
        except yaml.YAMLError as exc:
            print(exc)


    outdir = "output/" + datetime.datetime.now().strftime("%y-%m-%d_%H-%M-%S") + "/"

    try:
        os.makedirs(outdir)
    except:
        pass



    for exp_dict in experiments:
        exp_name = list(exp_dict.keys())[0]
        os.makedirs(outdir + exp_name)
        exp = exp_dict[exp_name]
        if exp is None:
            exp = {} #ease of use
        if "general" in exp:
            config = {**config_main, **exp["general"]}
        else:
            config = config_main
        if "env" in exp:
            env_config = {**env_main, **exp["env"]}
        else:
            env_config = env_main
        repeats = config["repeats"]
        steps = config["steps"]

        with open(outdir + exp_name + "/q", "w") as rawfile:

            results = repeat_algo(env_init, env_config, steps, repeats, run_q, rawfile)
        plt.plot(range(steps), results, alpha=0.5, label="Q-learn")

        #HTMRL
        if "algorithms" in exp and "htmrl" in exp['algorithms']:
            htmrl = {**algorithms_main["htmrl"], **exp["algorithms"]["htmrl"]}
        elif "htmrl" in algorithms_main:
            htmrl = algorithms_main["htmrl"]
        else:
            htmrl = None
        print(htmrl)
        if htmrl is not None:
            with open(outdir + exp_name + "/htmrl", "w") as rawfile:
                results = repeat_algo(env_init, env_config, steps, repeats, run_htmrl, rawfile, htmrl_config=htmrl)

            plt.plot(range(steps), results, alpha=0.5, label="HTM")

        #eps-greedy
        if "algorithms" in exp and "eps" in exp['algorithms']:
            eps = {**algorithms_main["eps"], **exp["algorithms"]["eps"]}
        elif "eps" in algorithms_main:
            eps = algorithms_main["eps"]
        else:
            eps = None
        if eps is not None:
            with open(outdir + exp_name + "/eps", "w") as rawfile:
                results = repeat_algo(env_init, env_config, steps, repeats, run_greedy, rawfile, eps=eps["e"])
            print(results.shape)
            plt.plot(range(steps), results, alpha=0.5, label="eps-greedy")


        #Random
        if "random" in algorithms_main:
            with open(outdir + exp_name + "/random", "w") as rawfile:
                results = repeat_algo(env_init, env_config, steps, repeats, run_random, rawfile)

            plt.plot(range(steps), results, alpha=0.5, label="random")

        with open(outdir + exp_name + "/config", "w") as writefile:
            writefile.write("\n".join([str(config), str(env_config), str(htmrl), str(eps)]))
        plt.legend()
        plt.savefig(outdir + exp_name + ".png")
        plt.gcf().clear()
