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

# 读取 retoken.json 文件
def load_retoken():
    try:
        with open('json/retoken.json', 'r') as f:
            retokens = json.load(f)
        return retokens
    except FileNotFoundError:
        return []

# 写入 retoken.json 文件
def save_retoken(data):
    with open('json/retoken.json', 'w') as f:
        json.dump(data, f, indent=4)

# 读取 actoken.json 文件
def load_access_tokens():
    try:
        with open('json/actoken.json', 'r') as f:
            access_tokens = json.load(f)
        return access_tokens
    except FileNotFoundError:
        return []

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

# 刷新 access_token 的主函数
def refresh_access_tokens():
    # 读取 retoken.json 文件
    refresh_tokens = load_retoken()

    access_tokens = load_access_tokens()

    # 将现有的 access_tokens 转换为字典，方便更新
    access_token_dict = {list(item.keys())[0]: list(item.values())[0] for item in access_tokens}

    # 用于记录获取 access_token 失败的邮箱和 refresh_token
    failed_tokens = []

    # 遍历 refresh_token 列表，获取每个 email 和 token
    for item in refresh_tokens:
        for email, refresh_token in item.items():
            # 使用 POST 请求通过 refresh_token 获取 access_token
            response = requests.post(
                "https://token.oaifree.com/api/auth/refresh",
                data={"refresh_token": refresh_token}
            )
            # 获取 access_token
            access_token = response.json().get("access_token")

            if access_token:  # 如果成功获取到 access_token
                # 更新 access_token
                access_token_dict[email] = access_token
            else:  # 如果 access_token 为空，删除对应的条目
                failed_tokens.append({email: refresh_token})
                if email in access_token_dict:
                    del access_token_dict[email]  # 从 access_token_dict 中删除该 email 条目

    # 将更新后的 access_token 字典转换回列表形式
    updated_access_tokens = [{email: token} for email, token in access_token_dict.items()]

    # 将结果写入到 actoken.json 文件
    with open('json/actoken.json', 'w') as f:
        json.dump(updated_access_tokens, f, indent=4)

    # 如果有失败的 token，记录到 failed_tokens.json
    if failed_tokens:
        save_failed_tokens(failed_tokens)
    else:
        save_failed_tokens([])

    return updated_access_tokens



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

# 主页路由，根据 actoken.json 生成相应数量的 div 盒子
@app.route('/')
@login_required
def index():
    # 读取 actoken.json 中的 access_tokens
    access_tokens = load_access_tokens()

    # 渲染模板，传递 access_tokens 列表
    return render_template('index.html', access_tokens=access_tokens)


# 定义一个路由，用于处理 UNIQUE_NAME 的提交
@app.route('/submit_name', methods=['POST'])
@login_required
def submit_name():
    data = request.json
    unique_name = data.get('unique_name')
    index = data.get('index')
    access_tokens = load_access_tokens()
    # 确保 index 是有效的索引
    if index and 1 <= index <= len(access_tokens):
        # 获取对应的 access_token
        token_info = access_tokens[index - 1] 
        email, access_token = list(token_info.items())[0]
        token_key = register_token(access_token, unique_name)
        print(token_key)
        logurl = getoauth(token_key)
        return jsonify({
            "status": "success",
            # "email": email,
            "login_url": logurl
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid index."
        }), 400

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


# Admin 主页路由
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():

    if request.method == 'GET':
        # 加载并显示 retoken.json 文件中的内容
        retokens = load_retoken()
        return render_template('admin.html', retokens=retokens)

    if request.method == 'POST':
        # 获取更新后的 retoken 数据
        new_retokens = request.json.get('retokens')
        
        # 如果数据格式有效，保存到文件
        if new_retokens:
            save_retoken(new_retokens)
            return jsonify({"status": "success", "message": "retoken.json 已更新！"}), 200
        else:
            return jsonify({"status": "error", "message": "无效的数据格式！"}), 400


# 用户管理部分  
USERS_FILE = 'json/user.json'

@app.route('/user-management')
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
    app.run(host='0.0.0.0', debug=False)
