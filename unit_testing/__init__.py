"""Load all the files in this directory as modules.

http://stackoverflow.com/questions/1057431/loading-all-modules-in-a-folder-in-python
"""

import os
for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    __import__(module[:-3], locals(), globals())
del module
