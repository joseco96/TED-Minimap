"""
See Pranav's textual write up on these:
https://docs.google.com/spreadsheets/d/1z-wzZlZervLoxdEVF3HBkrpzuAthBYvOayN7cnfiLXY/edit#gid=0
"""

import sys
import json
import math
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

NUM_SIG_FIGS = 3

# ------------------------------------------------------------
# Here are the main functions used by the AC.

def initialize_state(config):
    """
    Set the tracking values to their initial states. Should be called at the
    start of a trial.
    """
    config.state = {
        # Map from alias to player name.
        'aliases': {},

        # Set to True when a mission is running. We only accumulate data and
        # produce values when this is True.
        'is_running': False,
        # The last time we reported results to the bus.
        'last_report_time': -1,

        # Here we accumulate all of the msg_data we produce. When the mission
        # stops, we write these to a csv file.
        'msg_data': [],

        # Here are a few values that we published and keep around to support
        # aggregate computations.
        'triaging': [],
        'team_scores': [],
        # 'word_counts': [],

        # For the process_..._agg values.
        'players_deltas': [],
        'efforts': [],
        'skill_uses': [],
        'workloads': [],

        # We track some values by player.
        'players': {},

        # Position and exploration values. We track the number of squares
        # visited so far and the new ones this period. These are sets of (x, z)
        # tuples.
        'visited_positions': set(),
        'new_positions': set(),

        # These accumulate data from messages that are then reported
        # periodically. In most cases, these are values since the last report.
        'cur_scores': None
    }


def record_aliases(data, config):
    """
    Find the aliases from the client info in the trial data and record them for
    later.
    """
    aliases = config.state['aliases']
    for client in data['client_info']:
        # This is what we will map to.
        playername = client['playername']

        for key in ('callsign', 'participant_id', 'participantid', 'uniqueid'):
            alias = client.get(key)
            if alias:
                aliases[alias] = playername

    config.logger.info(f'Prepared aliases: {aliases}')


def mission_start(_data, config):
    """
    Call this when the mission starts. Should reinitialize values as needed.
    """
    config.state['is_running'] = True
    config.step = 1
    # config.state['last_report_time'] = data['elapsed_milliseconds']


def mission_stop(_data, config):
    """
    Call this when the mission stops. Should report final values.
    """
    config.state['is_running'] = False
    config.step = 'final'

    visited_positions = config.state['visited_positions']
    # config.logger.info(f'Writing {len(visited_positions)} positions')
    visited_filename = os.path.join(config.results_dir, 'visited-ac.json')
    with open(visited_filename, 'wt', encoding='utf-8') as out:
        json.dump(list(visited_positions), out)

    # And plot once more with the final map.
    config.state['new_positions'] = set()
    plot_coverage(config)

    # And record a CSV file with all of the msg_data we published.
    df = pd.DataFrame.from_records(config.state['msg_data'])
    msg_filename = os.path.join(config.results_dir, 'msg-data.csv')
    df.to_csv(msg_filename, index=False)


def check_elapsed_time(data, config):
    """
    Check to see if we have reached the end of a period. If so, compute and
    report the next set of values. This should be called periodically, probably
    with every message we receive.
    """
    # If we are running, we should do things. Otherwise, we should sit tight.
    if not config.state['is_running']:
        return

    elapsed_ms, delta_ms = get_elapsed_time(data, config)
    if delta_ms < config.extra_info['period_ms']:
        return

    # Actually prepare and report the appropriate values.
    config.logger.info(f'Time to report scores -- step {config.step}: {elapsed_ms} (+ {delta_ms})')
    publish_ac_result(data, config)
    config.step += 1


def process_message(topic, data, config):
    """
    Records any ongoing state that will be used when producing results.
    """
    # Just make sure we have a record for this player.
    message_handler = MESSAGE_HANDLERS.get(topic)
    if message_handler is None:
        if topic not in config.unrecognized_topics:
            config.logger.warning(f'Unrecognized topic: {topic}')
            config.unrecognized_topics.add(topic)
        return

    # If we are not running, just return without doing any work.
    if not config.state['is_running']:
        return

    message_handler(data, config)


