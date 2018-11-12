"""Parent component for Geeklink MiniPi devices
"""

import logging
import voluptuous as vol
import socket
import json
import threading
 
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
 
_LOGGER = logging.getLogger(__name__)

DOMAIN = "minipi"
ENTITYID = DOMAIN + ".pi1"
BUFSIZE = 2048

# 记录minipi的attr
attr = {"icon": "mdi:pi-box",
        "username": [],
        "addr": '',
        "home_id": '',
        "devices": [],
        "device_type_names":[],
        "device_sub_ids":[]}
            
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

def getbroadcast():
    # 获取geeklink设备广播包
    d = ''
    addr = ''
    sserver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sserver.bind(('0.0.0.0',9200))
    sserver.settimeout(10)
    try:
        data, addr = sserver.recvfrom(8196)
    except Exception as e:
        _LOGGER.error(e)
    finally:
        sserver.close()
    # 广播包转为json
    if data != '':
        d = data[5:]
#    _LOGGER.warning(data)
    jdata = json.loads(d)
    return addr, jdata
    
def devicelinkreq(addr, home_id, username):
    # 连接请求
    sclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sclient.bind(('0.0.0.0',19200))
    sclient.settimeout(5)
    sdata = b'\xff\xee\x88\x00\x61' + b'{"home_id":"' + home_id.encode('ascii') + b'","method":"deviceLinkReq":"user_name":"' + username.encode('ascii') + b'"}'
    sclient.sendto(sdata, addr)
    try:
        data, addr = sclient.recvfrom(8196)
    except Exception as e:
        _LOGGER.error(repr(e))
    finally:
        sclient.close()
    # 转为json
    if data != '':
        d = data[5:]
#    _LOGGER.warning(data)
    jdata = json.loads(d)
    return addr, jdata

def devicestategetreq(addr, session):
    # 发送deviceStateGetReq
    sclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sclient.bind(('0.0.0.0',19200))
    sclient.settimeout(5)
    sdata = b'\xff\xee\x88\x00\x2f' +  b'{"method":"deviceStateGetReq","session":"' + session.encode('ascii') + b'"}'
    sclient.sendto(sdata, addr)
    try:
        data, addr = sclient.recvfrom(8196)
    except Exception as e:
        _LOGGER.error(repr(e))
    finally:
        sclient.close()
    # 转为json
    if data != '':
        d = data[5:]
#    _LOGGER.warning(data)
    jdata = json.loads(d)
    return addr, jdata
    
def devicestatectrlreq(addr, session, subid, ircode, value):
    # 发送红外码控制设备
    sclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sclient.bind(('0.0.0.0',19200))
    sclient.settimeout(5)
    sdata = b'\xff\xee\x88\x00\xee' +  b'{"irCode":"' + ircode.encode('ascii') + b'","method":"deviceStateCtrlReq","session":"' + session.encode('ascii') + b'","sub_id":' + subid.encode('ascii') + b',"value":"' + value.encode('ascii') + b'"}'
    _LOGGER.warning(sdata)
    sclient.sendto(sdata, addr)
    try:
        data, addr = sclient.recvfrom(8196)
    except Exception as e:
        _LOGGER.error(repr(e))
    finally:
        sclient.close()
    # 转为json
    if data != '':
        d = data[5:]
#    _LOGGER.warning(data)
    jdata = json.loads(d)
    return addr, jdata

def setup(hass, config):
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    attr['username'] = username

    state = 'error'
    
    try:
        # 获取广播数据包，以获得homeID
        addr, ujson_broadcast = getbroadcast()
               
        # 发送连接请求，以获得sessionID
        addr, ujson_linkresp = devicelinkreq(addr, ujson_broadcast['home.id'], username)
        
        # 发送deviceStateGetReq，获取关联设备信息
        addr, ujson_stategetresp = devicestategetreq(addr, ujson_linkresp['session'])
        
        state = ujson_stategetresp['state']
                
    except Exception as e:
        _LOGGER.error(repr(e))
        state = 'error'
    else:
        attr['addr'] = addr
        attr['home_id'] = ujson_stategetresp['home_id']
        attr['devices'] = ujson_stategetresp['devices']
    if state == 'ok':
        for device in attr['devices']:
            attr['device_type_names'] = attr['device_type_names'] + [device['name']]
            attr['device_sub_ids'] = attr['device_sub_ids'] + [device['sub_id']]
    hass.states.set(ENTITYID, state, attributes=attr)
    
    def sendircode(service):
    # 发送红外码hass服务
        def sendircode_sub():
            try:
                # 获取服务参数
                ircode = service.data['ircode']
                sub_id = service.data['sub_id']
                value = service.data['value']
                # 请求连接
                addr, ujson_linkresp = devicelinkreq(attr['addr'], attr['home_id'], attr['username'])
                # 发送ircode
                devicestatectrlreq(attr['addr'], ujson_linkresp['session'], sub_id, ircode, value)
            except Exception as e:
                _LOGGER.error(repr(e))          
        threading.Thread(target=sendircode_sub).start()
    hass.services.register(DOMAIN, 'SendIRCode', sendircode)

    return True
    
