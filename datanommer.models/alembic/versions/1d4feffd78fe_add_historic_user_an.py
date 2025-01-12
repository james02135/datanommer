# This file is a part of datanommer, a message sink for fedmsg.
# Copyright (C) 2014, Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
""" Add historic user and package relationships.

This is pretty much for messages that occur *before* February, 2013.

Revision ID: 1d4feffd78fe
Revises: 5091535d0fb4
Create Date: 2013-04-12 13:00:46.452867

"""

import random

import fedmsg.config
from alembic import context, op
from fedmsg.meta import make_processors, msg2packages, msg2usernames

import datanommer.models as m


# revision identifiers, used by Alembic.
revision = "1d4feffd78fe"
down_revision = "5091535d0fb4"


def _page(q, chunk=1000):
    """Quick utility to page a query, 1000 items at a time.
    We need this so we don't OOM (out of memory) ourselves loading the world.
    """

    offset = 0
    while True:
        r = False
        for elem in q.limit(chunk).offset(offset):
            r = True
            yield elem
        offset += chunk
        if not r:
            break


def upgrade():
    """This takes a *really* long time.  Like, hours."""

    config_paths = context.config.get_main_option("fedmsg_config_dir")
    filenames = fedmsg.config._gather_configs_in(config_paths)

    config = fedmsg.config.load_config(filenames=filenames)

    make_processors(**config)

    engine = op.get_bind().engine
    m.init(engine=engine)
    for msg in _page(m.Message.query.order_by(m.Message.timestamp)):
        print(f"processing {msg.timestamp} {msg.topic}")

        if msg.users and msg.packages:
            continue

        changed = False

        if not msg.users:
            new_usernames = msg2usernames(msg.__json__(), **config)
            print("Updating users to %r" % new_usernames)
            changed = changed or new_usernames
            for new_username in new_usernames:
                new_user = m.User.get_or_create(new_username)
                msg.users.append(new_user)

        if not msg.packages:
            new_packagenames = msg2packages(msg.__json__(), **config)
            print("Updating packages to %r" % new_packagenames)
            changed = changed or new_usernames
            for new_packagename in new_packagenames:
                new_package = m.Package.get_or_create(new_packagename)
                msg.packages.append(new_package)

        if changed and random.random() < 0.01:
            # Only save if something changed.. and only do it every so often.
            # We do this so that if we crash, we can kind of pick up where
            # we left off.  But if we do it on every change: too slow.
            print(" * Saving!")
            m.session.commit()

    m.session.commit()


def downgrade():
    pass
