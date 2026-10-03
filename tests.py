import unittest
from unittest import mock
import questionnode
import database


nodes = {i: database.__dict__[i] for i in database.__dict__ if 
        isinstance(database.__dict__[i], questionnode.GameNode)}


class FakeScreen(object):
    """minimal curses stand-in, feeds scripted inputs to the game"""

    def __init__(self, inputs=()):
        self.inputs = [i.encode("utf-8") if isinstance(i, str) else i
            for i in inputs]

    def clear(self):
        pass

    def addstr(self, *args):
        pass

    def refresh(self):
        pass

    def getmaxyx(self):
        return (24, 80)

    def getyx(self):
        return (0, 0)

    def getstr(self, *args):
        return self.inputs.pop(0)

    def getch(self, *args):
        return 0


def quiet_curses():
    """patches curses capability calls so tests run without a terminal"""
    return [mock.patch("curses.has_colors", return_value=False),
        mock.patch("curses.color_pair", return_value=0)]

class TestAnswers(unittest.TestCase):

    def test_all_answers_mapped(self):
        global nodes
        for node in nodes:
            try:
                self.assertLessEqual(len(nodes[node].options), 
                    len(nodes[node].answer_map), 
                    "node %s has %s options and %s map points" % 
                    (str(nodes[node].idnum), str(len(nodes[node].options)), 
                    str(len(nodes[node].answer_map))))
            except AttributeError:
                self.assertEqual(len(nodes[node].answer_map), 1,
                "node %s has no options and %s map points" % 
                (str(nodes[node].idnum), str(len(nodes[node].answer_map))))

    def test_all_maps_valid(self):
        global nodes
        node_ids = [nodes[node].idnum for node in nodes]
        node_ids.append("")
        for node in nodes:
            for map_point in nodes[node].answer_map:
                self.assertIn(nodes[node].answer_map[map_point], node_ids, 
                "node %s has an invalid map point")

class TestDatabase(unittest.TestCase):

    def setUp(self):
        questionnode.reset_session(database.wrong)

    def test_registry_persists_all_nodes(self):
        for name in nodes:
            node = nodes[name]
            self.assertIs(questionnode.get_node(node.idnum), node,
                "node %s is not persisted in the registry" % node.idnum)

    def test_all_map_points_resolve(self):
        for name in nodes:
            for map_point in nodes[name].answer_map.values():
                resolved = questionnode.get_node(map_point)
                self.assertIsInstance(resolved, questionnode.GameNode,
                    "node %s maps to missing node %s" % 
                    (nodes[name].idnum, map_point))

    def test_query_cache_updates_on_register(self):
        first = questionnode.GameNode(["q"], ["0 - a"])
        first.idnum = "cache_test"
        second = questionnode.GameNode(["q"], ["0 - a"])
        second.idnum = "cache_test"
        try:
            questionnode.register_node(first)
            self.assertIs(questionnode.get_node("cache_test"), first)
            questionnode.register_node(second)
            self.assertIs(questionnode.get_node("cache_test"), second,
                "query cache was not updated on re-register")
        finally:
            questionnode.node_registry.pop("cache_test", None)
            questionnode._query_cache.pop("cache_test", None)

    def test_all_nodes_reachable(self):
        seen = set()
        stack = [questionnode.get_node(i) for i in 
            ("opening", "trick", "wrong")]
        while stack:
            node = stack.pop()
            if node.idnum in seen:
                continue
            seen.add(node.idnum)
            for map_point in node.answer_map.values():
                if map_point:
                    stack.append(questionnode.get_node(map_point))
        for name in nodes:
            self.assertIn(nodes[name].idnum, seen,
                "node %s is unreachable" % nodes[name].idnum)

class TestInputHandling(unittest.TestCase):

    def setUp(self):
        questionnode.reset_session(database.wrong)
        self.patches = quiet_curses()
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        questionnode.reset_session(database.wrong)

    def test_invalid_input_recovers(self):
        screen = FakeScreen(["garbage", "0"])
        nxt = database.opening.advance(screen, database.wrong, database.trick)
        self.assertIs(nxt, database.one)
        self.assertEqual(database.wrong.wrong, 1,
            "one invalid input should trigger exactly one error event")

    def test_trick_statement_reprompts(self):
        screen = FakeScreen(["whoami", "0"])
        nxt = database.opening.advance(screen, database.wrong, database.trick)
        self.assertIs(nxt, database.one)

    def test_trick_func_does_not_crash(self):
        screen = FakeScreen(["sudo"])
        nxt = database.opening.advance(screen, database.wrong, database.trick)
        self.assertIs(nxt, database.seven)

    def test_no_answer_node_advances(self):
        screen = FakeScreen()
        nxt = database.three.advance(screen, database.wrong, database.trick)
        self.assertIs(nxt, database.eight)

    def test_play_walks_tree_iteratively(self):
        screen = FakeScreen(["0", "0"])
        with mock.patch.object(questionnode, "get_node",
                side_effect=[database.one, None]):
            database.opening.play(screen, database.wrong, database.trick)
        self.assertEqual(questionnode.state, "one")

class TestSessionState(unittest.TestCase):

    def test_session_starts_clean(self):
        database.wrong.wrong = 5
        database.wrong.eternity = 9
        questionnode.state = "sixty"
        questionnode.reset_session(database.wrong)
        self.assertEqual(database.wrong.wrong, 0)
        self.assertEqual(database.wrong.eternity, 0)
        self.assertEqual(questionnode.state, "")

if __name__ == '__main__':
    unittest.main()