# ------------------------------------------------------------
# Here are the functions for accumulating data during runtime.

def record_location(data, config):
    """
    Here we accumulate the exploration information.
    """
    # We are not accumulating player-specific information here. But let's at
    # least make sure we have a data entry for them.
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    update_player_movement(data, player_data, config)

    # First we get the position (as integers).
    player_pos = (int(data['x']), int(data['z']))

    # We will set this to true if this as exploration. We use it to update
    # exploration timing.
    was_exploration = False

    # Now we get the FOV as a 7x7 square with player in the middle. CMU notes
    # that they lose cells in about 10-12% of cases with 5x5. After I worked out
    # the math, I asked CMU for their ideal size on this, and Pranav asked for
    # 5x5.
    #
    # for i in range(-3, 4):
    #     for j in range(-3, 4):
    for i in range(-2, 3):
        for j in range(-2, 3):
            pos = (player_pos[0] + i, player_pos[1] + j)

            # If this was not new, we're done here.
            if pos in config.state['visited_positions']:
                continue

            # If this was in the entrance hallway, just skip along.
            # if pos[1] > 62:
            #     continue

            # If we get here, the position is new, so record it now.
            config.state['visited_positions'].add(pos)
            config.state['new_positions'].add(pos)

            was_exploration = True
            record_skill_success(data, 'explore', player_data)

    if was_exploration:
        record_skill_start(data, 'explore', player_data)


def update_player_movement(data, player_data, _config):
    """
    Update our tracking for the player's movement. Label it exploration or
    standing as appropriate.
    """
    # If the delta in time will be zero, just don't even try.
    elapsed_ms = data['elapsed_milliseconds']
    if player_data['last_pos_elapsed_ms'] == elapsed_ms:
        return

    # We were checking for movement to see if the player has stopped breaking
    # rubble. However, some players move while breaking rubble. So now we just
    # check to see if enough time has elapsed and if so we stop the rubble
    # breaking.
    if player_data['dig_rubble_start_time'] is not None:
        rubble_duration = elapsed_ms - player_data['dig_rubble_start_time']
        if rubble_duration > 1000:
            # print('Canceling rubble digging due to elapsed time.')
            record_skill_duration(data, 'dig_rubble', player_data)

    # If the player is exploring and has moved to a new block, stop the timer.
    # If they are exploring a new block, we'll set the timer again in the
    # calling function.
    if player_data['explore_start_time'] is not None and \
        (int(data['x']) != int(player_data['last_x']) or
         int(data['z']) != int(player_data['last_z'])):
        record_skill_duration(data, 'explore', player_data)

    # Compute the movement distance and speed.
    move_speed = None
    if player_data['last_x'] is not None:
        dx = abs(data['x'] - player_data['last_x'])
        dz = abs(data['z'] - player_data['last_z'])
        dt = abs(elapsed_ms - player_data['last_pos_elapsed_ms'])

        move_dist = math.sqrt(dx * dx + dz * dz)
        move_speed = 1000.0 * move_dist / dt
        # print(f'moved {move_dist:.2f} at {move_speed:.2f} m/s')

        # Now check movement to see determine if the player is exploring or
        # standing around.
        if player_data['triage_start_time'] or \
            player_data['dig_rubble_start_time'] or \
            player_data['move_victim_start_time'] or \
            player_data['explore_start_time']:
            # They are engaged in a skill.
            pass
        elif move_speed is not None and move_speed < 1.0:
            # If they are moving, it is slow enough that we should call it
            # standing.
            player_data['inaction_stand_ms'] += dt

    # Update the position values for next step.
    player_data['last_x'] = data['x']
    player_data['last_z'] = data['z']
    player_data['last_pos_elapsed_ms'] = data['elapsed_milliseconds']


