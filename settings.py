
from os import environ
SESSION_CONFIGS = [
    dict(
        name="iat_images",
        display_name="IAT using images",
        num_demo_participants=4,
        app_sequence=["iat"],
        primary_images=True,
        primary=['images:felidae', 'images:canidae', 'images:white', "images:black"],
        secondary_images=True,
        secondary=['emojis:positive', 'emojis:negative'],
        num_iterations={1: 5, 2: 5, 3: 10, 4: 20, 5: 5, 6: 10, 7: 20,
                        8: 5, 9: 5, 10: 10, 11: 20, 12: 5, 13: 10, 14: 20,
                        15: 1, 16: 1, 17: 1, 18: 1,
                        },
    ),
]

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

PARTICIPANT_FIELDS = ['is_dropout']
SESSION_FIELDS = ['params']

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = "en"

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = "USD"
USE_POINTS = True

ADMIN_USERNAME = "admin"
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get("OTREE_ADMIN_PASSWORD")

DEMO_PAGE_TITLE = "Welcome to IAT based experiment"
DEMO_PAGE_INTRO_HTML = """
Espera las instrucciones para saber a qué página del IAT ingresar
"""

SECRET_KEY = "2015765205890"

# adjustments for testing
# generating session configs for all varieties of features
import sys

ROOMS = [
    dict(
        name='IAT_experiment',
        display_name='IAT_experiment',
        participant_label_file='_rooms/econ101.txt',
    ),
    dict(name='live_demo', display_name='Room for live demo (no participant labels)'),
]


if sys.argv[1] == 'test':
    MAX_ITERATIONS = 5
    FREEZE_TIME = 100
    TRIAL_PAUSE = 200
    TRIAL_TIMEOUT = 300

    SESSION_CONFIGS = [
        dict(
            name=f"testing_generic",
            num_demo_participants=1,
            app_sequence=['generic'],
            auto_response_time=None,
            input_freezing_time=FREEZE_TIME,
            inter_trial_time=TRIAL_PAUSE,
            num_iterations=MAX_ITERATIONS,
            attempts_per_trial=1,
            categories={'foo': 'positive', 'bar': 'negative'},
            labels={'foo': 'Positive', 'bar': 'Negative'},
        ),
        dict(
            name=f"testing_generic_retries",
            num_demo_participants=1,
            app_sequence=['generic'],
            auto_response_time=None,
            input_freezing_time=FREEZE_TIME,
            inter_trial_time=TRIAL_PAUSE,
            num_iterations=MAX_ITERATIONS,
            attempts_per_trial=3,
            categories={'foo': 'positive', 'bar': 'negative'},
            labels={'foo': 'Positive', 'bar': 'Negative'},
        ),
        dict(
            name=f"testing_generic_gonogo",
            num_demo_participants=1,
            app_sequence=['generic'],
            auto_response_time=TRIAL_TIMEOUT,
            input_freezing_time=FREEZE_TIME,
            inter_trial_time=TRIAL_PAUSE,
            num_iterations=MAX_ITERATIONS,
            attempts_per_trial=1,
            categories={'foo': 'positive', 'bar': 'negative'},
            labels={'foo': 'Positive', 'bar': 'Negative'},
        ),
        dict(
            name=f"testing_iat",
            num_demo_participants=1,
            app_sequence=['iat'],
            trial_delay=TRIAL_PAUSE / 1000.0,
            retry_delay=FREEZE_TIME / 1000.0,
            primary=['canidae', 'felidae'],
            secondary=['positive', 'negative'],
            num_iterations={1: 2, 2: 2, 3: 3, 4: 3, 5: 2, 6: 3, 7: 3},
        ),
        dict(
            name=f"testing_sliders",
            num_demo_participants=1,
            app_sequence=['sliders'],
            trial_delay=TRIAL_PAUSE / 1000.0,
            retry_delay=FREEZE_TIME / 1000.0,
            num_sliders=3,
            attempts_per_slider=3,
        ),
    ]
    for task in ['decoding', 'matrix', 'transcription']:
        SESSION_CONFIGS.extend(
            [
                dict(
                    name=f"testing_{task}_defaults",
                    num_demo_participants=1,
                    app_sequence=['real_effort'],
                    puzzle_delay=TRIAL_PAUSE / 1000.0,
                    retry_delay=FREEZE_TIME / 1000.0,
                ),
                dict(
                    name=f"testing_{task}_retrying",
                    num_demo_participants=1,
                    app_sequence=['real_effort'],
                    puzzle_delay=TRIAL_PAUSE / 1000.0,
                    retry_delay=FREEZE_TIME / 1000.0,
                    attempts_per_puzzle=5,
                ),
                dict(
                    name=f"testing_{task}_limited",
                    num_demo_participants=1,
                    app_sequence=['real_effort'],
                    puzzle_delay=TRIAL_PAUSE / 1000.0,
                    retry_delay=FREEZE_TIME / 1000.0,
                    max_iterations=MAX_ITERATIONS,
                ),
            ]
        )
