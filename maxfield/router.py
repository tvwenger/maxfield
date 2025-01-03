#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - router.py

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2020 by
Trey Wenger; tvwenger@gmail.com

Maxfield is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Maxfield is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Maxfield.  If not, see <http://www.gnu.org/licenses/>.

Original concept by jpeterbaker
January 2020 - A complete re-write of original Ingress Maxfield.
"""

import itertools
import functools
import numpy as np
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2

# walking speed (m/s)
_WALKSPEED = 1

# Seconds required to communicated completed links. This can be
# completed while walking, but subsequent, dependent links can't be
# started until this is finished.
_COMMTIME = 30

# Seconds required to create a link
_LINKTIME = 30

def time_callback(origins_dists, count_cut_origins):
    """
    Creates a callback to get total time between two portals. The
    total time between nodes A and B is action(A) + travel(A, B).
    Ideally this would be a class function, but that doesn't work
    with functools.partial for some reason...

    Inputs:
      origins_dists :: (M, M) array of integers
        The distance (meters) between each unique origin portal.
        Includes dummy depot portal at node 0.
      count_cut_origins :: N-length list of integers
        The number of times this portal is used as an origin
        consequtively. Does not include dummy depot portal.

    Returns: time_evaluator
      time_evaluator :: reference to function time_evaluator()
    """

    def action_time(node):
        """
        Gets the action time at specified portal. The action time
        depends on the number of outgoing links.

        Inputs:
          node :: integer
            The portal under consideration.

        Returns:
          time :: integer
            The time (seconds) spent linking and communicating at this
            node
        """
        if node == 0:
            # skip dummy depot
            return 0
        # N.B. node i corresponds to index i-1 in
        # count_cut_origins, since count_cut_origins has no depot
        return count_cut_origins[node-1]*_LINKTIME

    def travel_time(from_node, to_node):
        """
        Determine the walking time between two portals.

        Inputs:
          from_index :: integer
            The first portal
          to_index :: integer
            The second portal

        Returns: time
          time :: integer
            The walking time between the two portals (seconds)
            """
        return origins_dists[from_node][to_node] / _WALKSPEED

    #
    # Pre-compute total time.
    #
    _total_time = {}
    for from_node in range(len(origins_dists)):
        _total_time[from_node] = {}
        for to_node in range(len(origins_dists)):
            _total_time[from_node][to_node] = \
                (action_time(from_node) +
                 travel_time(from_node, to_node))

    def time_evaluator(manager, from_index, to_index):
        """
        The callback, which returns the total time (action + travel)
        between two nodes.

        Inputs:
          from_index :: integer
            The first portal
          to_index :: integer
            The second portal

        Returns: time
          time :: integer
            The total time (seconds)
        """
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return _total_time[from_node][to_node]

    return time_evaluator

class Router:
    """
    The Router object uses a vehicle routing algorithm to determine
    the near-optimal agent assignments.
    """
    def __init__(self, graph, portals_dists, num_agents=1,
                 max_route_solutions=100, max_route_runtime=60):
        """
        Initialize a new Router object.

        Inputs:
          graph :: networkx.DiGraph object
            The graph for which we are generating link assignments
          portals_dists :: (N,N) array of scalars
            The spherical distance between each of the N portals
          num_agents :: integer
            The number of agents in this fielding operation
          max_route_solutions :: integer
            The maximum number of agent routing solutions to generate
            before choosing the best. Once max_route_solutions or
            max_route_runtime is reached, the best routing plan is
            selected.
          max_route_runtime :: integer
            The maximum runtime of the agent routing algorithm
            (seconds). Once max_route_solutions or max_route_runtime
            is reached, the best routing plan is selected.

        Returns: router
          router :: router.Router object
            A new Router object
        """
        self.graph = graph
        self.portals_dists = portals_dists
        self.num_agents = num_agents
        self.max_route_solutions = max_route_solutions
        self.max_route_runtime = max_route_runtime
        #
        # Get links and origins in order
        #
        link_orders = [self.graph.edges[link]['order']
                       for link in self.graph.edges]
        self.ordered_links = \
            [link for _, link in sorted(
                zip(link_orders, list(self.graph.edges)))]
        self.ordered_origins = \
            [link[0] for link in self.ordered_links]
        self.ordered_links_depends = [graph.edges[link]['depends'] for link in self.ordered_links]

    def route_agents(self):
        """
        Using vehicle routing algorithm to determine near-optimal
        agent assignments by minimizing the total build time.

        Inputs: Nothing

        Returns: assignments
          assignments :: list of dicts
            Each element is one assignment with keys
              'agent' : the agent number
              'location' : where they are
              'arrive' : when they arrived
              'link' : the portal to which they throw a link
              'depart' : when they leave
        """
        #
        # If num_agents is 1, then we have a trivial problem because
        # the order is already set
        #
        if self.num_agents == 1:
            assignments = []
            for i in range(len(self.ordered_links)):
                if i == 0:
                    arrive = 0
                else:
                    arrive = (depart +
                              self.portals_dists[
                                  self.ordered_links[i-1][0],
                                  self.ordered_links[i][0]
                              ]//_WALKSPEED)
                depart = arrive + _LINKTIME
                location = self.ordered_links[i][0]
                link = self.ordered_links[i][1]
                assignments.append(
                    {'agent':0, 'location':location, 'arrive':arrive,
                     'link':link, 'depart':depart})
            return assignments
        #
        # If the same origin appears multiple times sequentially, we
        # can remove the extras since the agent doesn't need to move.
        # Get that origin portal as well as the count of sequential
        # occurances
        #
        ordered_cut_origins, count_cut_origins = \
            zip(*[(x, len(list(y))) for x, y in
                  itertools.groupby(self.ordered_origins)])
        #
        # Create origins_dists matrix, which has the distances between
        # each origin portal in the correct order.
        #
        origins_dists = np.array([[self.portals_dists[o1][o2]
                                   for o1 in ordered_cut_origins]
                                  for o2 in ordered_cut_origins])
        #
        # Optimize the agent routes. This is a vehicle routing
        # problem, with the constraint that each portal must be
        # visited in order.
        #
        # Since our agents can start and end at any portal, we add a
        # "dummy node" to the first row and column of origins_dists
        # that has a distance 0 to every other portal. Too, we cast
        # the distances between portals to an integer, which shouldn't
        # cause any problems since most (all?) portals are separated
        # by at least 1 meter.
        #
        origins_dists = np.hstack(
            (np.zeros((origins_dists.shape[0], 1)), origins_dists))
        origins_dists = np.vstack(
            (np.zeros(origins_dists.shape[1]), origins_dists))
        origins_dists = np.array(origins_dists, dtype=int)
        #
        # Create the routing index manager
        # Set starting and ending locations to index 0 for the dummy
        # depot
        #
        manager = pywrapcp.RoutingIndexManager(
            len(origins_dists), self.num_agents, 0)
        #
        # Create the routing model
        #
        routing = pywrapcp.RoutingModel(manager)
        #
        # Set the time callback
        #
        time_callback_index = routing.RegisterTransitCallback(
            functools.partial(
                time_callback(origins_dists, count_cut_origins),
                manager))
        #
        # Set the cost function to minimize total time
        #
        routing.SetArcCostEvaluatorOfAllVehicles(time_callback_index)
        #
        # Add the total time as a dimension
        # 1000000 = can wait at each portal for a long time,
        # 1000000 = can take a long time to complete
        # False = do not start each agent at 0 time.
        #
        routing.AddDimension(time_callback_index, 1000000, 1000000,
                             False, 'time')
        time_dimension = routing.GetDimensionOrDie('time')
        time_dimension.SetGlobalSpanCostCoefficient(100)
        #
        # Force order. If any of the links in the next group depend
        # on any of the links in this group, then the next group can't
        # be started until this one is finished. Otherwise, they can
        # be built at the same time.
        #
        for i in range(1, len(origins_dists)-1):
            # N.B. node i corresponds to count_cut_origins[i-1] since
            # the later has no depot.
            this_index = manager.NodeToIndex(i)
            next_index = manager.NodeToIndex(i+1)
            #
            # Get dependencies
            #
            this_link = int(np.sum(count_cut_origins[:i-1]))
            this_size = count_cut_origins[i-1]
            next_link = int(np.sum(count_cut_origins[:i]))
            next_size = count_cut_origins[i]
            for linki in range(this_link, this_link+this_size):
                for linkj in range(next_link, next_link+next_size):
                    if ((self.ordered_links[linki] in
                         self.ordered_links_depends[linkj]) or
                        (self.ordered_links[linki][0] in
                         self.ordered_links_depends[linkj])):
                        # Dependency conflict
                        break
                else:
                    # No conflict yet
                    continue
                # Dependency conflict
                break
            else:
                # No conflict, so they can be started simultaneously
                routing.solver().Add(
                    (time_dimension.CumulVar(next_index) >=
                     time_dimension.CumulVar(this_index)))
                continue
            # is a conflict, so next has to be after this is finished
            # and communicated
            routing.solver().Add(
                (time_dimension.CumulVar(next_index) >
                 (time_dimension.CumulVar(this_index) + 
                  count_cut_origins[i-1]*_LINKTIME + _COMMTIME)))
        #
        # Start immediately, and we're trying to minimize total time.
        #
        for i in range(self.num_agents):
            time_dimension.CumulVar(routing.Start(i)).SetRange(0, 0)
            routing.AddVariableMinimizedByFinalizer(
                time_dimension.CumulVar(routing.End(i)))
        #
        # Set search parameters, then close the model
        #
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = \
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_parameters.local_search_metaheuristic = \
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_parameters.solution_limit = self.max_route_solutions
        search_parameters.time_limit.seconds = self.max_route_runtime
        #search_parameters.log_search = True
        routing.CloseModelWithParameters(search_parameters)
        #
        # A naive initial solution is that agents alternate portals
        #
        naive_route = [
            list(range(1, len(origins_dists)))[i::self.num_agents]
            for i in range(self.num_agents)]
        naive_solution = \
            routing.ReadAssignmentFromRoutes(naive_route, True)
        #
        # Solve with initial solution
        #
        solution = routing.SolveFromAssignmentWithParameters(
            naive_solution, search_parameters)
        if not solution:
            raise ValueError("No valid assignments found")
        #
        # Package results
        #
        assignments = []
        for agent in range(self.num_agents):
            #
            # Loop over all assignments, except first (dummy depot)
            #
            index = routing.Start(agent)
            index = solution.Value(routing.NextVar(index))
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                #
                # Get time agent arrives at this node
                #
                arrive = solution.Min(time_dimension.CumulVar(index))
                #
                # Node is index in origins_dists, which corresponds
                # to index-1 in ordered_cut_origins since
                # ordered_cut_origins doesn't have depot. This is
                # related to the index in ordered_links via
                #
                linki = int(np.sum(count_cut_origins[:node-1]))
                #
                # Loop over all links starting now at this origin
                #
                for i in range(linki, linki+count_cut_origins[node-1]):
                    #
                    # add link time. Final link at this origin
                    # includes communication time
                    #
                    location = self.ordered_links[i][0]
                    link = self.ordered_links[i][1]
                    depart = arrive + _LINKTIME
                    assignments.append({
                        'agent':agent, 'location':location,
                        'arrive':arrive, 'link':link,
                        'depart':depart})
                    arrive = depart
                #
                # Get next index and move on
                #
                index = solution.Value(routing.NextVar(index))
        #
        # Sort assignments by arrival time
        #
        assignments = sorted(assignments, key=lambda k: k['arrive'])
        return assignments
