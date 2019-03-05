# By Traders, For Traders.


---

### 简介

vn.py是基于Python的开源量化交易系统开发框架，起源于国内私募基金的自主交易系统。2015年1月项目正式发布，在开源社区4年持续不断的贡献下，已经从早期的交易API接口封装，一步步成长为一套全功能量化交易平台。随着业内关注度的上升，用户群体也日渐多样化，包括：私募基金、证券自营和资管、期货资管和子公司、高校研究机构、专业个人投资者等等。

---

### 项目结构

1. 全功能量化交易平台（vnpy.trader），整合了多种交易接口，并针对具体策略算法和功能开发提供了简洁易用的API，用于快速构建交易员所需的量化交易应用。

    * 经过开源社区大量用户实盘检验，做到开箱即用的各类量化策略交易应用（包括逻辑层和界面层）：
    
        * AlgoTrading：算法交易模块，提供多种常用的智能交易算法：TWAP、Sniper、BestLimit、Iceberg、Arbitrage等等，支持数据库配置保存、CSV文件加载启动以及RPC跨进程算法交易服务

        * RiskManager：事前风控模块，负责在交易系统将任何交易请求发出到柜台前的一系列标准检查操作，支持用户自定义风控规则的扩展

2. Python交易API接口封装（vnpy.api），提供上述交易接口的底层对接实现

3. 简洁易用的事件驱动引擎（vnpy.event），作为事件驱动型交易程序的核心

6. 关于vn.py项目的应用演示（examples），对于新手而言可以从这里开始学习vn.py项目的使用方式

. [社区论坛](http://www.vnpy.com)和[知乎专栏](http://zhuanlan.zhihu.com/vn-py)，内容包括vn.py项目的开发教程和Python在量化交易领域的应用研究等内容

10. 官方交流QQ群262656087，管理严格（定期清除长期潜水的成员），入群费将捐赠给vn.py社区基金

---
### 环境准备

**Windows**

1. 支持的操作系统：Windows 7/8/10/Server 2008
2. 安装[MongoDB](https://www.mongodb.org/downloads#production)，并[将MongoDB配置为系统服务](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-windows/#configure-a-windows-service-for-mongodb-community-edition)
3. 安装python3.7或其他python3.x版本
4. 安装[Visual C++ Redistributable Packages for VS2013 x86版本](https://support.microsoft.com/en-us/help/3138367/update-for-visual-c-2013-and-visual-c-redistributable-package)

git clone https://github.com/AnFengDe/AntBrick/tree/python3
pip install -r requirements.txt

**Ubuntu**

请参考项目wiki中的[教程](https://github.com/vnpy/vnpy/wiki/Ubuntu%E7%8E%AF%E5%A2%83%E5%AE%89%E8%A3%85)。

---
### 项目运行


**关于TA-Lib安装**

Ubuntu上安装到talib时若遭遇'Permission denied'错误，请在install.sh运行完成后，在Terminal中输入以下命令安装：

```
sudo /home/vnpy/anaconda2/bin/conda install -c quantopian ta-lib=0.4.9
```

其中"/home/vnpy/anaconda2/"是你的Anaconda安装路径。


---
### Quick Start


1. 井通注册账号**

2. 找到vn.py应用示例目录examples，打开examples\CryptoTrader\GatewayConfig\JCC_connect.json，修改账号、密钥）
```
{
	"account": "jn5Cz1E468HLBF1ESc6PmqG2UxdBoDBHpn",  # 账号
	"secretKey": "sp5o1RYX54utAfzRqsxEA1S4gvHFU",     # 私钥
	"sessionCount": 3,
	"symbols": ["SWT-CNY","VCC-CNY"]                  # 交易对,会在屏幕下单区域显示
} 
```
3. 启动程序为examples\CryptoTrader\run.py，可在pyCharm中运行

4.启动后点击**_**_系统_**_--》**_连接JCC_**,即可连接JCC服务器

---

### 开发工具推荐

* [Pycharm]最流行的python开发工具

* [Visual Studio Code](https://code.visualstudio.com/)：针对编程的文本编辑器，方便阅读项目中的Python、C++、Markdown文件

* [Visual Studio 2013](https://www.visualstudio.com/en-us/downloads/download-visual-studio-vs.aspx)：这个就不多说了（作者编译API封装用的是2013版本）

---
### 其他内容

* [获取帮助](https://github.com/vnpy/vnpy/blob/dev/docs/SUPPORT.md)
* [社区行为准侧](https://github.com/vnpy/vnpy/blob/dev/docs/CODE_OF_CONDUCT.md)
* [Issue模板](https://github.com/vnpy/vnpy/blob/dev/docs/ISSUE_TEMPLATE.md)
* [PR模板](https://github.com/vnpy/vnpy/blob/dev/docs/PULL_REQUEST_TEMPLATE.md)

* [服务器文档]https://github.com/JCCDex/jcc_server_doc
* [签名文档]https://github.com/JCCDex/jcc_rpc

---
### License
MIT
