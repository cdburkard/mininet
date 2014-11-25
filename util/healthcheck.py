#!/usr/bin/python

"""

Health Check for Mininet:

options:
  - a( to conform with install.sh ): run the comprehensive health check and report results
  - c: check which controllers are installed, where they are installed, and if they are functional
  - n: check that mount and network namespaces are enabled, also check 'ip netns'
  - f: attempt to fix broken dependencies( requires either a, c, n, or s )
  - s: check which switches are installed, where they are installed, and if they are functional
  - d [ cmd ]: diagnose issue with specific mininet command

"""
from mininet.util import quietRun
from subprocess import check_output
from mininet.log import setLogLevel, error, warn, info, output

def checkUtil( command, verbose=False ):
    utilLoc = quietRun( 'which %s' % command ).strip( '\n' )
    info( '    %s: ----------------> ' % command )
    if utilLoc:
        info( 'installed\n' )
        return True
    else:
        info( 'missing!\n' )
        return False
        

def checkSwitches():
    switchMapping = { 'User Switch': [ 'ofprotocol', 'ofdatapath' ],
                      'OVS Switch': [ 'ovs-vsctl', 'ovsdb-server', 'ovs-vswitchd' ],
                      'IVS Switch': [ 'ivs-ctl' ] }

    for switch, utils in switchMapping.items():
        info( switch + ':\n' )
        for util in utils:
            checkUtil( util )

def checkControllers():
    controllerMapping = { 'ovs': [ 'ovs-controller', 'test-controller' ],
                          'reference': [ 'controller' ] }
    
    for controller, utils in controllerMapping.items():
        info( controller + ':\n' )
        for util in utils:
            checkUtil( util )

setLogLevel( 'info' )
info( '\nSWITCHES:\n\n' )
checkSwitches()
info( '\nCONTROLLERS:\n\n' )
checkControllers()
