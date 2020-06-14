import random

fruits = [
    'apple',
    'banana',
    'fig',
    'grape',
    'lemon',
    'lime',
    'orange',
    'peach',
    'plum',
]

animals = [
    'bat',
    'bear',
    'bird',
    'cat',
    'cow',
    'deer',
    'dog',
    'dove',
    'dragon',
    'duck',
    'eagle',
    'fish',
    'fox',
    'frog',
    'goose',
    'lion',
    'mouse',
    'owl',
    'pig',
    'rat',
    'seal',
    'shark',
    'sheep',
    'snake',
    'spider',
    'tiger',
    'turkey',
    'viper',
    'whale',
    'wolf',
]

colors = [
    'black',
    'blue',
    'bronze',
    'brown',
    'fire',
    'forest',
    'gold',
    'gray',
    'green',
    'navy',
    'pink',
    'purple',
    'red',
    'silver',
    'sky',
    'white',
    'yellow',
]


def generate_phrase(n=2):
    """Randomly generate a simple memorable phrase.

    Args:
        n: int, number of words in the phrase, default 2, max 3.
    """
    if n not in range(1, 4):
        raise Exception("Invalid number of words for phrase: {}.".format(n))

    lists = [fruits, animals, colors]

    return ' '.join([random.choice(l) for l in random.sample(lists, n)])