def record_scoreboard(data, config):
    """
    Record scoreboard data.
    """
    # elapsed_ms = data['elapsed_milliseconds']
    # timer = data['mission_timer']

    player_scores = {}
    team_score = 0
    for player, score in data['scoreboard'].items():
        if player == 'TeamScore':
            team_score = score
        else:
            player_scores[player] = score

    # print('Scoreboard', elapsed_ms, timer, score_by_player, score_team)
    config.state['cur_scores'] = {
        'player_scores': player_scores,
        'team_score': team_score
    }


def record_triage(data, config):
    """
    Record triage data.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    triage_state = data.get('triage_state')
    # Handle a triage start.
    if triage_state == 'IN_PROGRESS':
        record_skill_start(data, 'triage', player_data)
        return

    # If we get here it was a triage end.
    if triage_state == 'SUCCESSFUL':
        record_skill_success(data, 'triage', player_data)

    record_skill_duration(data, 'triage', player_data)


def record_role_selection(data, config):
    """
    Record information for role changes.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    if data['new_role'] == 'Hazardous_Material_Specialist':
        player_data['cur_role'] = 'HMS'
    elif data['new_role'] == 'Search_Specialist':
        player_data['cur_role'] = 'SS'
    elif data['new_role'] == 'Medical_Specialist':
        player_data['cur_role'] = 'MS'
    else:
        config.logger.warn(f"Unrecognized role for {player}: {data['new_role']}")
        player_data['cur_role'] = None


def record_tool_use(data, config):
    """
    Record information for tool use. Really this is just for gravel/rubble
    cleaning. Note that when we record the start time for rubble, we may never
    get a stop time (i.e., if they dont finish breaking the block).
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    tool_type = data['tool_type']
    target_block_type = data['target_block_type'].split(':')[1]

    # If it's not a hammer or the target is not rubble, just return.
    if tool_type != 'HAMMER' or target_block_type != 'gravel':
        return

    # Ensure we have a start time.
    record_skill_start(data, 'dig_rubble', player_data)


def record_rubble_destroyed(data, config):
    """
    This is the conclusion of rubble.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    # Record the success and time spent on this rubble.
    record_skill_success(data, 'dig_rubble', player_data)
    record_skill_duration(data, 'dig_rubble', player_data)


def record_pickup_victim(data, config):
    """
    Record information for related to moving victims.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    record_skill_start(data, 'move_victim', player_data)


def record_place_victim(data, config):
    """
    Record information for related to moving victims.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)

    record_skill_success(data, 'move_victim', player_data)
    record_skill_duration(data, 'move_victim', player_data)


def record_communication(data, config):
    """
    Record communications (from ASR). This has a mismatch with the basline
    computation. The baseline computation has all the data at once and can
    associate the message with the start time. Here, that ship may have sailed,
    and all we can do is consider the utterance as happening now.
    """
    player = get_player(data, config)
    player_data = ensure_player_data(player, config)
    player_chat_msg = data['features']['word_messages']
    config.logger.debug(
        f"Num words in message \"{player_chat_msg}\" by player {player}: {len(player_chat_msg)}")
    player_data["total_word_count"] += len(player_chat_msg)

MESSAGE_HANDLERS = {
    'observations/state': record_location,
    'observations/events/scoreboard': record_scoreboard,
    'observations/events/player/triage': record_triage,
    'observations/events/player/role_selected': record_role_selection,
    'observations/events/player/tool_used': record_tool_use,
    'observations/events/player/rubble_destroyed': record_rubble_destroyed,
    'observations/events/player/victim_picked_up': record_pickup_victim,
    'observations/events/player/victim_placed': record_place_victim,
    'agent/asr/final': record_communication
}

# ------------------------------------------------------------
# And here is the function to pull all the runtime results together and publish
# our message to the message bus.

def publish_ac_result(data, config):
    """
    Prepares the score information and publishes a message on the bus.
    """
    msg_data = prepare_ac_msg_data(data, config)
    config.state['msg_data'].append(msg_data)

    # Round the scores to a reasonable amount of precision.
    round_scores(msg_data)

    # Actually produce the message.
    config.helper.send_msg("agent/ac/" + \
                           config.helper.agent_name + "/ted",
                           "agent",
                           "AC:TED",
                           "0.1",
                           timestamp=config.helper.generate_timestamp(),
                           data=msg_data)

    # Plot the positions (if needed). Do this before resetting state for next
    # iteration so that we can see new positions.
    plot_coverage(config)

    config.logger.info(f' - data = {msg_data}')


