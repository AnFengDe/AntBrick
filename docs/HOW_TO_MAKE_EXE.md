# 如何制作EXE文件

*首先安装pyinstaller

* 开发时用import vnpy.trader.这样的方法来导入模块，而不是import .abc,否则exe执行会有问题

* pyinstaller默认只收集py文件，所以.json,.ico都需要打包到datas,
第一个路径是你的机器绝对路径，第二个是运行时的相对路径
datas=[('D:\\jcc\\AntBrick\\vnpy\\trader\\app\\brickTrade\\*.json','vnpy\\trader\\app\\brickTrade'),

* spec中的两个name是可执行文件的名字和目录名字，可以自行修改

* 打包命令是 pyinstaller run.spec,打包成功会在dist目录下生成对应的CfgData目录，
该目录可以拷贝到其他windows机器运行

* 如果打包提示有很多dll找不到，可以用以下方式加入到spec文件中
             binaries=[('C:\\Windows\\SysWOW64\\api-ms-win-crt-runtime-l1-1-0.dll','dll'),
             ('C:\\Windows\SysWOW64\\api-ms-win-crt-heap-l1-1-0.dll','dll'),
             
* 新的配置文件都在CfgData目录下，根据需要修改即可