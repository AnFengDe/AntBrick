# encoding: UTF-8

from __future__ import absolute_import
from vnpy.trader import vtConstant
from .coinbeneGateway import CoinbeneGateway

gatewayClass = CoinbeneGateway
gatewayName = 'COINBENE'
gatewayDisplayName = 'COINBENE'
gatewayType = vtConstant.GATEWAYTYPE_BTC
gatewayQryEnabled = False
