#!/usr/bin/python

'''
Notes:

This file contains classes and methods useful for integrating LincOE with Mininet, 
such as startOE, stopOE, opticalLink, and opticalSwitch

- $ONOS_ROOT ust be set
- Need to run with sudo -E to preserve ONOS_ROOT env var
- We assume LINC-Config-Generator is named LINC-Config-Generator
- We also assume linc-oe is named linc-oe
- LINC-config-generator and linc-oe must be subdirectories of the user's
  home directory

            TODO
        -----------
    - clean up files after runtime
        - maybe save the old files in a separate directory?
    - modify script to allow startOE to run before net.start()
    - add ONOS as a controller in script

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
from mininet.log import  setLogLevel, info, error, warn
import json
from mininet.link import Link, Intf
from mininet.cli import CLI

class opticalSwitch( Switch ):

    def __init__( self, name, dpid=None, allowed=True,
                  switchType='ROADM', annotations={}, **params ):
        params[ 'inNamespace' ] = False
        Switch.__init__( self, name, dpid=dpid, **params )
        self.name = name
        self.annotations = annotations
        self.allowed = allowed
        self.switchType = switchType
        self.configDict = {} # dictionary that holds all of the JSON configuration data

    def start( self, *opts, **params ):
        '''Instead of starting a virtual switch, we build the JSON
           dictionary for the emulated optical switch'''
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
        "return json configuration dictionary for switch"
        return self.configDict
    
    def terminate( self ):
        pass

class opticalLink( Link ):

    def __init__( self, node1, node2, port1=None, port2=None, allowed=True,
                  intfName1=None, intfName2=None, linkType='OPTICAL',
                  annotations={}, speed1=0, speed2=0, **params ):
        "Creates a dummy link without a virtual ethernet pair."
        self.allowed = allowed
        self.annotations = annotations
        self.linkType = linkType
        params1 = { 'speed': speed1 }
        params2 = { 'speed': speed2 }
        
        if isinstance( node1, opticalSwitch ):
            cls1 = opticalIntf
        else:
            cls1 = Intf
            # bad hack to stop error message from appearing when we try to set up intf in a packet switch, 
            # and there is no interface there( because we do not run makeIntfPair ). This way, we just set lo up
            intfName1 = 'lo'
        if isinstance( node2, opticalSwitch ):
            cls2 = opticalIntf
        else:
            cls2 = Intf
            intfName2 = 'lo'
        Link.__init__( self, node1, node2, port1=port1, port2=port2,
                       intfName1=intfName1, intfName2=intfName2, cls1=cls1,
                       cls2=cls2, params1=params1, params2=params2 )
        

    @classmethod
    def makeIntfPair( _cls, intfName1, intfName2, *args, **kwargs ):
        pass

    def json( self ):
        "build and return the json configuration dictionary for this link"
        configData = {}
        configData[ 'src' ] = ( 'of:' +  self.intf1.node.dpid + 
                                '/%s' % self.intf1.node.ports[ self.intf1 ] )
        configData[ 'dst' ] = ( 'of:' +  self.intf2.node.dpid +
                                '/%s' % self.intf2.node.ports[ self.intf2 ] )
        configData[ 'type' ] = self.linkType
        configData[ 'annotations' ] = self.annotations
        return configData

class opticalIntf( Intf ):

    def __init__( self, name=None, node=None, speed=0, 
                  port=None, link=None, **params ):
        self.node = node
        self.speed = speed
        self.port = port
        self.link = link
        self.name = name
        node.addIntf( self, port=port )
        self.params = params
        self.ip = None

    def json( self ):
        "build and return the JSON information for this interface( not used right now )"
        configDict = {}
        configDict[ 'port' ] = self.port
        configDict[ 'speed' ] = self.speed
        configDict[ 'type' ] = 'FIBER'
        return configDict

    def config( self, *args, **kwargs ):
        "dont configure a dummy interface"
        pass

def switchJSON( switch ):
    "returns the json configuration for a packet switch"
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
        portDict[ 'speed' ] = intfList[ 0 ].speed if isinstance( intf.link, opticalLink ) else 0
        ports.append( portDict )
    configDict[ 'ports' ] = ports
    return configDict


def startOE( net, controllerIP=None, controllerPort=None ):
    "Start the LINC optical emulator within a mininet instance"
    opticalJSON = {}
    linkConfig = []
    devices = []
    
    # if we are not given a controller IP or Port, we use the first found in Mininet
    if controllerIP is None:
        controllerIP = net.controllers[ 0 ].ip
    if controllerPort is None:
        controllerPort = net.controllers[ 0 ].port

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

    if not quietRun( 'echo $ONOS_ROOT' ).strip( '\n' ):
        error( 'Please set ONOS_ROOT environment variable!\n' )
        return False

    with open( 'Topology.json', 'w' ) as outfile:
        json.dump( opticalJSON, outfile, indent=4, separators=(',', ': ') )

    info( '***creating Topology file\n' )
    output = quietRun( '$ONOS_ROOT/tools/test/bin/onos-oecfg ./Topology.json > TopoConfig.json', shell=True )
    if output:
        error( '***ERROR: error creating topology file: %s ' % output )
        return False

    configGen = findDir( 'LINC-config-generator' )
    if not configGen:
        error( '***ERROR: please install LINC-config-generator in users home directory\n' )
        return False

    info( '***creating sys.config...\n' )
    output = quietRun( '%s/config_generator TopoConfig.json %s/sys.config.template %s %s'
                    % ( configGen, configGen, controllerIP, controllerPort ), shell=True )
    if output:
        error( '***ERROR: error creating sys.config file: %s ' % output )
        return False

    lincDir = findDir( 'linc-oe2' )
    if not lincDir:
        lincDir = findDir( 'linc-oe' )
    if not lincDir:
        error( '***ERROR: Could not find linc-oe in users home directory\n' )
        return False

    output = quietRun( 'cp -v sys.config %s/rel/linc/releases/1.0/' % lincDir, shell=True ).strip( '\n' )
    info( '***moving sys.config: ', output + '\n' )
    info( '***starting linc OE...\n' )
    output = quietRun( '%s/rel/linc/bin/linc start' % lincDir, shell=True )
    if output:
        error( '***ERROR: LINC-OE: %s' % output + '\n' )
        quietRun( '%s/rel/linc/bin/linc stop' % lincDir, shell=True )
        return False
    
    info( '***waiting for linc-oe to start...\n' )
    waitStarted( net )
    
    info( '***pushing Topology file to ONOS\n' )
    output = quietRun( '$ONOS_ROOT/tools/test/bin/onos-topo-cfg %s Topology.json' % controllerIP, shell=True )
    # successful output contains the two characters '{}'
    # if there is more output than this, there is an issue
    if output.strip( '{}' ):
        warn( '***WARNING: could not push topology file to ONOS: %s' % output )
    
    info( '***adding tap interfaces to existing switches...\n' )
    for link in net.links:
        if isinstance( link, opticalLink ):
            if link.annotations[ 'optical.type' ] == 'cross-connect':
                for intf in [ link.intf1, link.intf2 ]:
                    if not isinstance( intf, opticalIntf ):
                        intfList = [ intf.link.intf1, intf.link.intf2 ]
                        intfList.remove( intf )
                        intf2 = intfList[ 0 ]
                        intf.node.attach( findTap( intf2.node, intf2.node.ports[ intf2 ] ) )
                        
def waitStarted( net, timeout=None ):
    "wait until all tap interfaces are available"
    tapCount = 0
    time = 0
    for link in net.links:
        if isinstance( link, opticalLink ):
            if link.annotations[ 'optical.type' ] == 'cross-connect':
                tapCount += 1
    
    while True:
        if str( tapCount ) == quietRun( 'ip addr | grep tap | wc -l', shell=True ).strip( '\n' ):
            return True
        if timeout:
            if time >= timeout:
                error( '***ERROR: Linc OE did not start within %s seconds' % timeout )
                return False
            time += .5
        sleep( .5 )

def stopOE():
    "stop the optical emulator"
    lincDir = findDir( 'linc-oe' )
    quietRun( '%s/rel/linc/bin/linc stop' % lincDir, shell=True )

def findDir( directory ):
    "finds and returns the path of any directory in the user's home directory"
    user = quietRun( 'who am i' ).split()[ 0 ]
    homeDir = '/home/' + user
    Dir = quietRun( 'find %s -name %s' % ( homeDir, directory ) ).strip( '\n' )
    DirList = Dir.split( '\n' )
    if not Dir:
        return None
    elif len( DirList ) > 1 :
        warn( '***WARNING: found multiple instances of %s. using %s\n'
                 % ( directory, DirList[ 0 ] ) )
        return DirList[ 0 ]
    else:
        return Dir

def findTap( node, port, path=None ):
    '''utility function to parse through a sys.config
       file to find tap interfaces for a switch'''
    switch=False
    portLine = ''
    intfLines = []

    if path is None:
        lincDir = findDir( 'linc-oe' )
        if not lincDir:
            error( '***ERROR: Could not find linc-oe in users home directory\n' )
            return None
        path = '%s/rel/linc/releases/1.0/sys.config' % lincDir

    with open( path ) as f:
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

if __name__ == '__main__':
    setLogLevel( 'info' )
    net = Mininet( topo=opticalTestTopo(), controller=RemoteController )
    net.start()
    startOE( net )
    CLI( net )
    net.stop()
    stopOE()

