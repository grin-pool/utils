#!/usr/bin/python

# Copyright 2018 Blade M. Doyle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ------------------------------------------------------------------------

###
# Estmate MWGrinPool earnings from historic data
# Input: --days, --c29gps, --c31gps

# Algorithm:
#   Get a list of the blocks found by MWGrinPool within the requested block range
#   For each pool-found-block:
#       Calculate the theoritical rewards for a user with provided GPS
#   Generate a graph

import os
import sys
import argparse
import requests
from datetime import datetime

mwURL = "https://api.mwgrinpool.com"
NanoGrin = 1.0/1000000000.0

def print_header():
    print(" ")
    print("############# MWGrinPool Average Daily Earnings #############")
    print("## ")

def print_footer(rewardTotal):
    print(" ")
    print("## Total Rewards: {} Grin".format(rewardTotal))
    print("## Avg Daily Reward = {}".format(rewardTotal/NumDays))

parser = argparse.ArgumentParser()
parser.add_argument("--days", help="Number of days to average over")
parser.add_argument("--c29gps", help="Miners C29 Graphs/second")
parser.add_argument("--c31gps", help="Miners C31 Graphs/second")
args = parser.parse_args()


print_header()

if args.days is None:
    NumDays = input("   Number of days to average over: ")
else:
    NumDays = args.days

if NumDays > 31:
    print(" ")
    print("   -- Error: Please limit your query to 31 days to prevent excess load on our pool API")
    print(" ")
    sys.exit(1)

if args.c29gps is None:
    C29Gps = input("   Miners C29 Graphs/second: ")
else:
    C29Gps = args.c29gps

if args.c31gps is None:
    C31Gps = input("   Miners C31 Graphs/second: ")
else:
    C31Gps = args.c31gps


# Get current height and caclculate start and end blocks
heightURL = mwURL + "/grin/block/height"
grinHeight = requests.get(url = heightURL).json()
EndBlock   = grinHeight['height']
StartBlock = EndBlock - (1440 * NumDays)

# Get a list of the pool-found-blocks within the range
poolblocksURL = mwURL + "/pool/blocks/0,1440/height"
poolblocksJSON = requests.get(url = poolblocksURL).json()
poolblocks = [block['height'] for block in poolblocksJSON if (block['height'] >= StartBlock and block['height'] <= EndBlock)]
poolblocks.sort()

print(" ")
print("   Getting Mining Data: ")
miningData = []
rewardTotal = 0
for blockHeight in poolblocks:
    # For each pool block, get some information:
    #   Secondary Scale Value
    #   Any TX fees included in the block reward
    grinBlockURL = mwURL + "/grin/block/{}/height,secondary_scaling,fee".format(blockHeight)
    grinblockJSON = requests.get(url = grinBlockURL).json()
    #   Pool GPS at that block height
    poolGpsURL = mwURL + "/pool/stat/{}/gps".format(blockHeight)
    poolGpsJSON = requests.get(url = poolGpsURL).json()
    #   Calculate theoretical miners reward
    scale = (2**(1+31-24)*31)/float(max(29, grinblockJSON['secondary_scaling']))
    minerValue = C29Gps + C31Gps*scale
    poolValue = 0
    for gps in poolGpsJSON['gps']:
        if gps['edge_bits'] == 29:
            poolValue += gps['gps']
        else:
            poolValue += gps['gps']*scale
    minersReward = (minerValue/poolValue*60)+(grinblockJSON['fee']*NanoGrin)
    print("   + Miners reward for block {}: {}".format(blockHeight, minersReward))
    rewardTotal += minersReward

print_footer(rewardTotal)
