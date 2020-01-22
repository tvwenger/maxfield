#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - reorder.py

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

import numpy as np
from .field import can_add_outbound

def reorder_links_origin(graph):
    """
    Re-order links in this graph to minimize build time.
    Links that do not complete fields may be built earlier.
    Attempt to move those links earlier in the order, such that
    they are made with another link at the same origin portal. If
    there are no earlier links with the same origin but the link is
    reversible, try reversing the direction and finding an earlier
    origin portal. Update the order in the graph.

    Inputs:
      graph :: nextworkx graph object
        The graph for this plan

    Returns: Nothing
    """
    #
    # Get links in order
    #
    link_orders = [graph.edges[link]['order'] for link in graph.edges]
    ordered_links = [link for _, link in sorted(zip(link_orders, list(graph.edges)))]
    #
    # Move links that do not complete fields closer to another
    # link from the same origin portal
    #
    for i, link in enumerate(ordered_links):
        if graph.edges[link]['fields']:
            # this link completes a field
            continue
        #
        # Find the first time this portal is used as an origin for
        # another link
        #
        first = [j for j in range(len(ordered_links))
                 if ordered_links[j][0] == link[0]][0]
        #
        # If the first time happens before our current place in the
        # order, then re-order such that this link happens then
        #
        if first < i:
            ordered_links.insert(first, ordered_links.pop(i))
        elif graph.edges[link]['reversible']:
            #
            # If the link is reversible, see if we can improve things
            # by reversing the link direction
            #
            first = [j for j in range(len(ordered_links))
                     if ordered_links[j][0] == link[1]]
            #
            # first may be empty if there are no portals with this
            # origin
            #
            if (first and first[0] < i and
                can_add_outbound(graph, link[1])):
                #
                # Add reversed link with the same properties, remove
                # old edge, then move it
                #
                graph.add_edge(link[1], link[0], **graph.edges[link])
                graph.remove_edge(link[0], link[1])
                ordered_links[i] = (link[1], link[0])
                ordered_links.insert(first[0], ordered_links.pop(i))
    #
    # Update order in graph
    #
    for order, link in enumerate(ordered_links):
        graph.edges[link]['order'] = order

def get_path_length(graph, portals_dists):
    """
    Return the total walking distance required to complete all
    links in the graph.

    Inputs:
      graph :: nextworkx graph object
        The graph for this plan
      portals_dists :: (N,N) array of integers
        The spherical distance between each of the N portals (meters)

    Returns: path_length
      path_length :: integer
        The total distance (meters) traveled for this graph
    """
    #
    # Get links in order
    #
    link_orders = [graph.edges[link]['order'] for link in graph.edges]
    ordered_links = [link for _, link in sorted(zip(link_orders, list(graph.edges)))]
    #
    # Get origin portals and generate 2-D array of portals between
    # which we must travel
    #
    origin_portals = [link[0] for link in ordered_links]
    portal_travels = [(origin_portals[i], origin_portals[i+1])
                      for i in range(len(origin_portals)-1)]
    #
    # Sum path length distance
    #
    path_length = np.sum([portals_dists[travel] for travel in portal_travels])
    return path_length

def find_good_depends(ordered_links, ordered_links_depends, i, size):
    """
    Locate all elements j in ordered_links such that a block of
    moving links could be moved there without breaking dependencies.
    If j < i, then we are trying to place the block between j-1 and j.
    If j > i, then we are trying to place the block between j and j+1.

    Inputs:
      ordered_links :: (N,2) list of integers
        The graph links in order
      ordered_links_depends :: N-length list
        The dependencies for each link
      i :: integer
        The starting position of the block
      size :: integer
        The size of the block

    Returns: good_j
      good_j :: 1-D array of integers
        The indicies j such that inserting the block between j-1 and j
        (if j < i) or j and j+1 (if j > i) in ordered links does not
        break any dependencies.
    """
    good_j = []
    #
    # For j < i, none of the links in this block can depend on the
    # links between j and i. So, we determine if each index
    # between 0 and i has a conflict. good_j indicies are those
    # without conflicts nearest to i. We search backwards until we
    # reach the first conflict.
    #
    for j in range(i-1, -1, -1): # loop backwards between 0 and i-1
        for k in range(i, i+size): # loop over block
            if not ordered_links_depends[k]:
                # no dependencies
                continue
            if ((ordered_links[j] in ordered_links_depends[k]) or
                    (ordered_links[j][0] in ordered_links_depends[k])):
                # conflict
                break
        else:
            good_j.append(j)
            continue
        # we found a conflict, so we're done
        break
    #
    # For j > i, none of the links between i+size and j can depend on
    # the links in this block. So, we determine if each index
    # between i+size and -1 has a conflict. good_j indicies are those
    # without conflicts nearest to i+size. We search forwards until
    # we reach the first conflict.
    #
    for j in range(i+size, len(ordered_links)): # loop forwards
        if not ordered_links_depends[j]:
            # no dependencies
            good_j.append(j)
            continue
        for k in range(i, i+size): # loop over block
            if ((ordered_links[k] in ordered_links_depends[j]) or
                    (ordered_links[k][0] in ordered_links_depends[j])):
                break
        else:
            good_j.append(j)
            continue
        break
    #
    # Sort and return good_j
    #
    good_j.sort()
    return good_j

