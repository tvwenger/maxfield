#!/usr/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - PlanPrinterMap.py

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2016 by
Jonathan Baker; babamots@gmail.com
Trey Wenger; tvwenger@gmail.com

Builds valid fields

original version by jpeterbaker
29 Sept 2014 - tvw V2.0 major updates
26 Feb 2016 - tvw v3.0
              merged some new stuff from jpeterbaker's new version
              Added SBLA support
"""
import geometry
import numpy as np

# Set to False if only perfectly optimal plans should be produced
_ALLOW_SUBOPTIMAL = True

class Deadend(Exception):
    def __init__(self,s):
        self.explain = s

def can_add_more_links_from_portal(a, p):
    return (a.out_degree(p) < 8) or (a.node[p]['sbla'] and a.out_degree(p) < 40)

def try_reduce_out_degree(a,p):
    # Reverse as many edges out-edges of p as possible
    # now with SBLA support!
    toremove = []
    for q in a.edge[p]:
        if can_add_more_links_from_portal(a,q):
            if a.edge[p][q]['reversible']:
                a.add_edge(q,p)
                a.edge[q][p] = a.edge[p][q]
                toremove.append(q)

    for q in toremove:
        a.remove_edge(p,q)

def try_ordered_edge(a,p,q,reversible,allow_suboptimal):
    # now with SBLA support
    if a.has_edge(p,q) or a.has_edge(q,p):
        return

    # if reversible and a.out_degree(p) > a.out_degree(q):
        # p,q = q,p

    if not can_add_more_links_from_portal(a,p):
        try_reduce_out_degree(a,p)

    if not can_add_more_links_from_portal(a,p):
    # We tried but failed to reduce the out-degree of p
        if not reversible and not allow_suboptimal:
            # print '%s already has 8 outgoing'%p
            raise(Deadend('%s already has max outgoing'%p))
        if not can_add_more_links_from_portal(a,q):
            try_reduce_out_degree(a,q)
        if (not can_add_more_links_from_portal(a,q) and not allow_suboptimal):
            # print '%s and %s already have 8 outgoing'%(p,q)
            raise(Deadend('%s and %s already have max outgoing'%(p,q)))
        p,q = q,p
    
    try:
        m = len(a.edgeStack)
    except AttributeError:
        a.edgeStack = []
        m = 0

    a.add_edge(p,q,{'order':m,'reversible':reversible,'fields':[],'depends':[]})

    a.edgeStack.append( (p,q) )
    # print 'adding',p,q
    # print a.edgeStack


triangleContentCache = {}

class Triangle:
    def __init__(self,verts,a,exterior=False,allow_suboptimal=_ALLOW_SUBOPTIMAL):
        '''
        verts should be a 3-list of Portals
        verts[0] should be the final one used in linking
        exterior should be set to true if this triangle has no triangle parent
            the orientation of the outer edges of exterior Triangles do not matter
        '''
        # If this portal is exterior, the final vertex doesn't matter
        self.verts = list(verts)
        self.a = a
        self.exterior = exterior

        # This randomizes the Portal used for the jet link. I am
        # experimenting with having maxfield.triangulate and
        # Triangle.split choose this portal carefully, so don't
        # randomize
        """
        if exterior:
            # Randomizing should help prevent perimeter nodes from getting too many links
            final = np.random.randint(3)
            tmp = self.verts[final]
            self.verts[final] = self.verts[0]
            self.verts[0] = tmp
        """
        self.pts = np.array([a.node[p]['xyz'] for p in verts])
        self.children = []
        self.contents = []
        self.center = None
        self.allow_suboptimal = allow_suboptimal

    def findContents(self,candidates=None):
        if candidates == None:
            candidates = xrange(self.a.order())

        triangleKey = sum([1 << int(p) for p in self.verts])

        if triangleKey in triangleContentCache:
            self.contents.extend(triangleContentCache[triangleKey])

        else:
            for p in candidates:
                if p in self.verts:
                    continue
                if geometry.sphereTriContains(self.pts,self.a.node[p]['xyz']):
                    self.contents.append(p)
            triangleContentCache[triangleKey] = self.contents


    def randSplit(self):
        if len(self.contents) == 0:
            return
        
        p = self.contents[np.random.randint(len(self.contents))]
        
        self.splitOn(p)

        for child in self.children:
            child.randSplit()

    def nearSplit(self, recursive=False):
        # Split on the node closest to final
        if len(self.contents) == 0:
            return
        contentPts = np.array([self.a.node[p]['xyz'] for p in self.contents])
        displaces = contentPts - self.a.node[self.verts[0]]['xyz']
        dists = np.sum(displaces**2,1)
        closest = np.argmin(dists)

        self.splitOn(self.contents[closest])

        if recursive:
            for child in self.children:
                child.nearSplit()

    def splitOn(self,p):
        # Splits this Triangle to produce 3 children using portal p
        # p is passed as the first vertex parameter in the
        # construction of 'opposite', so it will be opposite's
        # 'final vertex' unless randomization is used
        # 'opposite' is the child that does not share the final vertex
        # Because of the build order, it's safe for this triangle to
        # believe it is exterior
        opposite  =  Triangle([p,self.verts[1],
                               self.verts[2]],self.a,True)
        # The other two children must also use my final as their final
        adjacents = [\
                     Triangle([self.verts[0],\
                               self.verts[2],p],self.a),\
                     Triangle([self.verts[0],\
                               self.verts[1],p],self.a)\
                    ]
        
        self.children = [opposite]+adjacents
        self.center = p

        for child in self.children:
            child.findContents(self.contents)

    def tostr(self):
        # Just a string representation of the triangle
        return str([self.a.node[self.verts[i]]['name'] for i in range(3)])

    def buildFinal(self):
        # print 'building final',self.tostr()
        if self.exterior:
            # Avoid making the final the link origin when possible
            # print self.tostr(),'is exterior'
            try_ordered_edge(self.a,self.verts[1],\
                               self.verts[0],self.exterior,self.allow_suboptimal)
            try_ordered_edge(self.a,self.verts[2],\
                               self.verts[0],self.exterior,self.allow_suboptimal)
        else:
            # print self.tostr(),'is NOT exterior'
            try_ordered_edge(self.a,self.verts[0],\
                               self.verts[1],self.exterior,self.allow_suboptimal)
            try_ordered_edge(self.a,self.verts[0],\
                               self.verts[2],self.exterior,self.allow_suboptimal)

        if len(self.children) > 0:
            for i in [1,2]:
                self.children[i].buildFinal()

    def buildExceptFinal(self):
        # print 'building EXCEPT final',self.tostr()
        self.nearSplit()
        if len(self.children) == 0:
            # print 'no children'
            p,q = self.verts[2] , self.verts[1]
            try_ordered_edge(self.a,p,q,True,self.allow_suboptimal)
            return

        # Child 0 is guaranteed to be the one opposite final
        self.children[0].buildGraph()

        for child in self.children[1:3]:
            child.buildExceptFinal()

    def buildGraph(self):
        # print 'building',self.tostr()
        '''
        A first generation triangle could have its final vertex's
        edges already completed by neighbors.
        This will cause the first generation to be completed when
        the opposite edge is added which complicates completing inside
        descendants.
        Solve this by choosing a new final vertex, if possible.
        '''
        if (                                                \
            self.a.has_edge(self.verts[0],self.verts[1]) or \
            self.a.has_edge(self.verts[1],self.verts[0])    \
           ) and                                            \
           (                                                \
            self.a.has_edge(self.verts[0],self.verts[2]) or \
            self.a.has_edge(self.verts[2],self.verts[0])    \
           ):
            # print 'Final vertex completed!!!'
            if self.a.has_edge(self.verts[2],self.verts[1]) or \
               self.a.has_edge(self.verts[1],self.verts[2]):
                raise Deadend('Final vertex completed by neighbors')
            else:
                # make verts[1] the new final vertex
                self.verts[0], self.verts[1] = self.verts[1], self.verts[0]

        self.buildExceptFinal()
        self.buildFinal()

    def contains(self,pt):
        return np.all(np.sum(self.orths*(pt-self.pts),1) < 0)

    # Attach to each edge a list of fields that it completes
    def markEdgesWithFields(self, clean=False):
        if clean:
            for p,q in self.a.edges_iter():
                self.a.edge[p][q]['fields'] = []
                self.a.edge[p][q]['depends'] = []

        edges = [(0,0)]*3
        for i in range(3):
            p = self.verts[i-1]
            q = self.verts[i-2]
            if not self.a.has_edge(p,q):
                p,q = q,p
            # The graph should have been completed by now, so the edge p,q exists
            edges[i] = (p,q)
            if not self.a.has_edge(p,q):
                print 'a does NOT have edge',p,q
                print 'there is a programming error'
                print 'a only has the edges:'
                for p,q in self.a.edges_iter():
                    print p,q
                print 'a has %s 1st gen triangles:'%len(self.a.triangulation)
                for t in self.a.triangulation:
                    print t.verts

        edgeOrders = [self.a.edge[p][q]['order'] for p,q in edges]

        lastInd = np.argmax(edgeOrders)
        # The edge that completes this triangle
        p,q = edges[lastInd]

        self.a.edge[p][q]['fields'].append(self.verts)
        if not self.exterior:
            # the last edge depends on the other two
            del edges[lastInd]
            self.a.edge[p][q]['depends'].extend(edges)
        else:
            # in an exterior triangle that has children, only the edge
            # on the opposite side of the "final" vertex is a dependency;
            # childless exterior triangles can be built in any order
            if len(self.children) > 0:
                self.a.edge[p][q]['depends'].append(edges[0])


        for child in self.children:
            child.markEdgesWithFields()

        # all edges starting from inside this triangle have to be completed before it
        for c in self.contents:
            self.a.edge[p][q]['depends'].append(c)

        #print("edge %d-%d depends on: %s" % (p, q, self.a.edge[p][q]['depends']))

    def edgesByDepth(self,depth):
        # Return list of edges of triangles at given depth
        # 0 means edges of this very triangle
        # 1 means edges splitting this triangle
        # 2 means edges splitting this triangle's children 
        # etc.
        if depth == 0:
            return [ (self.verts[i],self.verts[i-1]) for i in range(3) ]
        if depth == 1:
            if self.center == None:
                return []
            return [ (self.verts[i],self.center) for i in range(3) ]
        return [e for child in self.children\
                  for e in child.edgesByDepth(depth-1)]
