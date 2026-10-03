# coding: utf-8

import curses
from parts import everyword
import time
import random
import os


#global state variable is used to track game state for meta-game functions like
#rpg and command line tricks
state = ""

#node registry is the query layer for the node "database": nodes are stored
#by idnum and looked up when walking the choice tree
node_registry = {}
_query_cache = {}

def register_node(node):
    """stores a node by idnum and keeps the query cache in sync"""
    node_registry[node.idnum] = node
    _query_cache[node.idnum] = node

def get_node(idnum):
    """resolves an idnum to its node, caching query results"""
    try:
        return _query_cache[idnum]
    except KeyError:
        node = node_registry[idnum]
        _query_cache[idnum] = node
        return node

def reset_session(wrong_handler=None):
    """resets all mutable session state so each session starts clean"""
    global state
    state = ""
    if wrong_handler is not None:
        wrong_handler.reset()

class GameNode(object):
    #game node object, contains text and major behaviours

    def __init__(self, query, options):
        self.query = query
        self.options = options
        self.idnum = ""
        self.answer_map = {}

    def text_wrapping(self, word, standardscreen):
        """simple textwrapper, check how much space is left on the x-axis  
        if a word's length is longer than the remaining space, adds a newline"""
        maxx = standardscreen.getmaxyx()[1] - standardscreen.getyx()[1]
        word = " " + word
        if len(word) + 1 > maxx:
            standardscreen.addstr("\n")
        return word
            
    def pretty_printing(self, text, standardscreen):
        """splits text, a string, into a list of strings, checks dicts for them, 
        and changes print colour accordingly"""
        words = text.split(" ")
        for i in words:
            i = self.text_wrapping(i, standardscreen)
            begin = self.begin_punc_check(i)
            end = self.safe_end_punc(i)
            standardscreen.addstr(i[:begin])
            self.colour_lookup(i[begin:end[0]], standardscreen)
            standardscreen.addstr(i[end[1]:])
        standardscreen.refresh()

    def end_punc_check(self, word):
        """check end of word and count punctuation"""
        if word[-1:] in ["'", ".", "!", ":", ";", ")", ",", "(", "?", "-"]:
            return self.end_punc_check(word[:-1]) -1
        return 0

    def safe_end_punc(self, word):
        """corrects end_punc_check for weird string slicing behaviour"""
        count = self.end_punc_check(word)
        if count == 0:
            return (None,len(word))
        else:
            return (count,count)

    def begin_punc_check(self, word):
        """check beginning of word and counts punctuation"""
        if word[:1] in ["'", ".", "!", ":", ";", ")", ",", "(", "?", "-"]:
            return self.begin_punc_check(word[1:]) +1
        return 0

    def colour_lookup(self, word, standardscreen):
        """goes against a nltk dictionary to get part of speech and change
        colour accordingly"""
        if curses.has_colors():
            try:
                part = everyword[word.strip(" ")]
                if part in ["WP", "WRB", "TO", "CC", "EX", "WDT"]:
                    standardscreen.addstr(word, curses.color_pair(1))
                if part in ["NN", "NNS", "NNP"]:
                    standardscreen.addstr(word, curses.color_pair(2))
                if part in ["JJ", "DT", "JJR", "JJS"]:
                    standardscreen.addstr(word, curses.color_pair(3))
                if part in ["VBD", "VBG", "VBZ", "VB", "VBP", "VBN"]:
                    standardscreen.addstr(word, curses.color_pair(4))
                if part in ["RB", "RP", "MD"]:
                    standardscreen.addstr(word, curses.color_pair(5))
                if part in ["PRP", "IN", "PRP$"]:
                    standardscreen.addstr(word, curses.color_pair(6))
                if part in ["LS", "CD", "POS", "$", "-NONE-"]:
                    standardscreen.addstr(word)
            except KeyError:
                standardscreen.addstr(word)
        else:
            standardscreen.addstr(word)


    def play(self, standardscreen, wrong, trick):
        """main game loop, walks the choice tree iteratively so long
        sessions and repeated choices cannot grow the call stack"""
        global state
        node = self
        while node is not None:
            state = node.idnum
            node = node.advance(standardscreen, wrong, trick)

    def advance(self, standardscreen, wrong, trick):
        """prompts until a valid answer is entered, then returns the next
        node; invalid input is handled and re-prompted, never crashes"""
        answer = self.prompt_input(standardscreen)
        while answer not in self.answer_map:
            if answer.startswith(trick.tricks):
                jump = trick.play(standardscreen, wrong, trick, answer)
                if jump is not None:
                    return get_node(jump)
            else:
                wrong.play(standardscreen, wrong, trick)
            answer = self.prompt_input(standardscreen)
        return get_node(self.answer_map[answer])

    def prompt_input(self, standardscreen):
        """prints the query and options using pretty printing methods, and 
        prompts for user input"""
        standardscreen.clear()
        standardscreen.addstr("\n")
        for i in self.query:
            self.pretty_printing(i, standardscreen)
            standardscreen.addstr("\n\n     ")
        for i in self.options:
            self.pretty_printing(i, standardscreen)
            standardscreen.addstr("\n     ")
        standardscreen.addstr(standardscreen.getmaxyx()[0]-2,5,"$ ")
        answer = standardscreen.getstr(
            standardscreen.getmaxyx()[0]-2,7).decode(encoding = "utf-8")
        standardscreen.refresh()
        return answer

