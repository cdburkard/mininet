#!/usr/bin/python

'''
Notes:

This file contains classes and methods useful for integrating LincOE with Mininet, 
such as startOE, stopOE, opticalLink, and opticalSwitch

- $ONOS_ROOT ust be set
- Need to run with sudo -E to preserve ONOS_ROOT env var
- Currently, we assume the LINC-Config-Generator is in the home directory
- We also assume linc-oe is in the home directory
- LINC-config-generator and linc-oe must be subdirectories of the user's
  home directory

            TODO
        -----------
    - should make a method to check if all tap interfaces are up
    - clean up files after runtime
        - maybe save the old files in a separate directory?
    - modify script to allow startOE to run before net.start()
    - add ONOS as a controller
        - will need to wait until onos-rest is installed before attempting to push topology

            Usage:
        ------------
    - import opticalLink and opticalSwitch from this module
    - import startOE and stopOE from this module
    - create topology as you would a normal topology. when 
      to an optical switch with topo.addLink, always specify cls=opticalLink
    - when creating an optical switch, use cls=opticalSwitch in topo.addSwitch
    - for annotations on links and switches, a dictionary must be passed in as
      the annotations argument
    - startOE must be run AFTER net.start() with net as an argument.
    - stopOE can be run at any time

I created a separate function to start lincOE to avoid subclassing Mininet.
In case anyone wants to write something that DOES subclass Mininet, I
thought I would outline how:

If we want an object that starts lincOE within the mininet class itself,
we need to add another object to Mininet that contains all of the json object
information for each switch. We would still subclass switch and link, but these
classes would basically be dummy classes that store their own json information
in the Mininet class object. We may also change the default switch class to add
it's tap interfaces from lincOE during startup. The start() method for mininet would 
grab all of the information from these switches and links, write configuration files
for lincOE using the json module, start lincOE, then run the start methodfor each
switch. The new start() method for each switch would parse through the sys.config
file that was created and find the tap interface it needs to connect to, similar 
to the findTap function that I currently use. After all of the controllers and 
switches have been started, the new Mininet start() method should also push the 
Topology configuration file to ONOS.

'''

from time import sleep
import re
from mininet.node import Switch, RemoteController
from mininet.topo import Topo
from mininet.util import quietRun
from mininet.net import Mininet
from mininet.log import  setLogLevel, info, error
import  json
from mininet.link import Link, Intf
from mininet.cli import CLI

class opticalSwitch( Switch ):

    def __init__( self, name, latitude=None, longitude=None, dpid=None, allowed=True, switchType='ROADM', annotations={}, **params ):
        params[ 'inNamespace' ] = False
        Switch.__init__( self, name, dpid=dpid, **params )
        self.name = name
        self.annotations = annotations
        switchParams = {}
        switchParams.setdefault( 'numRegen', 0 )
        self.switchParams = switchParams
        self.latitude = latitude
        self.longitude = longitude
        self.allowed = allowed
        self.switchType = switchType
        self.configDict = {}

    def start( self, *opts, **params ):
        self.configDict[ 'uri' ] = 'of:' + self.dpid
        self.configDict[ 'annotations' ] = self.annotations
        self.configDict[ 'annotations' ].setdefault( 'name', self.name )
        self.configDict[ 'hw' ] = 'OE'
        self.configDict[ 'mfr' ] = 'Linc'
        self.configDict[ 'mac' ] = 'ffffffffffff' + self.dpid[-2] + self.dpid[-1]
        self.configDict[ 'type' ] = self.switchType
        self.configDict[ 'ports' ] = []
        for port, intf in self.intfs.items():
            if intf.name == 'lo':
                continue
            else:
                self.configDict[ 'ports' ].append( intf.json() )


    def json( self ):
        'use this to return dict for switch'
        return self.configDict
    def terminate( self ):
        pass

