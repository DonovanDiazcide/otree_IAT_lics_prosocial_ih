import time
import random
from pathlib import Path

from otree.api import *
from otree import settings


from . import stimuli_utils
from . import image_utils

doc = """
Generic atimulus/response app
"""


class Constants(BaseConstants):
    name_in_url = "generic"
    players_per_group = None
    num_rounds = 1

    """choices of categories and responses
    both for stimuli categories and responses
    should be associated with actual categories from pool in session config: 
    `categories={'left': something, 'right': something}`
    """
    choices = ["left", "right"]

    """Mapping of keys to choices
    the key names to use to match KeyboardEvent
    possible key names reference and compatibility: 
    https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code/code_values
    """
    keymap = {'KeyF': 'left', 'KeyJ': 'right'}

    instructions_template = __name__ + "/instructions.html"


C = Constants

POOL = stimuli_utils.load_csv(
    Path(__file__).parent / "stimuli.csv", ['stimulus', 'category']
)


class Subsession(BaseSubsession):
    is_practice = models.BooleanField(initial=False)


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    iteration = models.IntegerField(initial=0)
    num_trials = models.IntegerField(initial=0)
    num_solved = models.IntegerField(initial=0)
    num_failed = models.IntegerField(initial=0)


class Trial(ExtraModel):
    """A record of single iteration"""

    player = models.Link(Player)
    round = models.IntegerField(initial=0)
    iteration = models.IntegerField(initial=0)
    # time when the trial was picked up, None for pregenerated
    server_loaded_timestamp = models.FloatField()

    stimulus = models.StringField()
    category = models.StringField()
    solution = models.StringField()

    attempts = models.IntegerField(initial=0)
    server_response_timestamp = models.FloatField()
    response = models.StringField()
    reaction_time = models.FloatField()
    is_correct = models.BooleanField()


def creating_session(subsession: Subsession):
    session = subsession.session
    defaults = dict(
        num_iterations=10,
        trial_pause=1.0,
        focus_time=1.0,
        stimulus_time=None,
        freeze_seconds=0.5,
        attempts_per_trial=1,
    )
    required = ["categories", "labels"]
    session.params = {}
    for param in defaults:
        session.params[param] = session.config.get(param, defaults[param])
    for param in required:
        session.params[param] = session.config[param]

    subsession.is_practice = True

    for player in subsession.get_players():
        generate_all_trials(player)


def get_progress(player: Player, trial: Trial = None) -> dict:
    """Return whatever progress data to show on page"""
    params = player.session.params
    return dict(
        iteration=player.iteration,
        iterations_total=params["num_iterations"],
        attempts=trial.attempts if trial else None,
        attempts_total=params["attempts_per_trial"],
        num_trials=player.num_trials,
    )


def update_stats(player: Player, trial: Trial):
    """Update player stats"""
    if trial.is_correct:
        player.num_solved += 1
    else:
        player.num_failed += 1


def undo_stats(player: Player, trial: Trial):
    """Undo last update of stats"""
    if trial.is_correct:
        player.num_solved -= 1
    else:
        player.num_failed -= 1


def generate_trial(player: Player) -> Trial:
    """Create new trial with random stimuli"""
    params = player.session.params
    target_side = random.choice(C.choices)
    target_cat = params['categories'][target_side]
    targets = stimuli_utils.filter_by_category(POOL, [target_cat])
    target = random.choice(targets)

    return Trial.create(
        round=player.round_number,
        player=player,
        iteration=player.iteration,
        #
        stimulus=target['stimulus'],
        category=target['category'],
        solution=target_side,
    )


def generate_all_trials(player: Player):
    """Create `num_iterations` trials with non-repeating random stimuli"""
    params = player.session.params
    categories = params['categories']
    count = params['num_iterations']

    if not count:
        raise RuntimeError("Cannot generate trials without `num_iterations`")

    selected = stimuli_utils.filter_by_category(POOL, list(categories.values()))

    if len(selected) < count:
        raise RuntimeError(f"Insufficient stimuli in the pool for {count} iterations")

    random.shuffle(selected)

    categories_inversed = {v: k for k, v in categories.items()}

    for i in range(count):
        target = selected[i]
        target_side = categories_inversed[target['category']]

        Trial.create(
            round=player.round_number,
            player=player,
            iteration=1 + i,
            #
            stimulus=target['stimulus'],
            category=target['category'],
            solution=target_side,
        )


def get_current_trial(player: Player) -> Trial:
    """Get trial for current iteration, or None"""
    trials = Trial.filter(player=player, iteration=player.iteration)
    if trials:
        [trial] = trials
        return trial


def static_image_url(path):
    """hardcoded for now"""
    return f'/static/images/{path}'


def render_image(text):
    img = image_utils.render_text(text)
    img = image_utils.distort_image(img)
    data = image_utils.encode_image(img)
    return data


def encode_trial(trial: Trial) -> dict:
    """Get trial data to pass to live page"""
    # for orinary words
    # return dict(stimulus=trial.stimulus, datatype="text")

    # for static images
    # url = static_url_for(trial.stimulus)
    # return dict(image_url=url, datatype="image-url")

    # for rendered text
    data = render_image(trial.stimulus)
    return dict(image_data=data, datatype="image-data")


def check_response(trial: Trial, response: str) -> bool:
    """Check if the response is correct"""
    return trial.solution == response


