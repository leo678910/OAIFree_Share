import json
import requests
from datetime import datetime, timedelta
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import uuid
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)

# 读取 config.json 文件
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# 将配置项设置为 Flask 的 config
app.config.update(config)

# 读取 chatToken.json 文件
def load_retoken():
    try:
        with open('json/chatToken.json', 'r') as f:
            retokens = json.load(f)
        return retokens
    except FileNotFoundError:
        return []

# 保存更新后的 chatToken.json 文件
def save_retoken(updated_tokens):
    with open('json/chatToken.json', 'w') as f:
        json.dump(updated_tokens, f, indent=4)


# 写入 failed_tokens.json 文件
def save_failed_tokens(failed_tokens):
    with open('json/failed_tokens.json', 'w') as f:
        json.dump(failed_tokens, f, indent=4)

# 读取刷新历史
def load_refresh_history():
    try:
        with open('json/refresh_history.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []



# 保存刷新历史
def save_refresh_history(history):
    with open('json/refresh_history.json', 'w') as f:
        json.dump(history, f, indent=4)

# 加载用户表
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
# 保存用户信息
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


#-----------------------------------------chatgpt相关函数------------------------------------------------------
# 刷新 access_token 的主函数
def refresh_access_tokens():
    # 读取 refresh_token 列表
    refresh_tokens = load_retoken()

    failed_tokens = []  # 用于记录获取 access_token 失败的邮箱和 refresh_token

    # 遍历 refresh_token 列表
    for token_info in refresh_tokens:
        email = token_info['email']
        refresh_token = token_info['refresh_token']

        # 如果 refresh_token 为空，跳过这一行
        if not refresh_token:
            continue

        try:
            # 使用 POST 请求通过 refresh_token 获取 access_token
            response = requests.post(
                "https://token.oaifree.com/api/auth/refresh",
                data={"refresh_token": refresh_token}
            )
            response_data = response.json()

            access_token = response_data.get("access_token")
            if access_token:  # 如果成功获取到 access_token
                # 更新 access_token 和状态为 True
                token_info['access_token'] = access_token
                token_info['status'] = True
            else:
                # 如果获取失败，设置状态为 False
                token_info['status'] = False
                failed_tokens.append(token_info)
        
        except Exception as e:
            # 捕获请求错误并记录失败的 token，状态为 False
            token_info['status'] = False
            failed_tokens.append(token_info)

    # 保存更新后的 retoken 数据
    save_retoken(refresh_tokens)

    # 如果有失败的 token，记录到 failed_tokens.json
    save_failed_tokens(failed_tokens)

    return refresh_tokens


# 获取share token
def register_token(access_token, unique_name, expire_in=0, show_userinfo=True, gpt35_limit=-1, 
                   gpt4_limit=-1, reset_limit=False, show_conversations=False, site_limit="", 
                   temporary_chat=False):
    """
    注册共享令牌的函数。

    :param access_token: 用户的访问令牌
    :param unique_name: 独一无二的共享令牌名称
    :param expire_in: 共享令牌的过期秒数，默认为0
    :param show_userinfo: 是否显示用户信息，默认为False
    :param gpt35_limit: GPT-3.5模型的使用限制，默认为-1表示不限制
    :param gpt4_limit: GPT-4模型的使用限制，默认为-1表示不限制
    :param reset_limit: 是否重置使用限制，默认为False
    :param show_conversations: 是否显示对话记录，默认为True
    :param site_limit: 站点使用限制，默认为空字符串，表示不限制
    :param temporary_chat: 是否开启临时聊天功能，默认为True

    :return: token_key (str)，注册成功后返回的共享令牌 key
    """
    
    url = 'https://chat.oaifree.com/token/register'
    
    # 数据 payload
    data = {
        "access_token": access_token,
        "unique_name": unique_name,
        "expire_in": expire_in,
        "show_userinfo": show_userinfo,
        "gpt35_limit": gpt35_limit,
        "gpt4_limit": gpt4_limit,
        "reset_limit": reset_limit,
        "show_conversations": show_conversations,
        "site_limit": site_limit,
        "temporary_chat": temporary_chat
    }

    # 发起 POST 请求
    response = requests.post(url, headers={'Content-Type': 'application/x-www-form-urlencoded'}, data=data)

    # 获取返回的共享令牌 key
    token_key = response.json().get("token_key")

    return token_key

# 获取登陆链接
def getoauth(token):
    domain = app.config.get('domain')
    share_token = token 
    
    url = f'https://{domain}/api/auth/oauth_token'
    headers = {
        'Origin': f'https://{domain}',
        'Content-Type': 'application/json'
    }
    data = {
        'share_token': share_token
    }
    
    response = requests.post(url, headers=headers, json=data)
    loginurl = response.json().get('login_url')
    return loginurl


app.secret_key = app.config.get('secret_key')  # 用于加密 session


# ---------------------------------------------------登录登出 认证装饰器---------------------------------------------------------
# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_users()
        user = next((user for user in users if user['username'] == username), None)
        
        if user and check_password_hash(user['password'], password):
            # 登录成功，存储用户信息到session
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash('登录成功！', 'success')
            
            # 如果是管理员，跳转到管理页面，否则跳转到首页
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('index'))
        else:
            flash('用户名或密码错误，请重试。', 'danger')
    
    return render_template('login.html')

