#!/usr/bin/env

import time
from cfr import *
from random import random
import json

# DEFINE PARAMETERS AND TABLES #
CUMULATIVE_REGRETS = {} # dictionary of dictionaries
CUMULATIVE_STRATEGY = {} # dictionary of dictionaries
EPSILON = 0.05
TAU = 1000
BETA = 10
HAND_STRENGTH_ITERS = 1000
# END DEFS #


def writeCumulativeRegretsToFiles():
	with open('cumulativeRegrets.json', 'w') as f:
		json.dump(CUMULATIVE_REGRETS, f, indent=1)

def writeCumulativeStrategyToFiles():
	with open('cumulativeStrategy.json', 'w') as f:
		json.dump(CUMULATIVE_STRATEGY, f, indent=1)

def WalkTree(h, i, q):
	"""
	h: a History object
	i: the current player (information set will be from their perspective)
	q: the sample probability of getting to this node in the tree
	"""
	if h.NodeType == 2: # if h is terminal
		p1_utility, p2_utility = h.getTerminalUtilities() # returns (p1_util, p2_util)
		return p1_utility if i==0 else p2_utility

	elif h.NodeType == 0: # if h is a chance node
		newH = h.simulateChance()
		return WalkTree(newH, i, q)


	# get the information set for the current history and the player whose perspective we are using
	I = convertHtoI(h, i)

	# get the current regret matched strategy (normalize cumulative regrets)
	sigma = getCurrentRegretMatchedStrategy(I)

	else: # this must be an action node
		assert h.NodeType == 1, "Error: expected an action node!"

		# if it's an opponent action, sample from current regret matched strategy
		if h.ActivePlayer != i:

			# first, update the cumulative strategy
			updateCumulativeStrategy(I, sigma, q)

			# now sample an opponent action based on on the current regret matched strategy
			legalActions = h.getLegalActions()

			# replace annoying colons from the history (my fault)
			for i in range(len(legalActions)):
				legalActions[i]=legalActions[i].replace(":","")

			oppAction = chooseAction(sigma)

			assert (oppAction in legalActions), "Error: in walkTree, opp chose an action from sigma that is not allowed by history!"

			newH = h.simulateAction(oppAction)
			return WalkTree(newH, i, q)

		# if it's our action, use average strategy sampling to choose which actions to explore
		else:

			assert h.ActivePlayer==i, "Error: expected the active player to be the SAME as the expected player, got different."

			legalActions = h.getLegalActions()

			# replace annoying colons from the history
			for i in range(len(legalActions)):
				legalActions[i]=legalActions[i].replace(":","")

			# get the cumulative strategy for our current infoset
			s = getCumulativeStrategy(I) # ex. s = {action1:1.232 action2:17.384, action3:3.129 etc}

			# this will store the counterfactual value of each action
			actionValues = {}

			# sum up the items in s so that we can normalize them
			cumulativeStrategySum = 0
			actions = s.keys()
			for a in actions:
				values[a] = 0 #set the value of all actions to zero initially
				cumulativeStrategySum+=s[a]

			# go through each action, normalize and decide whether to sample
			for a in actions:
				# rho is the probability that an action is sampled
				# all actions get sampled with probability at least epsilon
				rho = max(EPSILON, float(s[a]) / cumulativeStrategySum)

				if random() < rho:
					newH = h.simulateAction(a)
					# determine the EV of taking action a by walking down that branch of the tree
					# q*min(1,rho) is the reach probability of the next node
					actionValues[a] = WalkTree(newH, i, q*min(1,rho))

			# determine the EV of the current regret-matched strategy (sigma)
			sigmaEV = 0
			for a in actions:
				sigmaEV += sigma[a] * actionValues[a]

			# UPDATE CUMULATIVE REGRETS
			for a in actions:
				# if the action had value greater than the EV of the current strategy, then we 'regret' not taking it!
				CUMULATIVE_REGRETS[I][a] += (values[a] - sigmaEV)

			# finally, return the EV of the current regret-matched strategy for the current infoset
			return sigmaEV

def getCumulativeStrategy(I, legalActions):
    """
    I (string): the information set that we want to look up the cumulative strategy for

    Gets cumulative strategy for information set I if it exists, else returns 0.
    """
    if I in CUMULATIVE_STRATEGY:
    	s = CUMULATIVE_STRATEGY[I]
    	assert len(legalActions)==len(s), "Error: number of actions in cumulative strategy lookup != that of legalActions!"
        return s
    else:
        print "Infoset ", I, " not in CUMULATIVE_STRATEGY, adding to dict, returning zeroes"
        s = {}
        for a in legalActions:
        	s[a] = 0

        # initialize a new entry in the cumulative strategy, with all zeroes
        CUMULATIVE_STRATEGY[I] = s
        return s