def play_game(player: Player, message: dict):
    """Main task workflow on the live page
    Implemented as reactive scheme: receive message from browser, react, respond.

    Generic task workflow, from server point of view:

    - receive: {'type': 'load'} -- the page has been loaded
    - check if it's game start or page refresh midgame
    - respond: {'type': 'status', 'progress': status}
    - respond: {'type': 'status', 'progress': status, 'trial': data} -- in case of midgame page reload

    - receive: {'type': 'new'} -- request for a new (or first) trial
    - generate new trial
    - respond: {'type': 'trial', 'trial': data}
    - respond: {'type': 'status', 'game_over': True} -- if num_iterations exhausted

    - receive: {'type': 'response', 'response': ..., 'reaction_time': ...} -- user responded
    - check and record response
    - respond: {'type': 'feedback', 'is_correct': true|false} -- feedback to the response

    Field 'progress' is added to all server responses.
    """
    params = player.session.params
    now = time.time()
    current = get_current_trial(player)

    message_type = message["type"]

    print("iteration:", player.iteration)
    print("current trial:", current)
    print("received:", message)

    def respond(msgtype, **fields):
        """Prepare message to send to current player"""
        msgdata = {'type': msgtype}
        msgdata.update(fields)
        msgdata['progress'] = get_progress(player, current)
        print("response:", msgdata)
        return {player.id_in_group: msgdata}

    if message_type == "load":  # client loaded page
        if current:
            return respond("status", trial=encode_trial(current))
        else:
            return respond("status")

    if message_type == "new":  # client requests new trial
        if current is not None:
            if current.response is None:
                raise RuntimeError("trying to skip unanswered trial")
            if now < current.server_loaded_timestamp + params["trial_pause"]:
                raise RuntimeError("advancing too fast")

        player.iteration += 1

        if player.iteration > params["num_iterations"]:
            return respond("status", game_over=True)

        # with on-the-go generated trials
        # t = generate_trial(player)

        # with pre-generated trials
        t = get_current_trial(player)

        if t is None:
            raise RuntimeError("failed to pick next trial")

        t.server_loaded_timestamp = now

        return respond("trial", trial=encode_trial(t))

    if message_type == "response":  # client responded current trial
        max_attempts = params['attempts_per_trial']

        if current is None:
            raise RuntimeError("response without trial")

        if current.response is not None:  # it's a retry
            if max_attempts <= 1:
                raise RuntimeError("retrying not allowed")

            if current.attempts >= max_attempts:
                raise RuntimeError("max attempts exhausted")

            if now < current.server_response_timestamp + params["freeze_seconds"]:
                raise RuntimeError("retrying too fast")

            undo_stats(player, current)

        response = message["response"]

        if response == "" or response is None:
            raise ValueError("bogus response")

        current.response = response
        current.reaction_time = message["reaction"]
        current.is_correct = check_response(current, response)
        current.server_response_timestamp = now
        current.attempts += 1

        if current.attempts == 1:
            # count trials only once
            player.num_trials += 1

        update_stats(player, current)

        # if this is a final attempt and user should advance
        is_final = (
            max_attempts == 1 or current.is_correct or current.attempts == max_attempts
        )

        return respond("feedback", is_correct=current.is_correct, is_final=is_final)

    if message_type == "cheat" and settings.DEBUG:  # debugging
        cheat_round(player, message['rt'])
        return respond("status", game_over=True)

    raise RuntimeError("unrecognized message from client")


def cheat_round(player, rt_mean):
    params = player.session.params
    now = time.time()

    rt_mean = float(rt_mean)
    rt_std = 1.0

    for i in range(max(1, player.iteration), params['num_iterations'] + 1):
        r = random.choice(Constants.choices)
        rt = max(0.0, random.gauss(rt_mean, rt_std))
        t = Trial.filter(player=player, iteration=i)[0]
        t.server_loaded_timestamp = now + i
        t.server_response_timestamp = now + i + rt
        t.response = r
        t.is_correct = check_response(t, r)
        t.reaction_time = rt


class Intro(Page):
    @staticmethod
    def vars_for_template(player: Player):
        params = player.session.params
        return dict(params=params, keymap=C.keymap, DEBUG=settings.DEBUG)


class Main(Page):
    @staticmethod
    def js_vars(player: Player):
        params = player.session.params
        return dict(params=params, keymap=C.keymap)

    @staticmethod
    def vars_for_template(player: Player):
        params = player.session.params
        return dict(params=params, keymap=C.keymap, DEBUG=settings.DEBUG)

    live_method = play_game


class Results(Page):
    pass


page_sequence = [Intro, Main, Results]


def custom_export(players):
    yield [
        "participant_code",
        "is_dropout",
        "session",
        "round",
        "is_practice",
        "player",
        "iteration",
        "server_loaded_timestamp",
        "stimulus",
        "category",
        "server_response_timestamp",
        "response",
        "response_correct",
        "reaction_time",
        "attempts",
    ]
    for player in players:
        participant = player.participant
        session = player.session
        subsession = player.subsession

        player_fields = [
            participant.code,
            participant.is_dropout if 'is_dropout' in participant.vars else None,
            session.code,
            subsession.round_number,
            subsession.is_practice,
            player.id,
        ]

        # yield a line for players even without trials
        yield player_fields

        for trial in Trial.filter(player=player):
            yield player_fields + [
                trial.iteration,
                trial.server_loaded_timestamp,
                trial.stimulus,
                trial.category,
                trial.server_response_timestamp,
                trial.response,
                trial.is_correct,
                trial.reaction_time,
                trial.attempts,
            ]