class opticalLink( Link ):

    def __init__( self, node1, node2, port1=None, port2=None, allowed=True, intfName1=None, intfName2=None, linkType='OPTICAL', annotations={}, speed1=0, speed2=0, **params ):
        self.allowed = allowed
        self.annotations = annotations
        self.linkType = linkType
        params1 = { 'speed': speed1 }
        params2 = { 'speed': speed2 }
        if isinstance( node1, opticalSwitch ):
            cls1 = opticalIntf
        else:
            cls1 = Intf
            # bad hack to stop error message from appearing when we try to set up intf in a packet switch, and there is no interface there( because we do not run makeIntfPair ) could probably change makeIntfPair to work
            intfName1 = 'lo'
        if isinstance( node2, opticalSwitch ):
            cls2 = opticalIntf
        else:
            cls2 = Intf
            intfName2 = 'lo'
        Link.__init__( self, node1, node2, port1=port1, port2=port2, intfName1=intfName1, intfName2=intfName2, cls1=cls1, cls2=cls2, params1=params1, params2=params2 )
        

    @classmethod
    def makeIntfPair( _cls, intfName1, intfName2, *args, **kwargs ):
        pass

    def json( self ):
        configData = {}
        configData[ 'src' ] = 'of:' +  self.intf1.node.dpid + '/%s' % self.intf1.node.ports[ self.intf1 ]
        configData[ 'dst' ] = 'of:' +  self.intf2.node.dpid + '/%s' % self.intf2.node.ports[ self.intf2 ]
        configData[ 'type' ] = self.linkType
        configData[ 'annotations' ] = self.annotations
        return configData

class opticalIntf( Intf ):

    def __init__( self, name=None, node=None, speed=100000,  port=None, link=None, **params ):
        self.node = node
        self.speed = speed
        self.port = port
        self.link = link
        self.name = name
        node.addIntf( self, port=port )
        self.params = params

    def json( self ):
        configDict = {}
        configDict[ 'port' ] = self.port
        configDict[ 'speed' ] = self.speed
        configDict[ 'type' ] = 'FIBER'
        return configDict

    def config( self, *args, **kwargs ):
        pass

    

class opticalTestTopo( Topo ):

    def build( self ):
         opticalAnn = { 'optical.waves': 80, 'optical.type': "WDM", 'durable': True }
         switchAnn = { 'bandwidth': 100000, 'optical.type': 'cross-connect', 'durable': True }
         h1 = self.addHost( 'h1' )
         h2 = self.addHost( 'h2' )
         s1 = self.addSwitch( 's1' )
         s2 = self.addSwitch( 's2' )
         O4 = self.addSwitch( 'O4', cls=opticalSwitch )
         O5 = self.addSwitch( 'O5', cls=opticalSwitch )
         O6 = self.addSwitch( 'O6', cls=opticalSwitch )
         self.addLink( O4, O5, cls=opticalLink, annotations=opticalAnn )
         self.addLink( O5, O6, cls=opticalLink, annotations=opticalAnn )
         self.addLink( s1, O4, cls=opticalLink, annotations=switchAnn )
         self.addLink( s2, O6, cls=opticalLink, annotations=switchAnn )
         self.addLink( h1, s1 )
         self.addLink( h2, s2 )

def switchJSON( switch ):
    configDict = {}
    configDict[ 'uri' ] = 'of:' + switch.dpid
    configDict[ 'mac' ] = quietRun( 'cat /sys/class/net/%s/address' % switch.name ).strip( '\n' ).translate( None, ':' )
    configDict[ 'hw' ] = 'PK'
    configDict[ 'mfr' ] = 'Linc'
    configDict[ 'type' ] = 'SWITCH'
    annotations = switch.params.get( 'annotations', {} )
    annotations.setdefault( 'name', switch.name )
    configDict[ 'annotations' ] = annotations
    ports = []
    for port, intf in switch.intfs.items():
        if intf.name == 'lo':
            continue
        portDict = {}
        portDict[ 'port' ] = port
        portDict[ 'type' ] = 'FIBER' if isinstance( intf.link, opticalLink ) else 'COPPER'
        intfList = [ intf.link.intf1, intf.link.intf2 ]
        intfList.remove( intf )
        portDict[ 'speed' ] = intfList[ 0 ].speed if isinstance( intf.link, opticalLink ) else 10000 # need to look at this. probably shouldnt have a default value
        ports.append( portDict )
    configDict[ 'ports' ] = ports
    return configDict

