import time
from otree.api import expect, Bot
from . import *


class PlayerBot(Bot):
    def play_round(self):
        yield Game

        trials = Trial.filter(player=self.player)
        expect(len(trials), 9)

        expect(self.player.total, 9)
        expect(self.player.answered, 9)
        expect(self.player.correct, 5)
        expect(self.player.incorrect, 4)


def call_live_method(method, group: Group, **kwargs):
    player = group.get_players()[0]
    conf = player.session.config
    trial_delay = conf.get('trial_delay', 1.0)

    iteration = 0
    timestamp = 0

    def forward():
        time.sleep(trial_delay)
        method(1, {'next': True})
        _trial = get_last_trial(player)
        expect(_trial.timestamp, ">", timestamp)
        expect(_trial.iteration, ">", iteration)
        return _trial

    def answer(ans, correct):
        _response = method(1, {'answer': ans})
        _feedback = _response[1]['feedback']
        _trial = get_last_trial(player)
        expect(_trial.answer, ans)
        expect(_feedback, correct)
        expect(_trial.is_correct, correct)
        return _trial

    # 2 correct answers lower
    for i in range(2):
        trial = forward()
        trial = answer(trial.solution.lower(), True)
        iteration, timestamp = trial.iteration, trial.timestamp

    # 3 correct answers upper
    for i in range(3):
        trial = forward()
        trial = answer(trial.solution.upper(), True)
        iteration, timestamp = trial.iteration, trial.timestamp

    # 4 incorrect answers
    for i in range(4):
        trial = forward()
        trial = answer("xxx", False)
        iteration, timestamp = trial.iteration, trial.timestamp
