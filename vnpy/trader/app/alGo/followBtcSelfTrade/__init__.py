# encoding: UTF-8

from __future__ import absolute_import
from .followBtcEngine import FollowBtcEngine
from .uiFollowBtcWidget import FollowBtcEngineManager

appName = 'FollowBtcSelfTrade'
appDisplayName = '跟随BTC刷单'
appEngine = FollowBtcEngine
appWidget = FollowBtcEngineManager
appIco = 'at.ico'
