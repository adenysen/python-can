#!/usr/bin/env python
# coding: utf-8

"""
This module tests cyclic send tasks.
"""

from __future__ import absolute_import

from time import sleep
import unittest

import can

from .config import *
from .message_helper import ComparingMessagesTestCase


class SimpleCyclicSendTaskTest(unittest.TestCase, ComparingMessagesTestCase):

    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        ComparingMessagesTestCase.__init__(self, allowed_timestamp_delta=None, preserves_channel=True)

    @unittest.skipIf(IS_CI, "the timing sensitive behaviour cannot be reproduced reliably on a CI server")
    def test_cycle_time(self):
        msg = can.Message(is_extended_id=False, arbitration_id=0x123, data=[0,1,2,3,4,5,6,7])
        bus1 = can.interface.Bus(bustype='virtual')
        bus2 = can.interface.Bus(bustype='virtual')
        task = bus1.send_periodic(msg, 0.01, 1)
        self.assertIsInstance(task, can.broadcastmanager.CyclicSendTaskABC)

        sleep(2)
        size = bus2.queue.qsize()
        # About 100 messages should have been transmitted
        self.assertTrue(80 <= size <= 120,
                        '100 +/- 20 messages should have been transmitted. But queue contained {}'.format(size))
        last_msg = bus2.recv()
        self.assertMessageEqual(last_msg, msg)

        bus1.shutdown()
        bus2.shutdown()


    def test_removing_bus_tasks(self):
        bus = can.interface.Bus(bustype='virtual')
        tasks = []
        for task_i in range(10):
            msg = can.Message(is_extended_id=False, arbitration_id=0x123, data=[0, 1, 2, 3, 4, 5, 6, 7])
            msg.arbitration_id = task_i
            task = bus.send_periodic(msg, 0.1, 1)
            tasks.append(task)
            self.assertIsInstance(task, can.broadcastmanager.CyclicSendTaskABC)

        assert len(bus._periodic_tasks) == 10

        for task in tasks:
            # Note calling task.stop will remove the task from the Bus's internal task management list
            task.stop()

        assert len(bus._periodic_tasks) == 0
        bus.shutdown()

    def test_managed_tasks(self):
        bus = can.interface.Bus(bustype='virtual', receive_own_messages=True)
        tasks = []
        for task_i in range(3):
            msg = can.Message(is_extended_id=False, arbitration_id=0x123, data=[0, 1, 2, 3, 4, 5, 6, 7])
            msg.arbitration_id = task_i
            task = bus.send_periodic(msg, 0.1, 10, store_task=False)
            tasks.append(task)
            self.assertIsInstance(task, can.broadcastmanager.CyclicSendTaskABC)

        assert len(bus._periodic_tasks) == 0

        # Self managed tasks should still be sending messages
        for _ in range(50):
            received_msg = bus.recv(timeout=5.0)
            assert received_msg is not None
            assert received_msg.arbitration_id in {0, 1, 2}

        for task in tasks:
            task.stop()

        for task in tasks:
            assert task.thread.join(5.0) is None, "Task didn't stop before timeout"

        bus.shutdown()

    def test_stopping_perodic_tasks(self):
        bus = can.interface.Bus(bustype='virtual')
        tasks = []
        for task_i in range(10):
            msg = can.Message(is_extended_id=False, arbitration_id=0x123, data=[0, 1, 2, 3, 4, 5, 6, 7])
            msg.arbitration_id = task_i
            task = bus.send_periodic(msg, 0.1, 1)
            tasks.append(task)

        assert len(bus._periodic_tasks) == 10
        # stop half the tasks using the task object
        for task in tasks[::2]:
            task.stop()

        assert len(bus._periodic_tasks) == 5

        # stop the other half using the bus api
        bus.stop_all_periodic_tasks(remove_tasks=False)

        for task in tasks:
            assert task.thread.join(5.0) is None, "Task didn't stop before timeout"

        # Tasks stopped via `stop_all_periodic_tasks` with remove_tasks=False should
        # still be associated with the bus (e.g. for restarting)
        assert len(bus._periodic_tasks) == 5

        bus.shutdown()


if __name__ == '__main__':
    unittest.main()
