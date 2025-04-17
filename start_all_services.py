import subprocess
import sys
import os
import time
import signal
import threading
import atexit

# 存储进程对象，用于优雅关闭
processes = []

def signal_handler(sig, frame):
    print("\n正在关闭所有服务...")
    stop_all_services()
    sys.exit(0)

def stop_all_services():
    """优雅地关闭所有服务"""
    for process in processes:
        if process and process.poll() is None:  # 如果进程仍在运行
            print(f"正在关闭 {process.args} 服务...")
            if sys.platform == 'win32':
                process.terminate()  # Windows下使用terminate()
            else:
                process.send_signal(signal.SIGTERM)  # Unix下使用SIGTERM信号
    
    # 等待所有进程关闭
    for process in processes:
        if process:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"无法正常关闭 {process.args}，强制终止...")
                process.kill()

def start_mcpo_service():
    """启动MCPO服务"""
    print("正在启动MCPO服务...")
    mcpo_path = os.path.join(os.getcwd(), "mcpo", "mcp.json")
    
    if not os.path.exists(mcpo_path):
        mcpo_path = "mcp.json"  # 尝试当前目录
        if not os.path.exists(mcpo_path):
            print(f"错误: 无法找到配置文件 {mcpo_path}")
            return None
    
    try:
        print(f"使用配置文件: {mcpo_path}")
        
        # 尝试使用uvx启动
        try:
            process = subprocess.Popen(
                ["uvx", "mcpo", "--config", mcpo_path, "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            print("已使用uvx启动MCPO服务")
        except FileNotFoundError:
            # 如果没有uvx，则尝试使用python -m mcpo
            print("未找到uvx，尝试使用python启动MCPO服务")
            process = subprocess.Popen(
                [sys.executable, "-m", "mcpo", "--config", mcpo_path, "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        
        processes.append(process)
        return process
    except Exception as e:
        print(f"启动MCPO服务失败: {e}")
        return None

def start_rag_server():
    """启动RAG服务器"""
    print("正在启动RAG服务器...")
    
    if not os.path.exists("rag_server.py"):
        print("错误: 找不到rag_server.py文件")
        return None
    
    try:
        process = subprocess.Popen(
            [sys.executable, "rag_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(process)
        return process
    except Exception as e:
        print(f"启动RAG服务器失败: {e}")
        return None

def start_video_server():
    """启动视频服务器"""
    print("正在启动视频服务器...")
    
    if not os.path.exists("video_server.py"):
        print("错误: 找不到video_server.py文件")
        return None
    
    try:
        # 正确分离命令和参数
        process = subprocess.Popen(
            [sys.executable, "video_server.py", "--video_source", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(process)
        return process
    except Exception as e:
        print(f"启动视频服务器失败: {e}")
        return None

def log_output(process, service_name):
    """实时输出进程日志"""
    if not process or not process.stdout:
        print(f"[{service_name}] 没有可用的输出流")
        return
        
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"[{service_name}] {line}", end='')
        
        # 检查进程是否已结束
        if process.poll() is not None:
            remaining_output = process.stdout.read()
            if remaining_output:
                print(f"[{service_name}] {remaining_output}")
            print(f"[{service_name}] 进程已结束，返回代码: {process.returncode}")
            break

def main():
    """主函数：启动所有服务并监控输出"""
    # 注册信号处理，用于捕获Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 注册退出函数，确保脚本退出时关闭所有服务
    atexit.register(stop_all_services)
    
    print("=== 智能监控系统 - 服务启动 ===")
    
    # 启动MCPO服务
    mcpo_process = start_mcpo_service()
    
    if not mcpo_process:
        print("MCPO服务启动失败，请检查配置文件和安装")
        return
    
    # 等待MCPO服务启动
    print("等待MCPO服务初始化...")
    time.sleep(5)
    
    # 启动RAG服务器
    rag_process = start_rag_server()
    if not rag_process:
        print("警告: RAG服务器启动失败，继续启动其他服务")
    else:
        # 等待RAG服务器启动
        print("等待RAG服务器初始化...")
        time.sleep(3)
    
    # 启动视频服务器
    video_process = start_video_server()
    if not video_process:
        print("警告: 视频服务器启动失败，继续启动其他服务")
    else:
        # 等待视频服务器启动
        print("等待视频服务器初始化...")
        time.sleep(2)
    
    # 创建线程记录输出
    threads = []
    
    if mcpo_process:
        threads.append(threading.Thread(target=log_output, args=(mcpo_process, "MCPO"), daemon=True))
    
    if rag_process:
        threads.append(threading.Thread(target=log_output, args=(rag_process, "RAG"), daemon=True))
    
    if video_process:
        threads.append(threading.Thread(target=log_output, args=(video_process, "视频服务"), daemon=True))
    
    # 启动所有线程
    for thread in threads:
        thread.start()
    
    print("\n所有服务已启动！按Ctrl+C可以停止所有服务。")
    
    # 检查服务状态并显示访问地址
    print("\n=== 服务访问地址 ===")
    print("MCPO服务文档: http://localhost:8000/docs")
    print("RAG服务文档: http://localhost:8085/docs")
    print("视频监控服务: http://localhost:8000/video_feed")
    print("智能问答模块: 通过前端Vue应用访问，连接到RAG服务(http://localhost:8085/detect_intent/)")
    
    # 主线程等待所有子进程完成
    while True:
        try:
            # 检查所有进程是否仍在运行
            running_processes = [p for p in processes if p and p.poll() is None]
            if not running_processes:
                print("所有服务已停止运行。")
                break
                
            # 如果有进程结束，重新组织进程列表
            exited_processes = [p for p in processes if p and p.poll() is not None]
            for p in exited_processes:
                index = processes.index(p)
                if index >= 0:
                    print(f"服务已退出: {p.args[0]}")
                    processes[index] = None
                    
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n接收到中断信号，正在关闭所有服务...")
            break
    
    stop_all_services()
    print("所有服务已关闭。")

if __name__ == "__main__":
    main()