# encoding: UTF-8

from __future__ import absolute_import
from vnpy.trader import vtConstant
from .ucoinGateway import UcoinGateway

gatewayClass = UcoinGateway
gatewayName = 'UCOIN'
gatewayDisplayName = 'UCOIN'
gatewayType = vtConstant.GATEWAYTYPE_BTC
gatewayQryEnabled = False
