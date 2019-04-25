# encoding: UTF-8

from __future__ import absolute_import
from vnpy.trader import vtConstant
from vnpy.trader.gateway.coinwGateway.coinwGateway import CoinwGateway

gatewayClass = CoinwGateway
gatewayName = 'Coinw'
gatewayDisplayName = 'Coinw'
gatewayType = vtConstant.GATEWAYTYPE_BTC
gatewayQryEnabled = False
