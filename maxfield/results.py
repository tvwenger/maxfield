#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - results.py

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
August 2020 - A complete re-write of original Ingress Maxfield.
"""

import os
import hashlib
import hmac
import base64
import urllib.request
import urllib.error
from io import BytesIO
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import image
from matplotlib.patches import Polygon
import imageio
from pygifsicle import optimize

# AP gained for various actions
_AP_PER_PORTAL = 1750 # assuming capture and full resonator deployment
_AP_PER_LINK = 313
_AP_PER_FIELD = 1250

class Results:
    """
    The Results object handles the saving of plan data and plots.
    """
    def __init__(self, plan, outdir='', res_colors=False,
                 google_api_key=None, google_api_secret=None,
                 output_csv=False, verbose=False):
        """
        Initialize a new Planner object.

        Inputs:
          plan :: a plan.Plan object
            The plan for which we are generating output.
          outdir :: string
            The directory where results are stored. Created if it
            doesn't already exist.
          res_colors :: boolean
            If True, use resistance color scheme, otherwise
            enlightened
          google_api_key :: string
            If not None, use this as an API key for google maps. If
            None, do not use google maps.
          google_api_secret :: string
            If not None, use this as a signature secret for google 
            maps. If None, do not use a google API signature.
          output_csv :: boolean
            If True, also output machine-readable CSV files
          verbose :: boolean
            If True, display helpful information along the way

        Returns: results
          results :: a new Results object
        """
        self.plan = plan
        self.outdir = outdir
        self.google_api_key = google_api_key
        self.google_api_secret = google_api_secret
        self.output_csv = output_csv
        self.verbose = verbose
        #
        # Get portal indicies sorted by portal name
        #
        self.name_order = np.argsort(
            [portal['name'].lower() for portal in self.plan.portals])
        #
        # Get portal indicies sorted from west (left) to east (right)
        #
        self.pos_order = np.argsort(self.plan.portals_mer[:, 0])
        #
        # Get links, origins, and destinations in build order
        #
        link_orders = [self.plan.graph.edges[link]['order']
                       for link in self.plan.graph.edges]
        self.ordered_links = [link for _, link in
                              sorted(zip(link_orders,
                                         list(self.plan.graph.edges)))]
        self.ordered_origins = [link[0] for link in
                                self.ordered_links]
        self.ordered_destinations = [link[1] for link in
                                     self.ordered_links]
        #
        # Make sure output directory exists
        #
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        #
        # Set color scheme
        #
        if res_colors:
            self.color = 'blue'
        else:
            self.color = 'green'
        #
        # Determine where to put portal labels to avoid overlapping
        # nearest portal
        #
        self.ha = ['center']*len(self.plan.portals)
        self.agent_ha = ['center']*len(self.plan.portals)
        self.va = ['center']*len(self.plan.portals)
        self.agent_va = ['center']*len(self.plan.portals)
        for i, dists in enumerate(self.plan.portals_dists):
            # find nearest except this portal which has 0 distance
            nonzero_idx = np.nonzero(dists)[0]
            nearest = nonzero_idx[np.argmin(dists[nonzero_idx])]
            if (self.plan.portals_mer[i, 0] <
                self.plan.portals_mer[nearest, 0]):
                self.ha[i] = 'right'
                self.agent_ha[i] = 'left'
            elif (self.plan.portals_mer[i, 0] >
                  self.plan.portals_mer[nearest, 0]):
                self.ha[i] = 'left'
                self.agent_ha[i] = 'right'
            if (self.plan.portals_mer[i, 1] <
                self.plan.portals_mer[nearest, 1]):
                self.va[i] = 'top'
                self.agent_va[i] = 'bottom'
            elif (self.plan.portals_mer[i, 1] >
                  self.plan.portals_mer[nearest, 1]):
                self.va[i] = 'bottom'
                self.agent_va[i] = 'top'
        #
        # Set up google map if we're using it
        #
        self.image = None
        if self.google_api_key is not None:
            #
            # Get url
            #
            url = ("/maps/api/staticmap?size=640x640&"
                   "style=feature:poi%7Celement:labels.text%7C"
                   "visibility:off&style=feature:poi.business%7C"
                   "visibility:off&style=feature:road%7C"
                   "element:labels.icon%7Cvisibility:off&"
                   "style=feature:transit%7Cvisibility:off&"
                   "center={0},{1}&zoom={2}&key={3}".
                   format(self.plan.LL_center[1],
                          self.plan.LL_center[0],
                          self.plan.zoom, self.google_api_key))
            #
            # Sign URL
            #
            if self.google_api_secret is not None:
                key = base64.urlsafe_b64decode(self.google_api_secret)
                signature = hmac.new(key, url.encode('UTF-8'),
                                     hashlib.sha1)
                signature = base64.urlsafe_b64encode(
                    signature.digest()).decode('UTF-8')
                url += '&signature={0}'.format(signature)
            url = "https://maps.googleapis.com"+url
            #
            # Fetch image
            #
            try:
                im_data = urllib.request.urlopen(url).read()
                im_data = BytesIO(im_data)
                self.image = image.imread(im_data)
            except urllib.error.URLError as err:
                print("Unable to connect to Google Maps API: {0}".
                      format(err))
            self.extent = [0, 640, 0, 640]

    def key_prep(self):
        """
        Save key preparation file to: outdir/key_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating key preparation file.")
        fname = os.path.join(self.outdir, 'key_preparation.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'key_preparation.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write('Key Preparation: sorted by portal name\n\n')
            fout.write('Needed = total keys required\n')
            fout.write('Have = keys in inventory\n')
            fout.write('Remaining = keys necessary to farm\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            fout.write('Needed ; Have ; Remaining ;   # ; Name\n')
            if self.output_csv:
                fout_csv.write('KeysNeeded, KeysHave, KeysRemaining, PortalNum, PortalName\n')
            for i in self.name_order:
                needed = self.plan.graph.in_degree(i)
                have = self.plan.portals[i]['keys']
                remaining = np.max([0, needed-have])
                fout.write(
                    '{0:>6d} ; {1:>4d} ; {2:>9d} ; {3:>3d} : {4}\n'.
                    format(needed, have, remaining, self.pos_order[i],
                           self.plan.portals[i]['name']))
                if self.output_csv:
                    fout_csv.write(
                        '{0}, {1}, {2}, {3}, {4}\n'.
                        format(needed, have, remaining, self.pos_order[i],
                               self.plan.portals[i]['name']))
        if self.verbose:
            print("File saved to: {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to: {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()

    def ownership_prep(self):
        """
        Save ownership preparation file to:
        outdir/ownership_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating ownership preparation file.")
        fname = os.path.join(self.outdir, 'ownership_preparation.txt')
        with open(fname, 'w') as fout:
            fout.write('Ownership Preparation: '
                       'sorted by portal name\n\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            fout.write("These portals' first links are incoming. "
                       "They should be at full resonators before "
                       "linking.\n\n")
            fout.write('  # ; Name\n')
            for i in self.name_order:
                if ((i in self.ordered_destinations and
                     i in self.ordered_origins and
                     (self.ordered_destinations.index(i) <
                      self.ordered_origins.index(i))) or
                        (i in self.ordered_destinations and
                         i not in self.ordered_origins)):
                    fout.write("{0:>3d} ; {1}\n".
                               format(self.pos_order[i],
                                      self.plan.portals[i]['name']))
            fout.write("\n")
            fout.write("These portals' first links are outgoing. "
                       "Their resonators can be applied when the "
                       "first agent arrives.\n\n")
            fout.write('  # ; Name\n')
            for i in self.name_order:
                if ((i in self.ordered_destinations and
                     i in self.ordered_origins and
                     (self.ordered_origins.index(i) <
                      self.ordered_destinations.index(i))) or
                        (i in self.ordered_origins and
                         i not in self.ordered_destinations)):
                    fout.write("{0:>3d} ; {1}\n".
                               format(self.pos_order[i],
                                      self.plan.portals[i]['name']))
        if self.verbose:
            print("File saved to: {0}".format(fname))

    def agent_key_prep(self):
        """
        Save agent key preparation file to:
        outdir/agent_key_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating agent key preparation file.")
        fname = os.path.join(self.outdir, 'agent_key_preparation.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'agent_key_preparation.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write("Agent Key Preparation: sorted by portal name "
                       "\n\n")
            fout.write('Needed = keys this agent requires\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            if self.output_csv:
                fout_csv.write('Agent, KeysNeeded, PortalNum, Portal Name\n')
            for agent in range(self.plan.num_agents):
                fout.write('Keys for Agent {0}\n'.format(agent+1))
                fout.write('Needed ;   # ; Name\n')
                destinations = [ass['link'] for ass in
                                self.plan.assignments
                                if ass['agent'] == agent]
                for i in self.name_order:
                    count = destinations.count(i)
                    if count > 0:
                        fout.write(
                            "{0:>6d} ; {1:>3d} ; {2}\n".
                            format(count, self.pos_order[i],
                                   self.plan.portals[i]['name']))
                        if self.output_csv:
                            fout_csv.write(
                                "{0}, {1}, {2}, {3}\n".
                                format(agent, count, self.pos_order[i],
                                       self.plan.portals[i]['name']))
                fout.write('\n')
        if self.verbose:
            print("File saved to: {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to: {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()

    def agent_assignments(self):
        """
        Save agent assignments to:
        outdir/agent_assignments.txt
        outdir/agent_1_assignment.txt
        outdir/agent_2_assignment.txt
        etc.

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating agent link assignments.")
        #
        # store each agent's link assignments
        #
        agent_assignments = [[] for _ in range(self.plan.num_agents)]
        #
        # Generate master assignment list
        #
        fname = os.path.join(self.outdir, 'agent_assignments.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'agent_assignments.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write("Agent Linking Assignments: links should be made in this order\n\n")
            fout.write("Link = the current link number\n")
            fout.write("Agent = the person making this link\n")
            fout.write("# = portal number on portal map\n")
            fout.write("Link Origin/Destination = portal name in portal file\n\n")
            fout.write("Link ; Agent ;   # ; Link Origin\n")
            fout.write("                 # ; Link Destination\n\n")
            if self.output_csv:
                fout_csv.write('LinkNum, Agent, OriginNum, OriginName, DestinationNum, DestinationName\n')
            #
            # Group assignments by arrival time
            #
            arrivals = list(set([ass['arrive'] for ass in
                                 self.plan.assignments]))
            arrivals.sort()
            link = 1
            for arrival in arrivals:
                #
                # Get the assignments happening at this arrival time
                #
                my_ass = [ass for ass in self.plan.assignments
                          if ass['arrive'] == arrival]
                for ass in my_ass:
                    origin = np.where(
                        self.pos_order == ass['location'])[0][0]
                    dest = np.where(
                        self.pos_order == ass['link'])[0][0]
                    fout.write("{0:4} ; {1:5} ; {2:3} ; {3} \n".format(
                        link, ass['agent']+1, origin,
                        self.plan.portals[origin]['name']))
                    fout.write("             ; {0:3} : {1} \n\n".format(
                        dest, self.plan.portals[dest]['name']))
                    if self.output_csv:
                        fout_csv.write('{0}, {1}, {2}, {3}, {4}, {5}\n'.format(
                            link, ass['agent']+1, origin, self.plan.portals[origin]['name'],
                            dest, self.plan.portals[dest]['name']))
                    #
                    # Save to agent assignment
                    #
                    agent_assignments[ass['agent']].append(
                        [link, origin, self.plan.portals[origin]['name'],
                         dest, self.plan.portals[dest]['name']])
                    link += 1
        if self.verbose:
            print("File saved to {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()
        #
        # Generate each agent's assignment
        #
        for i, asses in enumerate(agent_assignments):
            if self.verbose:
                print("Generating link assignment for agent {0}.".format(i+1))
            fname = os.path.join(self.outdir, 'agent_{0}_assignment.txt'.format(i+1))
            with open(fname, 'w') as fout:
                fout.write("Agent {0} Linking Assignment: links should be made in this order\n\n".format(i+1))
                fout.write("Link = the current link number\n")
                fout.write("Agent = the person making this link\n")
                fout.write("# = portal number on portal map\n")
                fout.write("Link Origin/Destination = portal name in portal file\n\n")
                fout.write("Link ; Agent ;   # ; Link Origin\n")
                fout.write("                 # ; Link Destination\n\n")
                for ass in asses:
                    fout.write("{0:4} ; {1:5} ; {2:3} ; {3} \n".format(
                        ass[0], i+1, ass[1], ass[2]))
                    fout.write("             ; {0:3} : {1} \n\n".format(
                        ass[3], ass[4]))
            if self.verbose:
                print("File saved to {0}".format(fname))
        if self.verbose:
            print()

    def make_portal_fig(self):
        """
        Generate and return a matplotlib figure and axis with the
        portals placed. This is useful since we start each plot with
        the portals.

        Inputs: Nothing

        Returns: fig, ax
          The generated matplotlib Figure and Axis
        """
        fig = plt.figure(figsize=(7.6, 8))
        ax = fig.add_subplot(111)
        ax.set_position([0, 0, 1, 0.95])
        if self.image is not None:
            implot = ax.imshow(self.image, extent=self.extent,
                               zorder=0)
        ax.plot(self.plan.portals_mer[:, 0],
                self.plan.portals_mer[:, 1],
                marker='o', color=self.color, linestyle='none',
                markeredgecolor='black', markersize=10, zorder=10)
        for i, mer in enumerate(self.plan.portals_mer[self.pos_order]):
            ax.text(mer[0], mer[1], i, fontweight='bold',
                    ha=self.ha[self.pos_order[i]],
                    va=self.va[self.pos_order[i]],
                    fontsize=16, zorder=11)
        ax.set_aspect('equal')
        if self.image is not None:
            ax.axis(self.extent)
        ax.axis('off')
        return fig, ax

    def portal_map(self):
        """
        Save portal map to:
        outdir/portal_map.png

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating portal map.")
        fig, ax = self.make_portal_fig()
        ax.set_title('Portal Map: {0} portals numbered W to E'.
                     format(len(self.plan.portals)), fontsize=18)
        fname = os.path.join(self.outdir, 'portal_map.png')
        fig.savefig(fname, dpi=300)
        plt.close(fig)
        if self.verbose:
            print("File saved to: {0}".format(fname))

    def link_map(self):
        """
        Save link map to:
        outdir/link_map.png

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating link map.")
        fig, ax = self.make_portal_fig()
        for link in self.ordered_links:
            # plot link
            ax.plot(self.plan.portals_mer[link, 0],
                    self.plan.portals_mer[link, 1],
                    linestyle='-', color=self.color)
            # add patch if this link completes a field
            for fld in self.plan.graph.edges[link]['fields']:
                coords = [self.plan.portals_mer[i] for i in fld]
                patch = Polygon(coords, facecolor=self.color,
                                alpha=0.3, edgecolor='none')
                ax.add_patch(patch)
        ax.set_title('Link Map: {0} links and {1} fields'.
                     format(self.plan.graph.num_links,
                            self.plan.graph.num_fields),
                     fontsize=18)
        fname = os.path.join(self.outdir, 'link_map.png')
        fig.savefig(fname, dpi=300)
        plt.close(fig)
        if self.verbose:
            print("File saved to: {0}".format(fname))
            print()

    def step_plots(self):
        """
        Save each step frame to:
        outdir/frames/frame_00000.png
        outdir/frames/frame_00001.png
        etc.
        And generate GIF in outdir/plan_movie.gif

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating step-by-step plots.")
        #
        # Make frame directory if necessary
        #
        outdir = os.path.join(self.outdir, 'frames')
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        #
        # Base frame is portal map with agent locations
        #
        num_links = 0
        num_fields = 0
        num_ap = len(self.plan.portals)*_AP_PER_PORTAL
        fig, ax = self.make_portal_fig()
        drawn_agents = []
        agents_last_pos = []
        frames = []
        for agent in range(self.plan.num_agents):
            #
            # Find agent's first location
            #
            for ass in self.plan.assignments:
                if ass['agent'] == agent:
                    break
            else:
                raise ValueError("Could not find agent {0} in "
                                 "assignments".format(agent))
            portal_idx = ass['location']
            agents_last_pos.append(portal_idx)
            xpos = self.plan.portals_mer[portal_idx, 0]
            ypos = self.plan.portals_mer[portal_idx, 1]
            drawn_agents.append(
                ax.text(xpos, ypos, 'A{0}'.format(agent+1),
                        bbox={'facecolor':'magenta', 'alpha':0.5,
                              'pad':1},
                        fontweight='bold',
                        ha=self.agent_ha[portal_idx],
                        va=self.agent_va[portal_idx],
                        fontsize=12, zorder=12))
        ax.set_title('Time: 00:00:00  Links:    0  Fields:    0  '
                     'AP: {0:>7d}'.format(num_ap), fontsize=18)
        fname = os.path.join(outdir, 'frame_00000.png')
        fig.savefig(fname, dpi=300)
        frames.append(fname)
        #
        # Group assignments by arrival time, and plot each arrival
        # time actions as a single frame.
        #
        arrivals = list(set([ass['arrive'] for ass in
                             self.plan.assignments]))
        arrivals.sort()
        #
        # Plot agent movements, links, and fields
        #
        frame = 1
        for arrival in arrivals:
            #
            # Get the assignments happening at this arrival time
            #
            my_ass = [ass for ass in self.plan.assignments
                      if ass['arrive'] == arrival]
            #
            # Determine if agents moved since last frame
            #
            drawn_lines = []
            for ass in my_ass:
                last_origin = agents_last_pos[ass['agent']]
                this_origin = ass['location']
                if last_origin == this_origin:
                    # did not move
                    continue
                #
                # Draw movement line
                #
                line, = ax.plot([self.plan.portals_mer[last_origin, 0],
                                 self.plan.portals_mer[this_origin, 0]],
                                [self.plan.portals_mer[last_origin, 1],
                                 self.plan.portals_mer[this_origin, 1]],
                                linestyle='--', color='magenta', lw=2)
                drawn_lines.append(line)
                #
                # Update agent position
                #
                drawn_agents[ass['agent']].remove()
                drawn_agents[ass['agent']] = \
                    ax.text(self.plan.portals_mer[this_origin, 0],
                            self.plan.portals_mer[this_origin, 1],
                            'A{0}'.format(ass['agent']+1),
                            bbox={'facecolor':'magenta', 'alpha':0.5,
                                  'pad':1},
                            fontweight='bold',
                            ha=self.agent_ha[portal_idx],
                            va=self.agent_va[portal_idx],
                            fontsize=12, zorder=12)
                agents_last_pos[ass['agent']] = this_origin
            #
            # If at least one agent moved, save frame and remove
            # movement lines
            #
            if drawn_lines:
                #
                # Update title, save
                #
                hr = arrival // 3600
                mn = (arrival-hr*3600) // 60
                sc = (arrival-hr*3600-mn*60)
                ax.set_title('Time: {0:02d}:{1:02d}:{2:02d}  '
                             'Links: {3:>4d}  Fields: {4:>4d}  '
                             'AP: {5:>7d}'.
                             format(hr, mn, sc, num_links, num_fields,
                                    num_ap), fontsize=18)
                fname = os.path.join(outdir, 'frame_{0:05d}.png'.
                                     format(frame))
                frame += 1
                fig.savefig(fname, dpi=300)
                frames.append(fname)
                #
                # Remove drawn lines
                #
                for line in drawn_lines:
                    line.remove()
            #
            # Draw links and fields, new fields are red
            #
            fields_patches = []
            fields_drawn = []
            for ass in my_ass:
                link = (ass['location'], ass['link'])
                ax.plot(self.plan.portals_mer[link, 0],
                        self.plan.portals_mer[link, 1],
                        color=self.color, lw=2)
                num_links += 1
                num_ap += _AP_PER_LINK
                for fld in self.plan.graph.edges[link]['fields']:
                    coords = [self.plan.portals_mer[i] for i in fld]
                    patch = Polygon(coords, facecolor='red',
                                    alpha=0.3, edgecolor='none')
                    fields_patches.append(patch)
                    fields_drawn.append(ax.add_patch(patch))
                    num_fields += 1
                    num_ap += _AP_PER_FIELD
            #
            # Update title, save
            #
            hr = arrival // 3600
            mn = (arrival-hr*3600) // 60
            sc = (arrival-hr*3600-mn*60)
            ax.set_title('Time: {0:02d}:{1:02d}:{2:02d}  '
                         'Links: {3:>4d}  Fields: {4:>4d}  '
                         'AP: {5:>7d}'.
                         format(hr, mn, sc, num_links, num_fields,
                                num_ap), fontsize=18)
            fname = os.path.join(outdir, 'frame_{0:05d}.png'.
                                 format(frame))
            frame += 1
            fig.savefig(fname, dpi=300)
            frames.append(fname)
            #
            # Remove red patch, update to color and re-add
            #
            for patch, drawn in zip(fields_patches, fields_drawn):
                drawn.remove()
                patch.set_facecolor(self.color)
                ax.add_patch(patch)
        plt.close(fig)
        if self.verbose:
            print("Frames saved to: {0}/".format(outdir))
        #
        # Generate GIF
        #
        fname = os.path.join(self.outdir, 'plan_movie.gif')
        with imageio.get_writer(fname, mode='I', duration=0.5) as writer:
            for frame in frames:
                image = imageio.imread(frame)
                writer.append_data(image)
        optimize(fname)
        if self.verbose:
            print("GIF saved to {0}".format(fname))
            print()
