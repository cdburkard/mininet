#!/usr/bin/python

'''
An example showing how to add and delete hosts, switches, and links
from the CLI.

Is there a better way to choose a custom class?
could explicitly define classes that can be chosen, as we do
when you start the mininet CLI.

How do we allow an arbitrary parameter to be input when creating a
new object?
use literal_eval to evaluate a python expression. unfortunately we
must include quotes for string objects if we do this... is there a
better way?

how do we start user switch at runtime?

PingFull does not work if there are no interfaces. should fix this
Done



'''




from mininet.topo import SingleSwitchTopo
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.log import setLogLevel, info, error, debug
from mininet.node import OVSSwitch
import importlib
from ast import literal_eval

class mobilityCLI( CLI ):
    "allow addition and deletion of objects from CLI"
    
    def do_delswitch( self, line ):
        "delete an arbitrary switch during runtime"
        args = line.split()
        if len( args ) != 1:
            error( 'usage: delswitch switchname\n' )
            return
        switchname = args[ 0 ]
        if switchname not in self.mn.nameToNode.keys():
            error( '*** no switch named %s\n' % switchname )
            return
        switch = self.mn.nameToNode[ switchname ]
        if switch not in self.mn.switches:
            error( '*** no switch named %s\n' % switchname )
            return
        self.mn.removeNode( switch )

    def do_dellink( self, line ):
        "delete an arbitrary link at runtime"
        args = line.split()
        if len( args ) != 2:
            error( 'usage: dellink node1 node2\n' )
            return
        node1Name = args[ 0 ]
        node2Name = args[ 1 ]
        for node in node1Name, node2Name:
            if node not in self.mn.nameToNode.keys():
                error( '*** no node named %s\n' % node )
                return
        node1 = self.mn.nameToNode[ node1Name ]
        node2 = self.mn.nameToNode[ node2Name ]
        self.mn.delLink( node1, node2 )

    def do_delhost( self, line ):
        "deletes an arbitrary host during runtime"
        args = line.split()
        if len( args ) != 1:
            error( 'usage: delhost hostname\n' )
            return
        hostname = args[ 0 ]
        args = args[ 1: ]
        if hostname not in self.mn.nameToNode.keys():
            error( '*** no host named %s\n' % hostname )
            return
        host = self.mn.nameToNode[ hostname ]
        if host not in self.mn.hosts:
            error( '*** no host named %s\n' % hostname )
            return
        self.mn.removeNode( host )

    def do_addhost( self, line ):
        "add an arbitrary host to mininet during runtime"
        args = line.split()
        if len( args ) < 1:
           error( 'usage: addhost hostname [arg1] [arg2] ...\n' )
           return
        hostname = args[ 0 ]
        if hostname in self.mn:
            error( '%s already exists!\n' % hostname )
            return
        args = args[ 1: ]
        params = {}
        switchname = None
        for arg in args:
            arg, val = arg.split( '=' )
            if arg == 'switch':
                switchname = val
                continue
            if arg == 'cls':
                try:
                    cls = getattr( importlib.import_module( 'mininet.node' ), val )
                except AttributeError:
                    try:
                        cls = getattr( importlib.import_module( 'mininet.nodelib' ), val )
                    except AttributeError:
                        error( '*** no class named %s\n' % val )
                        return
                params[ arg ] = cls
                continue
            params[ arg ] = literal_eval( val )
            print params
        if switchname:
            switch = self.mn.nameToNode[ switchname ]
        host = self.mn.addHost( hostname, **params )
        if switchname:
            link = self.mn.addLink( host, switch )
            switch.attach( link.intf2 )
            host.configDefault( **params )
        else:
            host.config( **params )

    def do_addswitch( self, line ):
        "add an arbitrary switch at runtime"
        args = line.split()
        if len( args ) < 1:
            error( 'usage: addswitch switchname [arg1] [arg2] ...\n' )
            return
        switchname = args[ 0 ]
        if switchname in self.mn:
            error( '%s already exists!\n' % switchname )
            return
        args = args[ 1: ]
        params = {}
        for arg in args:
            arg, val = arg.split( '=' )
            if arg == 'cls':
                try:
                    cls = getattr( importlib.import_module( 'mininet.node' ), val )
                except AttributeError:
                    error( '*** no switch class named %s\n' % val )
                    return
                params[ arg ] = cls
                #params[ arg ] = eval( val )
                continue
            params[ arg ] = literal_eval( val )
        switch = self.mn.addSwitch( switchname, **params )
        switch.start( self.mn.controllers )

    def do_addlink( self, line ):
        "add a link between nodes at runtime"
        args = line.split()
        if len( args ) < 2:
            error( 'usage: addlink node1 node2 [arg1] [arg2] ...\n' )
            return
        node1 = self.mn.nameToNode[ args[ 0 ] ]
        node2 = self.mn.nameToNode[ args[ 1 ] ]
        params = {}
        args = args[ 2: ]
        for arg in args:
            arg, val = arg.split( '=' )
            if arg == 'cls':
                try:
                    cls = getattr( importlib.import_module( 'mininet.link' ), val )
                except AttributeError:
                    error( '*** no link class named %s\n' % val )
                    return
                params[ arg ] = cls
                #params[ arg ] = eval( val )
                continue
            params[ arg ] = literal_eval( val )
        link = self.mn.addLink( node1, node2, **params )
        for node in node1, node2:
            if node in self.mn.hosts:
                node.configDefault( **node.params ) # ipbase wont work for this
            elif isinstance( node, OVSSwitch ): # or IVS Switch
                if node is node1:
                    node.attach( link.intf1 )
                if node is node2:
                    node.attach( link.intf2 )