def calc_new_length(ordered_links, portals_dists, original_length,
                    i, size, j):
    """
    Calculate the new total walking distance after moving a block
    of links. This is faster than calling get_path_length since we
    know which distances are changed.

    Inputs:
      ordered_links :: (N,2) list of integers
        The graph links in order
      portals_dists :: (N,N) array of scalars
        The spherical distance between each of the N portals
      original_length :: integer
        The original total walking distance for ordered_links
      i :: integer
        The starting position of the block
      size :: integer
        The size of the block
      j :: integer
        Where the block is moving. If j < i, the block is going
        between j-1 and j. Otherwise, it's going between j and j+1.

    Returns: new_length
      new_length :: integer
        The new walking length after moving the block of links
    """
    #
    # We have removed the distances:
    # (i-1 -> i) (i+size-1 -> i+size) and
    # if j < i: (j-1 -> j)
    # if j > i: (j -> j+1)
    #
    new_length = original_length
    if i > 0:
        new_length -= portals_dists[ordered_links[i-1][0],
                                    ordered_links[i][0]]
    if i+size < len(ordered_links):
        new_length -= portals_dists[ordered_links[i+size-1][0],
                                    ordered_links[i+size][0]]
    if 0 < j < i:
        new_length -= portals_dists[ordered_links[j-1][0],
                                    ordered_links[j][0]]
    if i < j < len(ordered_links)-1:
        new_length -= portals_dists[ordered_links[j][0],
                                    ordered_links[j+1][0]]
    #
    # and we have added the distances:
    # (i-1 -> i+size) and
    # if j < i: (j-1 -> i) and (i+size-1 -> j)
    # if j > i: (j -> i) and (i+size-1 -> j+1)
    #
    if 0 < i < len(ordered_links)-size:
        new_length += portals_dists[ordered_links[i-1][0],
                                    ordered_links[i+size][0]]
    if 0 < j < i:
        new_length += portals_dists[ordered_links[j-1][0],
                                    ordered_links[i][0]]
    if j < i:
        new_length += portals_dists[ordered_links[i+size-1][0],
                                    ordered_links[j][0]]
    if i < j < len(ordered_links)-1:
        new_length += portals_dists[ordered_links[i+size-1][0],
                                    ordered_links[j+1][0]]
    if i < j:
        new_length += portals_dists[ordered_links[j][0],
                                    ordered_links[i][0]]
    return new_length


def reorder_links_depends(graph, portals_dists):
    """
    Re-order links in this graph to minimize build time. Ideally we
    would check the actual time required to complete the build, but
    that takes too long. Instead, we just check the total walking 
    distance.

    Check link dependencies, and move blocks of links earlier or later
    if possible. Update the order in the graph. Since this
    fundamentally changes the plan, return each time there is an
    improvement. This function should be run repeatedly until there
    are no more improvements.

    Inputs:
      graph :: nextworkx graph object
        The graph for this plan
      portals_dists :: (N,N) array of scalars
        The spherical distance between each of the N portals

    Returns: Nothing
    """
    #
    # Get links and dependencies in order
    #
    link_orders = [graph.edges[link]['order'] for link in graph.edges]
    ordered_links = [link for _, link in sorted(zip(link_orders, list(graph.edges)))]
    ordered_links_depends = [graph.edges[link]['depends'] for link in ordered_links]
    #
    # Get the original travel distance
    #
    original_length = get_path_length(graph, portals_dists)
    #
    # Loop over groups of links starting from one individual
    # link to 1/4 of all links.
    #
    for size in range(1, len(ordered_links)//4+1):
        for i in range(len(ordered_links)-size+1):
            #
            # Get the block of links to be moved
            #
            moving_links = ordered_links[i:i+size]
            #
            # If the first and last origin portal in this block are
            # the same, and are the same as the origin portal
            # immediately before or after this block, then we will
            # not reduce the path length by moving this block.
            #
            same_origin = moving_links[0][0] == moving_links[-1][0]
            same_before = ((i > 0) and
                           (ordered_links[i-1][0] == moving_links[0][0]))
            same_after = ((i+size+1 < len(ordered_links)) and
                          (ordered_links[i+size+1][0] == moving_links[0][0]))
            if same_origin and (same_before or same_after):
                continue
            #
            # Find places where this block could go,
            # considering dependencies. N.B. we are placing the block
            # BETWEEN element j-1 and j if j < i, or between j and j+1
            # if j > i.
            #
            good_j = find_good_depends(ordered_links, ordered_links_depends, i, size)
            for j in good_j:
                #
                # Calculate new length after moving block
                #
                new_length = calc_new_length(ordered_links, portals_dists,
                                             original_length, i, size, j)
                if new_length < original_length:
                    #
                    # Move block to this location
                    #
                    if j < i:
                        # block between j-1 and j
                        new_ordered_links = ordered_links[:j]
                        new_ordered_links += moving_links
                        new_ordered_links += ordered_links[j:i]
                        new_ordered_links += ordered_links[i+size:]
                    else:
                        # block between j and j+1
                        new_ordered_links = ordered_links[:i]
                        new_ordered_links += ordered_links[i+size:j+1]
                        new_ordered_links += moving_links
                        new_ordered_links += ordered_links[j+1:]
                    #
                    # Update order in graph and return True
                    #
                    for order, link in enumerate(new_ordered_links):
                        graph.edges[link]['order'] = order
                    return True
    #
    # If we get here, then we did not improve the graph at all, so
    # we return False
    #
    return False