# 登出路由
@app.route('/logout')
def logout():
    session.clear()
    flash('已成功登出。', 'success')
    return redirect(url_for('login'))

# 验证是否登录的装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('请先登录。', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 验证是否为管理员的装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('请先登录。', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('需要管理员权限。', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


#------------------------------------------------------共享页相关-------------------------------------------------------

# 主页路由，根据 有效的账号数量 生成相应数量的 div 盒子
@app.route('/')
@login_required
def index():
    # 读取 chatToken.json 中的 access_tokens
    tokens = load_retoken()
    
    # 创建两个列表分别存储PLUS和普通账号
    plus_tokens = []
    normal_tokens = []
    
    # 遍历所有token并分组
    for idx, token in enumerate(tokens):
        if token['status']:  # 如果token有效
            token_info = {
                'index': idx,
                'type': token.get('type', 'unknown'),
                'PLUS': token.get('PLUS', 'false')
            }
            
            # 根据PLUS状态分组
            if token_info['PLUS'].lower() == 'true':
                plus_tokens.append(token_info)
            else:
                normal_tokens.append(token_info)
    
    # 按顺序合并两个列表，PLUS账号在前
    valid_tokens = plus_tokens + normal_tokens


    # 渲染模板,传递有效token的详细信息
    return render_template(
        'index.html',
        valid_tokens=valid_tokens,  # 传递排序后的token列表
        plus_count=len(plus_tokens),  # 传递PLUS账号数量
        normal_count=len(normal_tokens)  # 传递普通账号数量
    )



# 定义一个路由，用于处理 UNIQUE_NAME 的提交
@app.route('/submit_name', methods=['POST'])
@login_required
def submit_name():
    data = request.json
    unique_name = data.get('unique_name')
    index = data.get('index')

   
    tokens = load_retoken()

    # 获取所有有效的 access_token 列表
    valid_tokens = tokens

    # 确保 index 是有效的索引
    if index and 1 <= index <= len(valid_tokens):
        # 获取对应的 access_token
        token_info = valid_tokens[index - 1]
        access_token = token_info['access_token']

        # 注册 token 并获取对应的 token_key
        token_key = register_token(access_token, unique_name)
        print(token_key)
        if not token_key:
            # 更新 chatToken.json 中对应条目的 status 为 false
            for token in tokens:
                if token['access_token'] == access_token:
                    token['status'] = False
                    break
            
            # 保存更新后的 tokens 到 chatToken.json
            save_retoken(tokens)

            return jsonify({
                "status": "error",
                "message": "账号失效了，换一个吧"
            }), 400

        # 获取 OAuth 登录 URL
        logurl = getoauth(token_key)
        return jsonify({
            "status": "success",
            "login_url": logurl
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid index."
        }), 400


#------------------------------------------------------定时任务  tokens刷新-------------------------------------

AUTO_REFRESH_CONFIG_FILE = 'json/auto_refresh_config.json'

# 获取定时任务信息
def load_auto_refresh_config():
    try:
        with open(AUTO_REFRESH_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"auto_refresh_enabled": False, "refresh_interval_days": 1, "next_refresh_time": None}
# 保存定时任务信息
def save_auto_refresh_config(config):
    with open(AUTO_REFRESH_CONFIG_FILE, 'w') as f:
        json.dump(config, f)



def is_main_process():
    import os
    return os.environ.get('WERKZEUG_RUN_MAIN') != 'true'

current_timer = None
timer_lock = threading.Lock()

