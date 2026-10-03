import unittest
import curses
import questionnode
import database


nodes = {i: database.__dict__[i] for i in database.__dict__ if 
        isinstance(database.__dict__[i], questionnode.GameNode)}

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


class FakeWrong(object):
    """counts invalid-input events without touching curses"""

    def __init__(self):
        self.calls = 0

    def play(self, standardscreen, wrong, trick):
        self.calls += 1

    def reset(self):
        self.calls = 0


class FakeTrick(object):
    """records trick events and optionally forces a node jump"""

    def __init__(self, jump=None):
        self.tricks = ("pwd",)
        self.calls = []
        self.jump = jump

    def play(self, standardscreen, wrong, trick, answer):
        self.calls.append(answer)
        return self.jump


class FakeScreen(object):
    """minimal curses surface for handler rendering tests"""

    def clear(self):
        pass

    def refresh(self):
        pass

    def addstr(self, *args, **kwargs):
        pass

    def getch(self, *args):
        return 0

    def getmaxyx(self):
        return (24, 80)

    def getyx(self):
        return (0, 0)


class TestDatabase(unittest.TestCase):

    def test_every_module_node_is_registered_with_stable_id(self):
        db = database.db
        for name, node in nodes.items():
            self.assertEqual(node.idnum, name)
            self.assertIn(name, db)
            self.assertIs(db.get(name), node)

    def test_query_cache_refreshes_on_register(self):
        db = database.NodeDatabase()
        node = questionnode.GameNode(["q"], ["0 - a"])
        db.register("sample", node)
        self.assertIs(db.all_nodes()["sample"], node)
        replacement = questionnode.GameNode(["q2"], ["0 - b"])
        db.register("sample", replacement)
        self.assertIs(db.all_nodes()["sample"], replacement)
        self.assertIs(db.get("sample"), replacement)
        self.assertEqual(replacement.idnum, "sample")

    def test_database_persists_across_session_reset(self):
        db = database.db
        ids_before = set(db.all_nodes())
        session = questionnode.GameSession(
            database.opening, database.wrong, database.trick)
        session.reset()
        self.assertEqual(set(db.all_nodes()), ids_before)


class TestReachability(unittest.TestCase):

    def test_all_nodes_reachable_from_opening(self):
        db = database.db
        self.assertEqual(
            db.reachable_from("opening"), set(db.all_nodes()),
            "some question nodes are unreachable or missing targets")


class TestInputRecovery(unittest.TestCase):

    def test_invalid_answers_resolve_to_none(self):
        for name in ("opening", "one", "two", "ten6", "forty4"):
            node = database.db.get(name)
            for bad in ("", " ", "9", "99", "garbage", "0 1"):
                self.assertIsNone(
                    node.resolve(bad),
                    "%r unexpectedly resolved on node %s" % (bad, name))

    def test_valid_answers_resolve(self):
        self.assertIs(database.opening.resolve("0"), database.one)
        self.assertIs(database.opening.resolve("y"), database.one)
        self.assertIs(database.opening.resolve("yes"), database.one)
        self.assertIs(database.opening.resolve("1"), database.two)

    def test_invalid_input_reprompts_without_crash(self):
        node = database.opening
        scripted = iter(["9", "", "garbage", "0"])
        original = node.prompt_input
        node.prompt_input = lambda scr: next(scripted)
        fake_wrong = FakeWrong()
        try:
            nxt = node.play(None, fake_wrong, database.trick)
        finally:
            node.prompt_input = original
        self.assertIs(nxt, database.one)
        self.assertEqual(fake_wrong.calls, 3)

    def test_trick_input_handled_once_then_reprompts(self):
        node = database.opening
        scripted = iter(["pwd", "1"])
        original = node.prompt_input
        node.prompt_input = lambda scr: next(scripted)
        fake_trick = FakeTrick()
        try:
            nxt = node.play(None, database.wrong, fake_trick)
        finally:
            node.prompt_input = original
        self.assertIs(nxt, database.two)
        self.assertEqual(fake_trick.calls, ["pwd"])

    def test_trick_can_jump_to_another_node(self):
        node = database.opening
        original = node.prompt_input
        node.prompt_input = lambda scr: "pwd"
        fake_trick = FakeTrick(jump=database.seven)
        try:
            nxt = node.play(None, database.wrong, fake_trick)
        finally:
            node.prompt_input = original
        self.assertIs(nxt, database.seven)

    def test_real_trick_handler_ignores_unknown_input(self):
        self.assertIsNone(
            database.trick.play(
                None, database.wrong, database.trick, "xyzzy"))
        self.assertIsNone(
            database.trick.play(
                None, database.wrong, database.trick, ""))

    def test_sudo_has_full_handler_signature(self):
        saved = curses.has_colors
        curses.has_colors = lambda: False
        self.addCleanup(setattr, curses, "has_colors", saved)
        jump = database.trick.funcs["sudo"](
            FakeScreen(), database.wrong, database.trick, "sudo")
        self.assertIs(jump, database.seven)


class TestCleanSession(unittest.TestCase):

    def test_reset_restores_clean_state(self):
        database.wrong.wrong = 9
        database.wrong.eternity = 99
        questionnode.state = "dirty"
        session = questionnode.GameSession(
            database.opening, database.wrong, database.trick)
        session.reset()
        self.assertEqual(database.wrong.wrong, 0)
        self.assertEqual(database.wrong.eternity, 0)
        self.assertEqual(questionnode.state, "")

    def test_session_walks_tree_iteratively_and_terminates(self):
        first = questionnode.GameNode(["q"], ["0 - a"])
        second = questionnode.GameNode(["q"], ["0 - b"])
        first.answer_map = {"0": second}
        second.answer_map = {"0": ""}
        first.prompt_input = lambda scr: "0"
        second.prompt_input = lambda scr: "0"
        session = questionnode.GameSession(
            first, database.wrong, database.trick)
        end = session.run(None)
        self.assertEqual(end, "")
        self.assertIs(questionnode.state, second)


if __name__ == '__main__':
    unittest.main()
