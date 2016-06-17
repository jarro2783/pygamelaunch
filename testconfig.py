#!/usr/bin/python

import yaml
from pprint import pprint
from sys import argv

def load(config):
    f = open(config)
    return yaml.load(f)

def pretty(y):
    pprint(y, indent=4)

if __name__ == "__main__":
    pretty(load(argv[1]))