def startOE( net, controllerPort=6633 ):
    opticalJSON = {}
    linkConfig = []
    devices = []
    
    for switch in net.switches:
        if isinstance( switch, opticalSwitch ):
            devices.append( switch.json() )
        else:
            devices.append( switchJSON( switch ) )
    opticalJSON[ 'devices' ] = devices

    for link in net.links:
        if isinstance( link, opticalLink ) :
            linkConfig.append( link.json() )

    opticalJSON[ 'links' ] = linkConfig

    with open( 'Topology.json', 'w' ) as outfile:
        json.dump( opticalJSON, outfile, indent=4, separators=(',', ': ') )
    
    if quietRun( 'echo $ONOS_ROOT' ).strip( '\n' ) is None:
        error( 'Please set ONOS_ROOT environment variable!\n' )

    print quietRun( '$ONOS_ROOT/tools/test/bin/onos-oecfg ./Topology.json > TopoConfig.json', shell=True )
    info( '***creating sys.config...\n' )
    configGen = findDir( 'LINC-config-generator' )
    if not configGen:
        error( '***ERROR: please install LINC-config-generator in users home directory\n' )
    print quietRun( '%s/config_generator TopoConfig.json %s/sys.config.template localhost %d' %  ( configGen, configGen, controllerPort ), shell=True )
    lincDir = findDir( 'linc-oe2' )
    if not lincDir:
        lincDir = findDir( 'linc-oe' )
    if not lincDir:
        error( '***ERROR: Could not find linc-oe in users home directory\n' )
    print quietRun( 'cp -v sys.config %s/rel/linc/releases/1.0/' % lincDir, shell=True )
    info( '***starting linc OE...\n' )
    print quietRun( '%s/rel/linc/bin/linc start' % lincDir, shell=True )
    info( '***waiting for linc-oe to start...\n' )
    # We have to wait for all of the tap interfaces to be displayed before trying to connect to them. Need to make a method to do this.
    sleep( 5 )
    print quietRun( '$ONOS_ROOT/tools/test/bin/onos-topo-cfg localhost Topology.json', shell=True )
    info( '***adding tap interfaces to existing switches...\n' )
    for link in net.links:
        if isinstance( link, opticalLink ):
            if link.annotations[ 'optical.type' ] == 'cross-connect':
                for intf in [ link.intf1, link.intf2 ]:
                    if not isinstance( intf, opticalIntf ):
                        intfList = [ intf.link.intf1, intf.link.intf2 ]
                        intfList.remove( intf )
                        intf.node.attach( findTap( intfList[ 0 ].node, intfList[ 0 ].node.ports[ intfList[ 0 ] ] ) )
                        
    info( '***done\n' )


def stopOE():
    quietRun( 'rel/linc/bin/linc stop', shell=True )

# need a check in place if multiple paths are found
# currently only look in home directory to make the search faster
def findDir( directory ):
    "finds and returns the path of any directory in the user's home directory"
    user = quietRun( 'who am i' ).split()[ 0 ]
    homeDir = '/home/' + user
    Dir = quietRun( 'find %s -name %s' % ( homeDir, directory ) ).strip( '\n' )
    if not Dir:
        return None
    else:
        return Dir

# modify this to look in any file. by default, look in default releases/1.0 location
def findTap( node, port ):
    switch=False
    portLine = ''
    intfLines = []
    lincDir = findDir( 'linc-oe2' )
    if not lincDir:
        lincDir = findDir( 'linc-oe' )
    if not lincDir:
        error( '***ERROR: Could not find linc-oe in users home directory\n' )
        return None

    with open( '%s/rel/linc/releases/1.0/sys.config' % lincDir ) as f:
        for line in f:
            if 'tap' in line:
                intfLines.append( line )
            if node.dpid in line.translate( None, ':' ):
                switch=True
                continue
            if switch:
                if 'switch' in line:
                    switch = False
                if 'port_no,%s}' % port in line:
                    portLine = line
                    break 

    if portLine:
        m = re.search( 'port,\d+', portLine )
        port = m.group( 0 ).split( ',' )[ 1 ]
    else:
        print 'ERROR: Could not find any ports in sys.config'
        return

    for intfLine in intfLines:
        if 'port,%s' % port in intfLine:
            return re.findall( 'tap\d+', intfLine )[ 0 ]

if __name__ == '__main__':
    setLogLevel( 'info' )
    # currently this is not being used. but it should work
    net = Mininet( topo=opticalTestTopo(), controller=RemoteController )
    net.start()
    startOE( net )
    CLI( net )
    net.stop()
    stopOE()