def schedule_next_refresh():
    if not is_main_process():
        print("在 reloader 进程中，跳过定时器设置")
        return
        
    global current_timer
    config = load_auto_refresh_config()
    
    with timer_lock:
        if config['auto_refresh_enabled']:
            if current_timer:
                current_timer.cancel()
                
            next_refresh = datetime.now() + timedelta(days=config['refresh_interval_days'])
            config['next_refresh_time'] = next_refresh.isoformat()
            save_auto_refresh_config(config)

            current_timer = threading.Timer(
                (next_refresh - datetime.now()).total_seconds(), 
                auto_refresh_tokens
            )
            current_timer.start()

def auto_refresh_tokens():

    print('开始自动刷新')
    new_access_tokens = refresh_access_tokens()

    # 更新刷新历史
    update_refresh_history(len(new_access_tokens))

    # 添加延时，确保两次刷新之间有足够间隔
    time.sleep(2)  # 等待1秒

    # 刷新完成后，调度下一次刷新
    schedule_next_refresh()

# 更新刷新历史
def update_refresh_history(token_count):

    history = load_refresh_history()

    history.append({
        "timestamp": datetime.now().isoformat(),
        "token_count": token_count
    })

    # 保留最近的 5 条记录
    history = history[-5:]

    save_refresh_history(history)

# 设定定时任务
@app.route('/set_auto_refresh', methods=['POST'])
@admin_required
def set_auto_refresh():
    data = request.json
    config = load_auto_refresh_config()

    # 取消现有的定时任务
    config['auto_refresh_enabled'] = data['enabled']
    config['refresh_interval_days'] = data['interval']
    save_auto_refresh_config(config)

    if config['auto_refresh_enabled']:
        schedule_next_refresh()

    return jsonify({"status": "success", "message": "自动刷新设置已更新"})

# 加载定时任务配置信息
@app.route('/get_auto_refresh_config', methods=['GET'])
def get_auto_refresh_config():
    config = load_auto_refresh_config()
    return jsonify(config)

# 在应用启动时调用这个函数
def init_auto_refresh():
    if not is_main_process():
        print("在 reloader 进程中，跳过定时器初始化")
        return
        
    print(f"在主进程中初始化自动刷新, 当前时间: {datetime.now()}")
    config = load_auto_refresh_config()

    if config['auto_refresh_enabled'] and config['next_refresh_time']:
        next_refresh = datetime.fromisoformat(config['next_refresh_time'])
        
        if next_refresh > datetime.now():
            delay_seconds = (next_refresh - datetime.now()).total_seconds()
            print(f"设置初始定时器, 延迟秒数: {delay_seconds}")
            
            global current_timer
            with timer_lock:
                current_timer = threading.Timer(delay_seconds, auto_refresh_tokens)
                current_timer.start()
        else:
            schedule_next_refresh()

# 在应用启动时调用
init_auto_refresh()

