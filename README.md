# ziweiqi


1、工具描述：一款根据目标单位名称和备案域名ip进行资产信息收集工具，资产准确率99.9%
<br><br><br>
2、适用场景：护网比赛前期资产信息收集，单个/批量目标单位或备案域名资产的资产信息收集
<br><br><br>
3、运行环境：env 目录下一键安装点击 install_env.bat，如果运行环境有困难可以考虑使用 Windows Server 2022 Datacenter + python 3.9.11 
<br><br>
<img width="1539" height="176" alt="image" src="https://github.com/user-attachments/assets/2b55ee3a-681c-4cc1-8c37-e12ce39bd82f" />
<br><br>
4、使用方法<br>
<br>
使用的时候需要配置fofa_key 和  aiqicha_cookie <br>
<br>
<img width="1578" height="1139" alt="2" src="https://github.com/user-attachments/assets/6d27a72f-77ac-4560-a24f-26ec17b20eb6" />
<br>
5、补充<br>
<br>
5.1：目标单位名称或备案域名ip，针对hvv进行资产收集用，fofa做了cn的过滤，支持大批量目标。<br>
<br>
<img width="1573" height="1140" alt="1" src="https://github.com/user-attachments/assets/6101c94d-b1bf-45cb-8c0a-9b078ff01064" />
<br>
5.2：每次进行资产收集的时候会对上次的结果进行备份和清理。<br>
<br>
<img width="1575" height="1136" alt="image" src="https://github.com/user-attachments/assets/2b277656-da32-4b77-b223-7d3f6f693423" />
<br><br>
<img width="1393" height="778" alt="image" src="https://github.com/user-attachments/assets/91b0871a-22a6-4fd4-a55d-7b96894dc1fc" />
<br><br><img width="1485" height="441" alt="image" src="https://github.com/user-attachments/assets/8467a681-90b2-4903-b57a-4db8f9620e9a" />

<br>
<br>
5.3： 工信部批量查询备案资产（没有集成到软件里面，但可以手动批量），批量查询除开aiqicha，也可以使用工信部的ziweiqi/tools/ICP_Query/icpApi.py,大批量会封，已经做了二开，批量尽量不要超过99个。
<br>
<img width="1596" height="1085" alt="image" src="https://github.com/user-attachments/assets/82e9c5dc-723a-4c13-8741-5ebb044d5542" />
<br>
5.4 enscan做了二开资产最好不要超过200个，aiqicha会封，fofa也做了访问速率控制，速度放慢都是因为防止接口访问降低频率不被封。
<br>
<br>



