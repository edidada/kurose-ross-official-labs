from argparse import Namespace
from copy import deepcopy
import unittest
import rdtsim as rdt


class ReliableTransportTests(unittest.TestCase):
    def simulate(self, loss, corruption, seed, messages=200):
        delivered = []
        options = Namespace(num_msgs=messages, interarrival_time=0.5,
                            loss_prob=loss, corrupt_prob=corruption,
                            seqnum_limit=16 if seed % 2 else 2, random_seed=seed, trace=0)
        simulator = rdt.Simulator(options, cbB=delivered.append)
        rdt.the_sim = simulator
        simulator.run()
        # Original simulator ends when the last message is offered, not
        # delivered. Drain only its remaining channel/timer events; do not
        # fabricate ACKs, extend application traffic or modify the simulator.
        events = 0
        while simulator.event_list:
            event = simulator.event_list.pop(0)
            if event.ev_type == rdt.EventType.FROM_LAYER5:
                continue
            simulator.time = event.ev_time
            if event.ev_type == rdt.EventType.FROM_LAYER3:
                event.ev_entity.input(deepcopy(event.packet))
            else:
                event.ev_entity.timer_interrupt()
            events += 1
            self.assertLess(events, 100000, 'Protocol did not quiesce')
        self.assertEqual(delivered, [bytes([97+i % 26])*20 for i in range(messages)])
        self.assertIsNone(simulator.entity_A.pending)
        self.assertFalse(simulator.entity_A.queue)
        return simulator.get_stats()

    def test_original_network_simulator_matrix(self):
        for seed in range(12):
            for loss, corruption in ((0, 0), (0.25, 0), (0, 0.25), (0.3, 0.3), (0.6, 0.2)):
                with self.subTest(seed=seed, loss=loss, corruption=corruption):
                    stats = self.simulate(loss, corruption, seed)
                    if loss:
                        self.assertGreater(stats['n_lost'], 0)
                    if corruption:
                        self.assertGreater(stats['n_corrupt'], 0)

    def test_empty_and_many_wraps(self):
        self.simulate(0, 0, 50, messages=0)
        self.simulate(0.15, 0.15, 51, messages=1500)