class NoAnswerNode(GameNode):
    def __init__(self, query):
        self.query = query
        self.idnum = ""
        self.answer_map = {}

    def advance(self, standardscreen, wrong, trick):
        """displays text and returns next node"""
        standardscreen.clear()
        standardscreen.addstr("\n")
        for i in self.query:
            self.pretty_printing(i, standardscreen)
            standardscreen.addstr("\n\n     ")
        answer = standardscreen.getch(
            standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return get_node(self.answer_map["0"])

class GameEnd(GameNode):
    def advance(self, standardscreen, wrong, trick):
        """prints errors if there are any remaining errors, and asks the final
        ending question"""
        while wrong.eternity < 17:
            wrong.play(standardscreen, wrong, trick)
        else:
            answer = self.prompt_input(standardscreen)
            while answer not in ["0", "1"]:
                answer = self.prompt_input(standardscreen)
            else:
                if answer == "0":
                    while True:
                        wrong.play(standardscreen, wrong, trick)
                else:
                    wrong.glitch_out(standardscreen)
                    wrong.spasm(standardscreen)


class WrongAnswerHandler(GameNode):
    def __init__(self, errors, glitch):
        self.errors = errors
        self.glitch = glitch
        self.idnum = ""
        self.answer_map = {}
        self.wrong = 0
        self.eternity = 0

    def reset(self):
        """restores clean session state"""
        self.wrong = 0
        self.eternity = 0

    def play(self, standardscreen, wrong, trick):
        """prints error message if there are any remaining, and if not, prints
        an incrementing counter"""
        if self.wrong < len(self.errors):
            standardscreen.clear()
            standardscreen.addstr("\n ERR: Unidentified Error\n\n",
                curses.color_pair(1))
            self.pretty_printing(self.errors[self.wrong], standardscreen)
            self.wrong += 1
            standardscreen.refresh()
            hang = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        else:
            standardscreen.clear()
            standardscreen.addstr("\n ERR: Unidentified Error\n\n",
                curses.color_pair(1))
            standardscreen.addstr("     " + str(self.eternity))
            self.eternity += 1
            hang = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)

    def spasm(self, standardscreen):
        """calls recursive loop until throws maximum recursion depth error"""
        standardscreen.clear()
        standardscreen.addstr("\n ERR: Unidentified Error\n\n",
            curses.color_pair(1))
        standardscreen.addstr("     " + str(self.eternity))
        self.eternity += 1
        self.spasm(standardscreen)

    def indentation_manager(self, standardscreen):
        pass


    def glitch_out(self, standardscreen):
        standardscreen.clear()
        standardscreen.addstr("\n ERR: Unidentified Error\n\n",
            curses.color_pair(1))
        standardscreen.addstr("     " + str(self.eternity))
        plain = []
        probability = [1]
        for i in range(40):
            probability.append(0)
        for char in self.glitch:
             plain.append(char)
             if standardscreen.getyx()[1]+1 >= standardscreen.getmaxyx()[1]-5:
                 standardscreen.addstr(" \n     ")
             else:
                 standardscreen.addstr(char)
        standardscreen.refresh()
        time.sleep(.5)
        for i in range(400):
            standardscreen.clear()
            standardscreen.addstr("\n ERR: Unidentified Error\n\n     ",
                curses.color_pair(1))
            if i % 10 == 0:
                probability.pop()
            for char in self.glitch:
                if random.choice(probability) == 0:
                    if standardscreen.getyx()[1]+3 >= standardscreen.getmaxyx(
                            )[1]-5:
                        standardscreen.addstr(" \n     ")
                    else:
                        standardscreen.addstr(char)
                else:
                    if standardscreen.getyx()[1]+3 >= standardscreen.getmaxyx(
                            )[1]-5:
                        standardscreen.addstr(" \n     ")
                    else:
                        standardscreen.addstr(char, curses.color_pair(2))
                standardscreen.refresh()
            time.sleep(.01)

