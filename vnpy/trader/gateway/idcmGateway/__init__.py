# encoding: UTF-8

from __future__ import absolute_import
from vnpy.trader import vtConstant
from .idcmGateway import IdcmGateway

gatewayClass = IdcmGateway
gatewayName = 'IDCM'
gatewayDisplayName = 'IDCM'
gatewayType = vtConstant.GATEWAYTYPE_BTC
gatewayQryEnabled = False