# 手动刷新access token
@app.route('/refresh_tokens', methods=['POST'])
@admin_required
def refresh_tokens():
    try:
        # 调用刷新 access_token 的函数
        new_access_tokens = refresh_access_tokens()
        update_refresh_history(len(new_access_tokens))
        
        return jsonify({
            "status": "success",
            "access_tokens": new_access_tokens
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# -----------------------------------------------------管理页相关路由----------------------------


# Admin 主页路由
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():

    if request.method == 'GET':
        # 加载并显示 chatToken.json 文件中的内容
        retokens = load_retoken()
        return render_template('GPT.html', retokens=retokens)

    if request.method == 'POST':
        # 获取更新后的 retoken 数据
        new_retokens = request.json.get('retokens')
        
        # 如果数据格式有效，保存到文件
        if new_retokens:
            save_retoken(new_retokens)
            return jsonify({"status": "success", "message": "chatToken.json 已更新！"}), 200
        else:
            return jsonify({"status": "error", "message": "无效的数据格式！"}), 400

# 加载刷新历史
@app.route('/refresh_history', methods=['GET'])
@admin_required
def get_refresh_history():
    refresh_history = load_refresh_history()
    return jsonify({
        "status": "success",
        "history": refresh_history
    }), 200

# 加载失败Refresh Token
@app.route('/get_failed_tokens')
@admin_required
def get_failed_tokens():
    try:
        with open('json/failed_tokens.json', 'r') as file:
            failed_tokens = json.load(file)
        return jsonify(failed_tokens), 200
    except FileNotFoundError:
        return jsonify([]), 200  # 如果文件不存在，返回空列表
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in failed_tokens.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# 加载Refresh Token
@app.route('/get_tokens')
@admin_required
def get_tokens():
    try:
        with open('json/chatToken.json', 'r') as file:
            tokens = json.load(file)
        return jsonify(tokens), 200
    except FileNotFoundError:
        return jsonify([]), 200  # 如果文件不存在，返回空列表
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in tokens.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#-----------------------------------------------------------GPT账号管理相关-----------------------------------------

# 添加新账号
@app.route('/api/tokens', methods=['POST'])
@admin_required
def create_tokens():
    data = request.get_json()
    tokens = load_retoken()
    
    # 检查账号是否已存在
    if any(token['email'] == data['email'] for token in tokens):
        return jsonify({'success': False, 'message': '该账号已存在'}), 400
    
    new_token = {
        'email': data['email'],
        'refresh_token': data['ReToken'],
        'access_token': data['AcToken'],
        'status': True,
        'type':"GPT",
        'PLUS': data['PLUS']
    }
    
    tokens.append(new_token)
    save_retoken(tokens)
    
    return jsonify({'success': True, 'message': '用户创建成功'})

# 更新账号信息
@app.route('/api/tokens/<email>', methods=['PUT'])
@admin_required
def update_token(email):
    data = request.get_json()
    tokens = load_retoken()
    
    token_index = next((i for i, token in enumerate(tokens) if token['email'] == email), None)
    if token_index is None:
        return jsonify({'success': False, 'message': '账号不存在'}), 404

    
    # 如果提供了邮箱，则更新邮箱
    if data.get('ReToken'):
        tokens[token_index]['email'] = data['email']
    
    # 如果提供了ReToken，则更新ReToken
    if data.get('ReToken'):
        tokens[token_index]['refresh_token'] = data['ReToken']
    else:
        tokens[token_index]['refresh_token'] = ''

    # 如果提供了AcToken，则更新AcToken
    if data.get('AcToken'):
        tokens[token_index]['access_token'] = data['AcToken']
        tokens[token_index]['status'] = True
    else:
        tokens[token_index]['access_token'] = ''
    if data.get('PLUS'):
        tokens[token_index]['PLUS'] = data['PLUS']
    save_retoken(tokens)
    return jsonify({'success': True, 'message': '账号更新成功'})

# 删除用户
@app.route('/api/tokens/<email>', methods=['DELETE'])
@admin_required
def delete_token(email):
    toekns = load_retoken()
    
    # 过滤掉要删除的用户
    updated_email = [token for token in toekns if token['email'] != email]
    
    if len(updated_email) == len(toekns):
        return jsonify({'success': False, 'message': '账号不存在'}), 404
    
    save_retoken(updated_email)
    return jsonify({'success': True, 'message': '账号删除成功'})



# ------------------------------------------------------用户管理部分------------------------------------------------
USERS_FILE = 'json/user.json'

@app.route('/user')
@admin_required
def user_management():
    return render_template('user_management.html')



# 获取所有用户
@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = load_users()
    # 返回用户列表时不包含密码信息
    return jsonify([{k: v for k, v in user.items() if k != 'password'} for user in users])

# 创建新用户
@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    users = load_users()
    
    # 检查用户名是否已存在
    if any(user['username'] == data['username'] for user in users):
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    new_user = {
        'id': str(uuid.uuid4()),
        'username': data['username'],
        'password': generate_password_hash(data['password']),
        'role': data['role']
    }
    
    users.append(new_user)
    save_users(users)
    
    return jsonify({'success': True, 'message': '用户创建成功'})

# 更新用户信息
@app.route('/api/users/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    data = request.get_json()
    users = load_users()
    
    user_index = next((i for i, user in enumerate(users) if user['id'] == user_id), None)
    if user_index is None:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 检查用户名是否与其他用户冲突
    if any(user['username'] == data['username'] and user['id'] != user_id for user in users):
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    # 更新用户信息
    users[user_index]['username'] = data['username']
    users[user_index]['role'] = data['role']
    
    # 如果提供了新密码，则更新密码
    if data.get('password'):
        users[user_index]['password'] = generate_password_hash(data['password'])
    
    save_users(users)
    return jsonify({'success': True, 'message': '用户更新成功'})

# 删除用户
@app.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    users = load_users()
    
    # 过滤掉要删除的用户
    updated_users = [user for user in users if user['id'] != user_id]
    
    if len(updated_users) == len(users):
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    save_users(updated_users)
    return jsonify({'success': True, 'message': '用户删除成功'})

# 启动 Flask 应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
