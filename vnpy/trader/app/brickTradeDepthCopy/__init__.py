# encoding: UTF-8

from __future__ import absolute_import
from .brickTradeEngine import BrickTradeEngine
from .uiBrickTradeWidget import BrickTradeManager

appName = 'BrickTradeDepthCopy'
appDisplayName = '深度复制搬砖'
appEngine = BrickTradeEngine
appWidget = BrickTradeManager
appIco = 'at.ico'
