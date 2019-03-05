# encoding: UTF-8

from __future__ import absolute_import
from vnpy.trader import vtConstant
from .jccGateway import JccGateway

gatewayClass = JccGateway
gatewayName = 'JCC'
gatewayDisplayName = 'JCC'
gatewayType = vtConstant.GATEWAYTYPE_BTC
gatewayQryEnabled = False
