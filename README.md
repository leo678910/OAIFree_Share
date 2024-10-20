## 项目介绍  
基于始皇的OAIFree服务，搭建一个共享站，方便给自己的小伙伴们使用  

## 页面预览  

### 登录页  
默认管理员账户
```
账号：admin
密码：password
```
请登录后在用户管理中更改用户名和密码  
![image](https://github.com/user-attachments/assets/d6503e6c-6267-48c2-a3fb-8d28de77d0be)

---
### 共享页  
点击公告中的小图标可以跳转到后台管理(仅限管理员)  
根据后台的Token数量生成对应数量的盒子  
![image](https://github.com/user-attachments/assets/9fa82f95-496e-4ae5-8015-c304da6bfa35)

---
### Token管理页  
可对Refresh Token进行修改  
支持自动/手动刷新Access Token  
显示刷新失败的Refresh Token信息  
![image](https://github.com/user-attachments/assets/198a30e2-b8f9-4ac7-960f-3ad84a5a8a2d)

---
### 用户管理页 
支持新增、删除、修改用户信息  
![image](https://github.com/user-attachments/assets/a2a31fd6-2984-47c1-9616-227db7a16255)
![image](https://github.com/user-attachments/assets/62cb9e30-6b05-4fb5-b507-a822e1f2a027)

## 部署 

### Linux  
###  更新服务器并安装依赖
首先更新系统并安装一些必要的工具：

```
sudo apt update
sudo apt upgrade -y
```
### 安装 Python 及其依赖
安装 Python3 和 pip： 确保系统中安装了 Python3 和 pip（Python 的包管理工具）。

```
sudo apt install python3 python3-pip python3-venv -y
```
### 设置虚拟环境
创建虚拟环境： 为了避免与系统的 Python 环境冲突，建议使用虚拟环境。

```
python3 -m venv venv
```
激活虚拟环境：

```
source venv/bin/activate
```
### 安装 Flask 和项目依赖
```
pip install flask requests gunicorn
```

### 运行 Flask 应用程序
使用 gunicorn 来运行
```
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
-w 4：使用 4 个 worker 进程。
-b 0.0.0.0:8000：监听所有接口上的 8000 端口。
