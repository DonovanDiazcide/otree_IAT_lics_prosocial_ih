import time
import random
from otree.api import *
from otree import settings
from . import stimuli
from . import blocks
from . import stats

doc = """
Implicit Association Test, draft
"""


class Constants(BaseConstants):
    name_in_url = 'iat'
    players_per_group = None
    num_rounds = 7

    # the keys F and J have tactile marks
    keys = {'left': "f", 'right': "j"}
    trial_delay = 0.250


class Subsession(BaseSubsession):
    practice = models.BooleanField()

    primary_left = models.StringField()
    primary_right = models.StringField()
    secondary_left = models.StringField()
    secondary_right = models.StringField()


def get_block_for_round(rnd):
    """Get a round setup from BLOCKS with actual categories' names substituted from session config
    The `rnd`: Player or Subsession
    """
    block = blocks.BLOCKS[rnd.round_number]
    result = blocks.configure(block, rnd.session.config)
    return result


def get_num_iterations_for_round(rnd):
    """Get configured number of iterations
    The `rnd`: Player or Subsession
    """
    idx = rnd.round_number
    num = rnd.session.iat_params['num_iterations'][idx]
    return num


def creating_session(subsession: Subsession):
    session = subsession.session
    defaults = dict(
        retry_delay=0.5,
        trial_delay=0.5,
        num_iterations={1: 5, 2: 5, 3: 10, 4: 20, 5: 5, 6: 10, 7: 20},
    )
    session.iat_params = {}
    for param in defaults:
        session.iat_params[param] = session.config.get(param, defaults[param])

    block = get_block_for_round(subsession)

    subsession.practice = block['practice']
    subsession.primary_left = block['left'].get('primary', "")
    subsession.primary_right = block['right'].get('primary', "")
    subsession.secondary_left = block['left'].get('secondary', "")
    subsession.secondary_right = block['right'].get('secondary', "")


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    iteration = models.IntegerField(initial=0)
    num_trials = models.IntegerField(initial=0)
    num_correct = models.IntegerField(initial=0)
    num_failed = models.IntegerField(initial=0)


class Trial(ExtraModel):
    """A record of single iteration
    Keeps corner categories from round setup to simplify furher analysis.
    The stimulus class is for appropriate styling on page.
    """

    player = models.Link(Player)
    round = models.IntegerField(initial=0)
    iteration = models.IntegerField(initial=0)
    timestamp = models.FloatField(initial=0)

    stimulus_cls = models.StringField(choices=('primary', 'secondary'))
    stimulus_cat = models.StringField()
    stimulus = models.StringField()
    correct = models.StringField(choices=('left', 'right'))

    response = models.StringField(choices=('left', 'right'))
    response_timestamp = models.FloatField()
    reaction_time = models.FloatField()
    is_correct = models.BooleanField()
    retries = models.IntegerField(initial=0)


def generate_trial(player: Player) -> Trial:
    """Create new question for a player"""
    block = get_block_for_round(player.subsession)
    chosen_side = random.choice(['left', 'right'])
    chosen_cls = random.choice(list(block[chosen_side].keys()))
    chosen_cat = block[chosen_side][chosen_cls]
    stimulus = random.choice(stimuli.DICT[chosen_cat])

    player.iteration += 1
    return Trial.create(
        player=player,
        iteration=player.iteration,
        timestamp=time.time(),
        #
        stimulus_cls=chosen_cls,
        stimulus_cat=chosen_cat,
        stimulus=stimulus,
        correct=chosen_side,
    )


def get_current_trial(player: Player):
    """Get last (current) question for a player"""
    trials = Trial.filter(player=player, iteration=player.iteration)
    if trials:
        [trial] = trials
        return trial


def encode_trial(trial: Trial):
    return dict(
        cls=trial.stimulus_cls,
        cat=trial.stimulus_cat,
        word=trial.stimulus,
    )


def get_progress(player: Player):
    """Return current player progress"""
    return dict(
        num_trials=player.num_trials,
        num_correct=player.num_correct,
        num_incorrect=player.num_failed,
        iteration=player.iteration,
        total=get_num_iterations_for_round(player),
    )


def custom_export(players):
    """Dumps all the trials generated"""
    yield [
        "session",
        "participant_code",
        "round",
        "primary_left",
        "primary_right",
        "secondary_left",
        "secondary_right",
        "iteration",
        "timestamp",
        "stimulus_class",
        "stimulus_category",
        "stimulus",
        "expected",
        "response",
        "is_correct",
        "reaction_time",
    ]
    for p in players:
        if p.round_number not in (3, 4, 6, 7):
            continue
        participant = p.participant
        session = p.session
        subsession = p.subsession
        for z in Trial.filter(player=p):
            yield [
                session.code,
                participant.code,
                subsession.round_number,
                subsession.primary_left,
                subsession.primary_right,
                subsession.secondary_left,
                subsession.secondary_right,
                z.iteration,
                z.timestamp,
                z.stimulus_cls,
                z.stimulus_cat,
                z.stimulus,
                z.correct,
                z.response,
                z.is_correct,
                z.reaction_time,
            ]


