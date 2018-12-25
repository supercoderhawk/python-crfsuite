# -*- coding: utf-8 -*-
from __future__ import absolute_import
import re

MAX_SEG_LEN = 'max_seg_len'
FORWARD_STATE = 'frw_state'
PREFIX = 'prefix'
SUFFIX = 'suffix'


class ParsedDump(object):
    """
    CRFsuite model parameters. Objects of this type are returned by
    :meth:`pycrfsuite.Tagger.info()` method.

    Attributes
    ----------

    transitions : dict
        ``{(from_label, to_label): weight}`` dict with learned transition weights

    state_features : dict
        ``{(attribute, label): weight}`` dict with learned ``(attribute, label)`` weights

    header : dict
        Metadata from the file header

    labels : dict
        ``{name: internal_id}`` dict with model labels

    attributes : dict
        ``{name: internal_id}`` dict with known attributes
    semi_markov: dict
        ``{}`` dict with

    """

    def __init__(self):
        self.header = {}
        self.labels = {}
        self.attributes = {}
        self.transitions = {}
        self.state_features = {}
        self.semi_markov = {MAX_SEG_LEN: {}, FORWARD_STATE: {}}
        self.error_lines = []


class CRFsuiteDumpParser(object):
    """
    A hack: parser for `crfsuite dump` results.

    Obtaining coefficients "the proper way" is quite hard otherwise
    because in CRFsuite they are hidden in private structures.
    """

    def __init__(self):
        self.state = None
        self.result = ParsedDump()

    def feed(self, line):
        # Strip initial ws and line terminator, but allow for ws at the end of feature names.
        line = line.lstrip().rstrip('\r\n')
        if not line:
            return

        m = re.match(r"(FILEHEADER|LABELS|ATTRIBUTES|TRANSITIONS|STATE_FEATURES|SEMI_MARKOV_MODEL) = {", line)
        if m:
            self.state = m.group(1)
        elif line == '}':
            self.state = None
        else:
            try:
                getattr(self, 'parse_%s' % self.state)(line)
            except Exception as e:
                self.result.error_lines.append(line)

    def parse_FILEHEADER(self, line):
        m = re.match("(\w+): (.*)", line)
        self.result.header[m.group(1)] = m.group(2)

    def parse_LABELS(self, line):
        m = re.match("(\d+): (.*)", line)
        self.result.labels[m.group(2)] = m.group(1)

    def parse_ATTRIBUTES(self, line):
        m = re.match("(\d+): (.*)", line)
        self.result.attributes[m.group(2)] = m.group(1)

    def parse_TRANSITIONS(self, line):
        m = re.match(r"\(\d+\) (.+) --> (.+): ([+-]?\d+\.\d+)", line)
        from_, to_ = m.group(1), m.group(2)
        assert from_ in self.result.labels
        assert to_ in self.result.labels
        self.result.transitions[(from_, to_)] = float(m.group(3))

    def parse_STATE_FEATURES(self, line):
        m = re.match(r"\(\d+\) (.+) --> (.+): ([+-]?\d+\.\d+)", line)
        attr, label = m.group(1), m.group(2)
        assert attr in self.result.attributes
        assert label in self.result.labels
        self.result.state_features[(attr, label)] = float(m.group(3))

    def parse_SEMI_MARKOV_MODEL(self, line):
        if line:
            if '[' not in line:
                key, value = line.split(' = ')
                self.result.semi_markov[key.strip()] = value.strip()
            else:
                if line.startswith(MAX_SEG_LEN):
                    _, seg_len = line.split(' = ')
                    seg_len = int(seg_len)
                    label = line[line.index('[') + 1:line.index(']')]
                    self.result.semi_markov[MAX_SEG_LEN][label] = seg_len
                elif line.startswith(FORWARD_STATE):
                    index = int(line[line.index('[') + 1:line.index(']')])
                    _, length = line[line.index('(') + 1:line.index(')')].split('=')
                    length = int(length)
                    labels = line[line.rindex('=') + 1:].strip().split('|')
                    self.result.semi_markov[FORWARD_STATE][index] = {'length': length, 'labels': labels,
                                                                     PREFIX: {}, SUFFIX: {}}
                elif line.startswith(PREFIX):
                    index = int(line[line.index('[') + 1:line.index(']')])
                    affix_index = int(line[line.rindex('[') + 1:line.rindex(']')])
                    prefix_states = line[:line.rindex('=') + 1:-1].strip().split('|')
                    prefix_state_item = {'state': prefix_states}
                    self.result.semi_markov[FORWARD_STATE][index][PREFIX][affix_index] = prefix_state_item
                elif line.startswith(SUFFIX):
                    index = int(line[line.index('[') + 1:line.index(']')])
                    affix_index = int(line[line.rindex('[') + 1:line.rindex(']')])
                    suffix_states = line[line.rindex(')') + 1:-1].strip().split('|')
                    transition_index = int(line[line.index('=') + 1:line.rindex('(')])
                    transition_position = int(line[line.rindex('=') + 1:line.rindex(')')])
                    suffix_item = {'state': suffix_states, 'transition_index': transition_index,
                                   'transition_position': transition_position}
                    self.result.semi_markov[FORWARD_STATE][index][SUFFIX][affix_index] = suffix_item
                else:
                    raise Exception('unknown parameter')
