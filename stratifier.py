"""
Study: NS15S

sent to /api/stratify:
    name: student_condition
    proportions: {"treatment": 1, "control": 1}
    study/program: Program_124lhkT
    attributes: Classroom_123PYDST

Stratifier entity
    name
    program
    proportions

StratifierHistory entity, child of its Stratifier
    profile: {"classroom": "Classroom_123PYDST", "race": "white"}
    history: {"treatment": 13, "control": 12}

sent to /api/stratify:
    name: student_condition
    proportions: {"treatment": 1, "control": 1}
    study/program: Program_124lhkT
    attributes: Classroom_456

New StratifierHistory entity, child of its Stratifier
    profile: Classroom_456
    history: {"treatment": 1, "control": 0}

----

sent to /api/stratify:
    name: student_condition
    proportions: {"treatment": 1, "control": 1}
    study/program: Program_124lhkT
    attributes: Classroom_123PYDST

construct general stratifier key: name + program + proportions + attributes
construct condition key: [key] + "control"
construct condition key: [key] + "treatment"



for each shard key, count them
"""

"""Stratification Visualizer

Paste into the interactive console to use.
"""

from core import *
from api import Api
import collections
import textwrap

api = Api(User(user_type='god'))

name = 'student_condition'
program_id = 'Program_XYZ'
proportions = {"treatment": 1, "control": 1}

classrooms = ["Classroom_ABC",
              "Classroom_DEF",
              "Classroom_GHI",
              "Classroom_JKL",
              "Classroom_MNO"]

classroom_assignments = collections.defaultdict(list)
classroom_totals = collections.defaultdict(lambda: 0)
all_assignments = []
all_totals = {'treatment': 0, 'control': 0}
for x in range(1000):
    classroom = classrooms[x % 5]
    condition = api.stratify(program_id, name, proportions, {"classroom": classroom})
    condition_binary = '.' if condition == 'treatment' else ' '
    classroom_totals[classroom + condition] += 1
    all_totals[condition] += 1
    classroom_assignments[classroom].append(condition_binary)
    all_assignments.append(condition_binary)

print '\n'.join(textwrap.wrap(' '.join([str(a) for a in all_assignments]), 50))
print 'treatment: {}, control: {}'.format(
        all_totals['treatment'],
        all_totals['control'])
print '\n-----\n'
for c, d in classroom_assignments.items():
    print '\n' + c + '\n'
    print '\n'.join(textwrap.wrap(''.join([str(a) for a in d]), 50))
    print 'treatment: {}, control: {}'.format(
        classroom_totals[c + 'treatment'],
        classroom_totals[c + 'control'])

from google.appengine.ext import ndb
from sharding import GeneralCounterShard
ndb.delete_multi(GeneralCounterShard.query().iter(keys_only=True))