class AltNet( Mininet ):

    # I was a little confused about this datastructure upon first look. maybe this will help others?
    def getNodeLinks( self, node ):
        """Get all of the links attached to a node.
        node: node name
        returns: dictionary of interfaces to connected nodes"""
        interfaces = []
        nodeLinks = {}
        for intf in node.intfList():
            if intf.link:
                intfs = [ intf.link.intf1, intf.link.intf2 ]
                intfs.remove( intf )
                interfaces += intfs
                nodeLinks[ intfs[ 0 ] ] = intfs[ 0 ].node 
        return nodeLinks

    def removeNode( self, node ):
        "remove a node from a running network"
        node.stop()
        node.cleanup()
        nodeLinks = self.getNodeLinks( node )
        for intf, n in nodeLinks.items():
            del n.intfs[ n.ports[ intf ] ]
            del n.ports[ intf ]
        if node in self.hosts:
            self.hosts.remove( node )
        elif node in self.switches:
            self.switches.remove( node )
            info( '\n' )
        del self.nameToNode[ node.name ]

    def delLink( self, node1, node2 ):
        "delete a link from mininet while running"
        for intf in node1.intfList():
            if intf.link:
                intf1 = intf
                intfs = [ intf.link.intf1, intf.link.intf2 ]
                intfs.remove( intf )
                intf2 = intfs[0]
                if intf2 in node2.intfList():
                    intf.link.delete()
                    port1 = node1.ports[ intf1 ]
                    port2 = node2.ports[ intf2 ]
                    del node1.nameToIntf[ intf1.name ]
                    del node2.nameToIntf[ intf2.name ]
                    del node1.intfs[ port1 ]
                    del node2.intfs[ port2 ]
                    del node1.ports[ intf1 ]
                    del node2.ports[ intf2 ]
                    return True
        debug( '*** warning: no link between %s and %s\n' %( node1, node2 ) )
        return False

    def pingFull( self, hosts=None, timeout=None ):
        """Ping between all specified hosts and return all data.
           hosts: list of hosts
           timeout: time to wait for a response, as string
           returns: all ping data; see function body."""
        # should we check if running?
        # Each value is a tuple: (src, dsd, [all ping outputs])
        all_outputs = []
        if not hosts:
            hosts = self.hosts
            output( '*** Ping: testing ping reachability\n' )
        for node in hosts:
            output( '%s -> ' % node.name )
            for dest in hosts:
                if node != dest:
                    opts = ''
                    if timeout:
                        opts = '-W %s' % timeout
                    if dest.IP():
                        result = node.cmd( 'ping -c1 %s %s' % (opts, dest.IP()) )
                        outputs = self._parsePingFull( result )
                        sent, received, rttmin, rttavg, rttmax, rttdev = outputs
                        all_outputs.append( (node, dest, outputs) )
                    else:
                        received = None
                    output( ( '%s ' % dest.name ) if received else 'X ' )
            output( '\n' )
        output( "*** Results: \n" )
        for outputs in all_outputs:
            src, dest, ping_outputs = outputs
            sent, received, rttmin, rttavg, rttmax, rttdev = ping_outputs
            output( " %s->%s: %s/%s, " % (src, dest, sent, received ) )
            output( "rtt min/avg/max/mdev %0.3f/%0.3f/%0.3f/%0.3f ms\n" %
                    (rttmin, rttavg, rttmax, rttdev) )
        return all_outputs

def testCLI():
    net = AltNet(topo = SingleSwitchTopo())
    net.start()
    mobilityCLI( net )
    net.stop()

def testAPI():
    net = AltNet(topo = SingleSwitchTopo())
    net.start()
    net.pingAll()
    net.delLink( net.hosts[0], net.switches[ 0 ] )
    net.pingAll()
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    testCLI()
    #testAPI()