def play_game(player: Player, message: dict):
    """Main game workflow
    Implemented as reactive scheme: receive message from vrowser, react, respond.

    Generic game workflow, from server point of view:
    - receive: {'type': 'load'} -- empty message means page loaded
    - check if it's game start or page refresh midgame
    - respond: {'type': 'status', 'progress': ...}
    - respond: {'type': 'status', 'progress': ..., 'trial': data} -- in case of midgame page reload

    - receive: {'type': 'next'} -- request for a next/first trial
    - generate new trial
    - respond: {'type': 'trial', 'trial': data}

    - receive: {'type': 'answer', 'answer': ...} -- user answered the trial
    - check if the answer is correct
    - respond: {'type': 'feedback', 'is_correct': true|false} -- feedback to the answer

    When done solving, client should explicitely request next trial by sending 'next' message

    Field 'progress' is added to all server responses to indicate it on page.

    To indicate max_iteration exhausted in response to 'next' server returns 'status' message with iterations_left=0
    """
    session = player.session
    my_id = player.id_in_group
    ret_params = session.iat_params
    max_iters = get_num_iterations_for_round(player)

    now = time.time()
    # the current trial or none
    current = get_current_trial(player)

    message_type = message['type']

    # print("iteration:", player.iteration)
    # print("current:", current)
    # print("received:", message)

    # page loaded
    if message_type == 'load':
        p = get_progress(player)
        if current:
            return {my_id: dict(type='status', progress=p, trial=encode_trial(current))}
        else:
            return {my_id: dict(type='status', progress=p)}

    # client requested new trial
    if message_type == "next":
        if current is not None:
            if current.response is None:
                raise RuntimeError("trying to skip over unsolved trial")
            if now < current.timestamp + ret_params["trial_delay"]:
                raise RuntimeError("retrying too fast")
            if current.iteration == max_iters:
                return {
                    my_id: dict(
                        type='status', progress=get_progress(player), iterations_left=0
                    )
                }
        # generate new trial
        z = generate_trial(player)
        p = get_progress(player)
        return {my_id: dict(type='trial', trial=encode_trial(z), progress=p)}

    # client gives an answer to current trial
    if message_type == "answer":
        if current is None:
            raise RuntimeError("trying to answer no trial")

        if current.response is not None:  # it's a retry
            if now < current.response_timestamp + ret_params["retry_delay"]:
                raise RuntimeError("retrying too fast")

            # undo last updation of player progress
            player.num_trials -= 1
            if current.is_correct:
                player.num_correct -= 1
            else:
                player.num_failed -= 1

        # check answer
        answer = message["answer"]

        if answer == "" or answer is None:
            raise ValueError("bogus answer")

        current.response = answer
        current.reaction_time = message["reaction_time"]
        current.is_correct = current.correct == answer
        current.response_timestamp = now

        # update player progress
        if current.is_correct:
            player.num_correct += 1
        else:
            player.num_failed += 1
        player.num_trials += 1

        p = get_progress(player)
        return {
            my_id: dict(
                type='feedback',
                is_correct=current.is_correct,
                progress=p,
            )
        }

    if message_type == "cheat" and settings.DEBUG:
        # generate remaining data for the round
        m = random.random() + 1.0
        if current:
            current.delete()
        for i in range(player.iteration, max_iters):
            t = generate_trial(player)
            t.iteration = i
            t.timestamp = now + i
            t.response = t.correct
            t.is_correct = True
            t.response_timestamp = now + i
            t.reaction_time = random.gauss(m, 0.250)
        return {
            my_id: dict(type='status', progress=get_progress(player), iterations_left=0)
        }

    raise RuntimeError("unrecognized message from client")


# PAGES


class Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class RoundN(Page):
    template_name = "iat/Main.html"

    @staticmethod
    def js_vars(player: Player):
        return dict(params=player.session.iat_params, keys=Constants.keys)

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            params=player.session.iat_params,
            block=get_block_for_round(player),
            num_iterations=get_num_iterations_for_round(player),
            DEBUG=settings.DEBUG,
            keys=Constants.keys,
        )

    live_method = play_game


class Results(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 7

    @staticmethod
    def vars_for_template(player: Player):
        return dict()


page_sequence = [Intro, RoundN, Results]