def prepare_ac_msg_data(data, config):
    """
    Prepares and returns the AC message data to be published for this period.
    """
    elapsed_ms, delta_ms = get_elapsed_time(data, config)
    msg_data = {
        # Timing information.
        'elapsed_ms': elapsed_ms,
        'delta_ms': delta_ms
    }
    # Reset the time for next pass.
    config.state['last_report_time'] = elapsed_ms

    # Compute all the supporting values.
    compute_coverage(msg_data, config)
    compute_skills(msg_data, config)
    compute_scores(msg_data, config)
    compute_comms(msg_data, config)

    compute_process_values(msg_data, config)
    config.logger.debug(f"Message data: {msg_data}")
    return msg_data


def get_elapsed_time(data, config):
    """
    Finds the elapsed time and computes the delta since the last update. Returns
    both.
    """
    # If we do not have time information, do not do anything.
    if 'elapsed_milliseconds' not in data:
        return -1, -1

    # Get the time.
    elapsed_ms = data['elapsed_milliseconds']

    # If we did not have a last report time, set it now so that we'll start
    # going forward.
    if config.state['last_report_time'] < 0:
        config.state['last_report_time'] = elapsed_ms
        return elapsed_ms, 0

    delta_ms = elapsed_ms - config.state['last_report_time']
    return elapsed_ms, delta_ms


def compute_coverage(msg_data, config):
    """
    Computes the coverage values and adds them to the msg_data.
    """
    # Update location values.
    msg_data['process_coverage'] = len(config.state['new_positions'])
    msg_data['process_coverage_agg'] = \
        len(config.state['visited_positions']) / config.extra_info['total_coverage_area']

    # Reset bookkeeping.
    config.state['new_positions'] = set()


def compute_skills(msg_data, config):
    """
    Computes the skill action/inaction values and adds them to the msg_data.
    """
    elapsed_ms = msg_data['elapsed_ms']

    # Initialize the values to 0, we will add to them below.
    msg_data['inaction_stand_s'] = 0
    msg_data['action_triage_s'] = 0
    msg_data['triage_count'] = 0
    msg_data['action_dig_rubble_s'] = 0
    msg_data['dig_rubble_count'] = 0
    msg_data['action_move_victim_s'] = 0
    msg_data['move_victim_count'] = 0
    msg_data['action_explore_s'] = 0
    msg_data['explore_count'] = 0

    # Update skill-related values.
    for player_data in config.state['players'].values():
        # Add up the time just standing around.
        msg_data['inaction_stand_s'] += \
            player_data['inaction_stand_ms'] / 1000.0

        for skill in ('triage', 'dig_rubble', 'move_victim', 'explore'):
            duration_ms = player_data[f'{skill}_duration_ms']
            # If we have an activity that is continuing. Count it here and reset
            # the start time to capture the duration for the next period.
            skill_start_key = f'{skill}_start_time'
            if player_data[skill_start_key]:
                duration_ms += (elapsed_ms - player_data[skill_start_key])
                player_data[skill_start_key] = elapsed_ms

            msg_data[f'action_{skill}_s'] += (duration_ms / 1000.0)
            msg_data[f'{skill}_count'] += player_data[f'{skill}_success_count']

    config.state['triaging'].append(msg_data['action_triage_s'])
    msg_data['process_triaging_agg'] = \
        sum(config.state['triaging']) / config.extra_info['total_triage_time_s']

    # Reset bookkeeping.
    reset_player_field('inaction_stand_ms', config)
    for skill in ('triage', 'dig_rubble', 'move_victim', 'explore'):
        reset_player_field(f'{skill}_duration_ms', config)
        reset_player_field(f'{skill}_success_count', config)


