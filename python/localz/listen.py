import os
import sys
import json
import time
import argparse
import threading
import collections

import pika
from rez.config import config

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count")
parser.add_argument("--file")
parser.add_argument("--save-interval", default=2, type=int)

opts = parser.parse_args()

# Dictionary with..
# - host: {
#   - user: [{
#     - qualifiedPackageName
#     - lastUsed
#     - firstUsed
#   }]
# }
history = collections.defaultdict(lambda: collections.defaultdict(dict))
state = {"updated": False, "running": True}

if opts.file:
    fname = os.path.expanduser(opts.file)
    fname = os.path.abspath(fname)
    fname = os.path.normpath(fname)

    try:
        with open(fname) as f:
            history = json.load(f)

    except OSError:
        # Clean slate
        pass


def update_db():
    """Update output every so often, but not on every message"""

    while True:
        if not state["running"]:
            break

        if state["updated"]:
            state["updated"] = False

            with open(fname, "w") as f:
                json.dump(history, f, indent=2, sort_keys=True)

            if opts.verbose:
                print("Updated '%s'" % opts.file)

        time.sleep(opts.save_interval)


def on_resolve(ch, method, properties, body):
    payload = json.loads(body)

    try:
        context = payload["context"]
    except KeyError:
        return sys.stderr.write(" [x] Unexpected message: %s\n" % body)

    host = history[payload["host"]]
    user = host[payload["user"]]

    for pkg in context["resolved_packages"]:
        name = "{name}-{version}".format(**pkg["variables"])
        timestamp = context["timestamp"]

        if name not in user:
            user[name] = {
                "firstUsed": timestamp,
            }

        user[name]["lastUsed"] = timestamp

    state["updated"] = True

    if not opts.file:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if opts.verbose:
        packages = history[payload["host"]][payload["user"]]
        for name, stats in packages.items():
            print("%s [%s, %s]" % (name,
                                   stats["firstUsed"],
                                   stats["lastUsed"]))
        print("")


host = config.context_tracking_host
param = pika.ConnectionParameters(host=host)
connection = pika.BlockingConnection(param)

channel = connection.channel()
channel.basic_consume(queue='myqueue',
                      on_message_callback=on_resolve,
                      auto_ack=True)


if opts.file:
    print(' [*] Saving messages to %s' % fname)
    thread = threading.Thread(target=update_db)
    thread.daemon = True
    thread.start()

try:
    print(' [*] Listening for context resolves @ %s' % host)
    channel.start_consuming()
except KeyboardInterrupt:
    state["running"] = False
    print("Graceful shutdown")