def updateCumulativeStrategy(I, action_dict, q):
    """
    Updates the cumulative strategy table for information set I by adding on latest strategy profile.
    I (string): the information set we're working with
    strategy: a strategy profile (list of weights associated with each action)
    """
    if I in CUMULATIVE_STRATEGY:
        assert len(CUMULATIVE_STRATEGY[I]) == len(action_dict), "ERROR: Tried to update cumulative strategy with wrong number of actions."

        # add the new set of strategy probabilities on to the cumulative strategy
        for a in action_dict.keys():
            CUMULATIVE_STRATEGY[I][a] += float(action_dict[a]) / q
    else:
        print "Information set ", I, " not found in cumulative strategy. Adding first strategy profile."
        for a in action_dict.keys():
            CUMULATIVE_STRATEGY[I][a] = float(action_dict[a]) / q


def getCumulativeRegrets(I, legalActions):
"""
I (string): the information set that we want to look up the cumulative regrets for

Gets cumulative regrets for information set I if they exist, else creates new entry of all zeroes.
"""
	if I in CUMULATIVE_REGRETS:
		R = CUMULATIVE_REGRETS[I]
		assert len(legalActions)==len(R), "Error: num. actions in cumulative regrets differs from num. legalActions!"
	    return R
	else:
	    print "Infoset ", I, " not in CUMULATIVE_REGRETS, creating entry with all zeroes" 

	    R = {}
	    for a in legalActions:
	    	R[a]=0

	    CUMULATIVE_REGRETS[I]=R
	    return R


def getCurrentRegretMatchedStrategy(I, legalActions):
    """
    I (string): the information set we want to get the CURRENT strategy for
    legalActions: a list of legal action strings

    If we haven't hit this information set before, strategy will be evenly distributed across all legal actions.
    Otherwise, do regret matching on cumulative regrets for this information set.
    """
    cumulativeRegrets = getCumulativeRegrets(I, legalActions) # a dictionary with action:regret pairs

    # sum up all of the entries
    # Note: if regrets are less than zero, just add zero on
    rsum = 0
    for r in cumulativeRegrets.itervalues():
    	rsum += r if r >= 0 else 0

    if rsum == 0: # this means we haven't hit this Infoset before, so assign a uniform strategy
    	for a in legalActions:
    		strategy[a] = 1.0 / len(legalActions)

    else: # do regret matching

        for a in legalActions:
        	# note: if negative regrets for an action, it is chosen with probability 0
        	strategy[a] = (cumulativeRegrets[a] / float(rsum)) if cumulativeRegrets[a]>0 else 0

    return strategy


def chooseAction(action_dict):
    """
    Chooses an action from a dict of action:prob pairs
    Tested with a million choices, is very close in practice to the profile given.
    """
    action_dict_sum = sum(action_dict.itervalues)
    assert (action_dict_sum < 1.03 and action_dict_sum > 0.97), "Error: Strategy profile probabilities do not add up to 1."

    random_float = random()
    cutoff = 0
    for a in range(len(strategy)):
        cutoff += action_dict[a]
        if random_float <= cutoff:
            return a

def runCFR():
	"""
	# DEFINE PARAMETERS AND TABLES #
	CUMULATIVE_REGRETS = {} # dictionary of dictionaries
	CUMULATIVE_STRATEGY = {} # dictionary of dictionaries
	EPSILON = 0.05
	TAU = 1000
	BETA = 10
	HAND_STRENGTH_ITERS = 1000
	# END DEFS #

	History Params: (history, node_type, current_street, current_round, button_player, dealer, \
                    active_player, pot, p1_inpot, p2_inpot, bank_1, bank_2, p1_hand, p2_hand, board)
	"""
	beginCFRTime = time.time()

	sbPlayer = 0
	treeWalkCounter = 0
	while continueCFR == True:

		try:
			initialDealer = Dealer()
			startHistory = History([], 0, 0, 0, sbPlayer, initialDealer, sbPlayer, 0, 0, 0, 200, 200, [], [], [])
		
			WalkTree(startHistory, 0, 1.0) # always go from P1 perspective, but alternate SB player every time
			treeWalkCounter += 1

			# alternate to the other sb player
			sbPlayer = (sbPlayer+1) % 2

			print "Tree Walk #:", treeWalkCounter
			print "Entries in CR:", len(CUMULATIVE_REGRETS)
			print "Entries in CS:", len(CUMULATIVE_STRATEGY)

			# every 100 walks, save to json file
			if treeWalkCounter % 100 == 0:
				writeCumulativeStrategyToFiles()
				writeCumulativeRegretsToFiles()

		except: # if there is an error, write everything to files
			writeCumulativeStrategyToFiles()
			writeCumulativeRegretsToFiles()


	endCFRTime = time.time()
	print "------------- ENDED CFR --------------"
	print "RAN CFR FOR:", endCFRTime-beginCFRTime, "secs"



if __name__ == '__main__':
	runCFR()