def compute_scores(msg_data, config):
    """
    Computes the score-related values and adds them to the msg_data.
    """
    # Update the score-related values.
    if config.state['cur_scores']:
        cur_team_score = config.state['cur_scores']['team_score']
        prev_team_score = sum(config.state['team_scores'])

        msg_data['team_score'] = cur_team_score - prev_team_score
        msg_data['team_score_agg'] = cur_team_score
    else:
        msg_data['team_score'] = 0
        msg_data['team_score_agg'] = 0

    # Update for next round.
    config.state['team_scores'].append(msg_data['team_score'])


def compute_comms(msg_data, config):
    """
    Computes the communications values and adds them to the msg_data.
    """
    # Update the comms-related values.
    player_word_counts = [x['total_word_count'] for x in config.state['players'].values()]
    assert len(player_word_counts) == 3 # Should always have 3 players
    msg_data['comms_total_words'] = sum(player_word_counts)
    # Use unbiased sample variance
    msg_data['comms_equity'] = np.array(player_word_counts).std(ddof=1)

def compute_process_values(msg_data, config):
    """
    Roll up the intermediate values to produce higher-level team-process values.
    """
    delta_ms = msg_data['delta_ms']

    # Accumulate the total time available as the length of this period times the
    # number of players present.
    num_players = len(config.state['players'])
    players_delta_s = num_players * delta_ms / 1000.0
    config.state['players_deltas'].append(players_delta_s)

    skill_use_s = msg_data['action_triage_s'] + \
        msg_data['action_dig_rubble_s'] + \
        msg_data['action_move_victim_s'] + \
        msg_data['action_explore_s']
    msg_data['process_skill_use_s'] = skill_use_s
    config.state['skill_uses'].append(skill_use_s)

    # Effort is the flip of inaction.
    msg_data['process_effort_s'] = \
        players_delta_s - msg_data['inaction_stand_s']
    config.state['efforts'].append(msg_data['process_effort_s'])

    msg_data['process_skill_use_rel'] = 0
    if msg_data['process_effort_s']:
        msg_data['process_skill_use_rel'] = \
            msg_data['process_skill_use_s'] / msg_data['process_effort_s']

    # Workload burnt is average of exploration and triage.
    msg_data['process_workload_burnt'] = \
        msg_data['process_coverage'] / config.extra_info['total_coverage_area'] + \
        msg_data['action_triage_s'] / config.extra_info['total_triage_time_s']
    msg_data['process_workload_burnt'] *= 0.5
    config.state['workloads'].append(msg_data['process_workload_burnt'])

    # Now compute the aggregate values. These reflect the full history and are
    # normalized so that they should be between 0 and 1.
    #
    # The skill use and effort seconds are summed across all players. So we
    # divide by the number of player seconds as part of computing the agg value.
    #
    total_players_s = num_players * config.extra_info['total_mission_s']
    if total_players_s:
        msg_data['process_skill_use_agg'] = \
            sum(config.state['skill_uses']) / total_players_s
        msg_data['process_effort_agg'] = \
            sum(config.state['efforts']) / total_players_s
        msg_data['process_workload_burnt_agg'] = sum(config.state['workloads'])
    else:
        msg_data['process_skill_use_agg'] = 0.0
        msg_data['process_effort_agg'] = 0.0
        msg_data['process_workload_burnt_agg'] = 0.0


def reset_player_field(field, config):
    """
    Resets the given field to 0 for each known player state.
    """
    for player in config.state['players'].values():
        player[field] = 0


def round_scores(msg_data):
    """
    Round the values to a uniform (and not excessive) number of decimal places.
    """
    for key, val in msg_data.items():
        if isinstance(val, float) and abs(val) < sys.float_info.epsilon:
            # Cannot round 0.0
            continue
        if isinstance(val, float):
            val = round(val, NUM_SIG_FIGS - 1 - int(np.floor(np.log10(abs(val)))))
            msg_data[key] = val

# ------------------------------------------------------------
# Support functions