class TrickHandler(GameNode):
    """There are two types of tricks - statements and funcs. Statements print a 
    response to the user, funcs contain some independent logic."""

    def __init__(self, statements):
        """statements is a dict of all statements, funcs a dict of all funcs,
        tricks is a tuple of all statement + func names"""
        self.statements = statements
        self.idnum = ""
        self.funcs = {"pwd": self.pwd, "ls": self.ls, 
            "kill": self.kill, "logout": self.logout, "echo": self.echo, "sudo":
            self.sudo}
        self.tricks = self.tuple_constructor()
        self.answer_map = {}

    def play(self, standardscreen, wrong, trick, answer):
        """checks entered string against all possible trick keywords, using 
        startswith, and if a match is found, forwards it to the statement
        handler or calls the associated func. Returns an idnum to jump to,
        or None to re-prompt the current node"""
        key = None
        for i in self.tricks:
            if answer.startswith(i):
                key = i
        if key is None:
            return None
        if key in self.statements:
            self.statement_handler(standardscreen, key)
            return None
        return self.funcs[key](standardscreen, wrong, trick, answer)

    def tuple_constructor(self):
        """creates a tuple of all the possible tricks, both funcs and 
        statements"""
        all_tricks = [i for i in self.statements] + [i for i in 
            self.funcs]
        return tuple(all_tricks)

    def statement_handler(self, standardscreen, answer):
        """prints tricks; the main loop then re-prompts the current node"""
        standardscreen.clear()
        standardscreen.addstr("\n")
        self.pretty_printing(self.statements[answer], standardscreen)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()

    def pwd(self, standardscreen, wrong, trick, answer):
        home = os.getcwd()
        standardscreen.clear()
        standardscreen.addstr("\n     " + home)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return None

    def sudo(self, standardscreen, wrong, trick, answer):
        lol = "You think you're clever but really you're a rock"
        standardscreen.clear()
        standardscreen.addstr("\n")
        self.pretty_printing(lol, standardscreen)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return self.answer_map["0"]

    def ls(self, standardscreen, wrong, trick, answer):
        files = os.listdir(os.getcwd())
        standardscreen.clear()
        for f in files:
            standardscreen.addstr("\n     " + f)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return None

    def kill(self, standardscreen, wrong, trick, answer):
        kill = ("Maybe I underestimated you. You seem to have learned how" 
                " things work very quickly. Maybe too quickly.\n\n     Of " 
                "course you would have this power.")
        standardscreen.clear()
        standardscreen.addstr("\n")
        self.pretty_printing(kill, standardscreen)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return self.answer_map["0"]

    def logout(self, standardscreen, wrong, trick, answer):
        standardscreen.clear()
        return self.answer_map["0"]

    def echo(self, standardscreen, wrong, trick, answer):
        reply = ("You call is echoed by the space around you, but it's "
                "impossible to get a sense of its dimensions. You are alone. "
                "No one hears you.")
        standardscreen.clear()
        standardscreen.addstr("\n")
        self.pretty_printing("'"+answer[5:]+"'", standardscreen)
        standardscreen.addstr("\n\n     ")
        self.pretty_printing(reply, standardscreen)
        answer = standardscreen.getch(standardscreen.getmaxyx()[0]-2,5)
        standardscreen.refresh()
        return None



