# 26 Feb 2016 modified by Trey Wenger

# Introduction

This is for Ingress. If you don't know what that is, you're lost.

This code is designed to make a plan for linking a given set of portals in the
way (and the order) that creates the most fields. This is harder than it sounds.
If you're working on more than a dozen portals, learning to use this code may
be faster than planning by hand.

This code is used on the website http://www.ingress-maxfield.com


# Prerequisites

You'll need Python (I've got 2.7) as well as networkx, numpy, and matplotlib.

You can get these setup easily with the Enthought Python Distribution.

You can use pip to install the dependencies via:

    pip install -r requirements.txt

# Example

I'll be distributing this code with a file EXAMPLE.csv. Try running

    python makePlan.py -n 4 EXAMPLE.portals -d out/ -f output.pkl

This will put a bunch of files into the "out/" directory (see OUTPUT FILE LIST)

### OUTPUT FILE LIST

	keyPrep.txt
		List of portals, their numbers on the map, and how many keys are needed

	keys_for_agent_M_of_N.txt
		List of keys agent number M will need (if N agents are participating)

	links_for_agent_M_of_N.txt
		List of ALL the links
		Total distance traveled and AP earned by agent number M
			* Except for the links marked with a star (*), the links should be made IN THE ORDER LISTED
			* Links with a star can be made out of order, but only EARLY i.e. BEFORE their position in the list (this can save you time)
			* The links that agent number M makes are marked with underscores__
			* The first portal listed is the origin portal (where the agent must be)
			* The second portal listed is the destination portal (for which the agent must have a key)

	portalMap.png
		A map showing the locations of the portals
	linkMap.png
		A map showing the locations of portals and links
			* Up is north
			* Portal numbers increase from north to south
			* Portal numbers match "keyPrep.txt" and "linkes_for_agent_M_of_N.txt"
			* Link numbers match those in the link schedules "links_for_agent_M_of_N.txt"

	ownershipPrep.txt
		List of portals whose first link is incoming
			* These portals need to be captured and fully powered before the linking operation
		List of portals whose first link is outgoing
			* You may be able to save time by capturing and fully powering these portals DURING the linking operation

	lastPlan.pkl
		A Python pickle file containing all portal and plan information
			* The default name is "lastPlan.pkl"
			* In the examples above, this is called "output.pkl"

# Warranty

No promises

# Usage

    See

    python makePlay.py --help

# Portal list file format

  This file must be semi-colon delimited. Portal names must not
  contain a semi-colon. The first entry on the line must be the portal
  name. The next entries can be, in no particular order, the Intel map
  URL of the portal, the number of keys you or your team has for that
  portal, and the word SBLA if the portal holds a SoftBank Link
  Amp. If the number of keys are not included, I assume you have no
  keys. If you do not include SBLA, I assume there is not a SBLA on
  the portal. For example, each of the following are allowed:

 Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; 3; SBLA

 Catholic Church of the Holy Comforter; SBLA; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; 3

 Catholic Church of the Holy Comforter; 3; SBLA; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439

# Notes

The space of possible max-field plans is large. Rather than trying every
possibility, this program randomly tries some plans and presents you with one
that doesn't require you to walk too much.

If you don't like the plan you got, run it again. You'll probably get a
different plan.