def get_player(data, config):
    """
    Returns the participant ID from the data. Falls back to playername or other
    as needed.
    """
    # If we were passed a message, step down into the data.
    if 'data' in data:
        data = data['data']

    if 'participant_id' in data:
        name = data['participant_id']
    else:
        name = data.get('playername')

    aliases = config.state['aliases']
    if name in aliases:
        name = aliases[name]

    return name


def ensure_player_data(player, config):
    """
    Makes sure the player is recorded in the config. Return the player data
    structure.
    """
    if player not in config.state['players']:
        config.state['players'][player] = {
            # Used for computing position delta (and speed).
            'last_x': None,
            'last_y': None,
            'last_pos_elapsed_ms': None,

            # Time standing without exercising a skill.
            'inaction_stand_ms': 0,

            # Time the player started triaging. Only set *while* the player is
            # actively triaging.
            'triage_start_time': None,
            # Time spent triaging since the last time we reported results.
            'triage_duration_ms': 0,
            # Number of successful triages since we last reported results.
            'triage_success_count': 0,

            # Times for digging rubble skill.
            'dig_rubble_start_time': None,
            'dig_rubble_duration_ms': 0,
            'dig_rubble_success_count': 0,

            # Times for moving victim skill.
            'move_victim_start_time': None,
            'move_victim_duration_ms': 0,
            'move_victim_success_count': 0,

            # Times for exploring.
            'explore_start_time': None,
            'explore_duration_ms': 0,
            'explore_success_count': 0,

            # Information pertaining to role.
            'cur_role': None,

            # Total number of words in messages said by player
            'total_word_count': 0
        }
    return config.state['players'][player]


def record_skill_start(data, skill, player_data):
    """
    Record the start of a skill use.
    """
    start_time_key = f'{skill}_start_time'

    # If we are not already doing the thing, mark the time was started doing the
    # thing.
    if player_data[start_time_key] is None:
        elapsed_ms = data['elapsed_milliseconds']
        player_data[start_time_key] = elapsed_ms


def record_skill_success(_data, skill, player_data):
    """
    Record the successful completion of a skill use. This is only success, not
    failure.
    """
    success_key = f'{skill}_success_count'
    player_data[success_key] += 1


def record_skill_duration(data, skill, player_data):
    """
    Record the time spent on the skill (irrespective of success or failure).
    """
    start_time_key = f'{skill}_start_time'
    duration_key = f'{skill}_duration_ms'

    # Compute the triage duration and add it to the state. If we do not have a
    # start time, we cannot compute a duration, so just return.
    if player_data[start_time_key] is None:
        return

    # Store the duration.
    elapsed_ms = data['elapsed_milliseconds']
    duration_ms = elapsed_ms - player_data[start_time_key]
    player_data[duration_key] += duration_ms

    # Reset the start time.
    player_data[start_time_key] = None


def plot_coverage(config):
    """
    If the plot_coverage flag is set, makes a plot of the visited positions.
    """
    if not config.plot_coverage:
        return

    visited_positions = config.state['visited_positions']
    new_positions = config.state['new_positions']

    config.logger.info('Plotting visited positions')
    minx = min([x[0] for x in visited_positions])
    maxx = max([x[0] for x in visited_positions])
    miny = min([x[1] for x in visited_positions])
    maxy = max([x[1] for x in visited_positions])

    width = maxx - minx + 1
    height = maxy - miny + 1

    # grid = np.ndarray(shape=(height, width, 3), dtype=float)
    grid = np.zeros(shape=(height, width, 3), dtype=float)
    for pos in visited_positions:
        x = pos[0] - minx
        y = pos[1] - miny

        if pos in new_positions:
            grid[y][x][0] = 1.0
            grid[y][x][1] = 1.0
            grid[y][x][2] = 1.0
        else:
            grid[y][x][0] = 0.5
            grid[y][x][1] = 0.5
            grid[y][x][2] = 0.5

    plt.figure(figsize=(12, 12))
    plt.imshow(grid, interpolation='none')
    plot_filename = \
        os.path.join(config.results_dir, f'visited-positions-{config.step}.png')
    plt.savefig(plot_filename)
    config.logger.info(f' - wrote positions to {plot_filename}')
